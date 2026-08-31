"""API views enforcing server-side RBAC + audit logging."""
import csv
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Case, Count, Exists, F, FloatField, Max, OuterRef, Q, Value, When
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import choices
from .audit import log_action
from .backup_ops import backup_dir, create_backup_zip, list_backups, restore_from_zip
from .models import digits_only
from .models import (
    AuditLogEntry,
    Assessment,
    Caregiver,
    CaseFileChecklistItem,
    ConsentRecord,
    Cow1Plan,
    Evaluation,
    FamilyCarePlan,
    GroupWorkSession,
    Household,
    HouseholdMember,
    Organisation,
    PartnerAgency,
    PlannedVisit,
    ProcessNote,
    ProtectionIncident,
    Referral,
    ServiceDelivery,
    ServiceTarget,
    SiteConfig,
    SupportingDocument,
)
from .sa_id import parse_sa_id
from .permissions import (
    FIELD_WORKER_ROLES,
    IsAdminRole,
    IsStaffRole,
    ROLE_ADMIN,
    ROLE_AUXILIARY,
    ROLE_CAREGIVER,
    ROLE_CASE_WORKER,
    ROLE_CYCW,
    ROLE_PERMISSION_TEXT,
    can_edit_records,
    can_signoff_checklist,
    can_view_audit,
    is_field_worker,
    is_system_builder,
    is_training_user,
    training_households_filter,
    user_role,
)
from .serializers import (
    AssessmentSerializer,
    AuditLogSerializer,
    CaregiverSerializer,
    ChecklistItemSerializer,
    ConsentRecordSerializer,
    Cow1PlanSerializer,
    EvaluationSerializer,
    FamilyCarePlanSerializer,
    GroupWorkSessionSerializer,
    HouseholdDetailSerializer,
    HouseholdListSerializer,
    HouseholdSerializer,
    HouseholdMemberSerializer,
    OrganisationSerializer,
    PartnerAgencySerializer,
    PlannedVisitSerializer,
    ProcessNoteSerializer,
    ProtectionIncidentSerializer,
    ReferralSerializer,
    ServiceDeliverySerializer,
    SiteConfigSerializer,
    SupportingDocumentSerializer,
    UserSerializer,
)

CONFIRM_FIELDS = ['surname', 'id_number', 'date_of_birth']


def household_text_search(qs, q):
    """Surname / household number / ID (including spaced or dashed ID numbers)."""
    digits = digits_only(q)
    clauses = (
        Q(org_household_number__icontains=q)
        | Q(caregiver__surname__icontains=q)
        | Q(caregiver__id_number__icontains=q)
        | Q(caregiver__name__icontains=q)
        | Q(members__surname__icontains=q)
        | Q(members__id_number__icontains=q)
    )
    if digits:
        clauses |= Q(caregiver__id_number_digits__icontains=digits) | Q(members__id_number_digits__icontains=digits)
    return qs.filter(clauses).distinct()


def lookup_households_for_query(qs, raw):
    """
    Access-style open-by-ID: unique ID number (or exact household number) opens the file.
    Spaces and dashes in ID numbers are ignored.
    """
    raw = (raw or '').strip()
    digits = digits_only(raw)
    opened_by = None
    matched_label = ''
    hit_ids = []

    if digits and len(digits) >= 6:
        cg_hits = list(
            Caregiver.objects.filter(household__in=qs, id_number_digits=digits).select_related('household')
        )
        mem_hits = list(
            HouseholdMember.objects.filter(household__in=qs, id_number_digits=digits).select_related('household')
        )
        for person in cg_hits + mem_hits:
            hid = person.household_id
            if hid not in hit_ids:
                hit_ids.append(hid)
        if hit_ids:
            opened_by = 'id_number'
            person = (cg_hits + mem_hits)[0]
            role = 'caregiver' if person in cg_hits else 'member'
            matched_label = f'{person.name} {person.surname}'.strip() or person.id_number
            if role == 'member':
                matched_label = f'{matched_label} (household member)'

    if not hit_ids and raw:
        exact = list(qs.filter(org_household_number__iexact=raw).values_list('id', flat=True))
        if not exact and digits:
            exact = list(qs.filter(org_household_number__iexact=digits).values_list('id', flat=True))
        if exact:
            hit_ids = exact
            opened_by = 'household_number'
            hh = qs.filter(pk=exact[0]).select_related('caregiver').first()
            cg = getattr(hh, 'caregiver', None) if hh else None
            matched_label = (f'{cg.name} {cg.surname}'.strip() if cg else '') or (hh.org_household_number if hh else '')

    if hit_ids:
        households = qs.filter(pk__in=hit_ids).prefetch_related(
            'members', 'caregiver', 'assigned_to', 'checklist_items'
        )
        n = len(hit_ids)
        match = 'unique' if n == 1 else 'multiple'
        return match, opened_by, matched_label, households

    fuzzy = household_text_search(qs, raw).prefetch_related(
        'members', 'caregiver', 'assigned_to', 'checklist_items'
    )
    n = fuzzy.count()
    if n == 1:
        hh = fuzzy.first()
        cg = getattr(hh, 'caregiver', None)
        label = (f'{cg.name} {cg.surname}'.strip() if cg else '') or hh.org_household_number
        return 'unique', 'search', label, fuzzy
    if n > 1:
        return 'multiple', 'search', '', fuzzy[:50]
    return 'none', None, '', fuzzy.none()


def scoped_household_qs(user):
    """Field workers only see assigned households. Caregivers see their linked file. Training logins only see TEST- files."""
    qs = Household.objects.all()
    if is_training_user(user):
        qs = qs.filter(training_households_filter())
    else:
        qs = qs.exclude(training_households_filter())
    if is_field_worker(user):
        qs = qs.filter(assigned_to=user)
    elif user_role(user) == ROLE_CAREGIVER:
        qs = qs.filter(caregiver__user=user)
    return qs


def _ensure_checklist(household):
    """Populate the standard NPO checklist template for a household (once)."""
    if household.checklist_items.exists():
        return
    items = [
        CaseFileChecklistItem(household=household, category=cat, sub_item=sub)
        for cat, sub in choices.CHECKLIST_TEMPLATE
    ]
    CaseFileChecklistItem.objects.bulk_create(items)


def filter_unconfirmed(qs, field):
    """Households where the caregiver or any member has `field` with a value but unconfirmed."""
    return qs.filter(_unconfirmed_q(field)).distinct()


def _unconfirmed_q(field):
    if field == 'date_of_birth':
        cg = Q(caregiver__date_of_birth__isnull=False, caregiver__date_of_birth_confirmed=False)
        mem = Q(members__date_of_birth__isnull=False, members__date_of_birth_confirmed=False)
    else:
        cg = Q(**{f'caregiver__{field}__gt': '', f'caregiver__{field}_confirmed': False})
        mem = Q(**{f'members__{field}__gt': '', f'members__{field}_confirmed': False})
    return cg | mem


def annotate_completeness(qs):
    """Annotate a case-file completeness percentage from checklist items marked 'Yes'."""
    return qs.annotate(
        _total=Count('checklist_items', distinct=True),
        _yes=Count('checklist_items', filter=Q(checklist_items__has_evidence='Yes'), distinct=True),
    ).annotate(
        _pct=Case(
            When(_total=0, then=Value(0.0)),
            default=100.0 * F('_yes') / F('_total'),
            output_field=FloatField(),
        )
    )


# ------------------------------ Auth ------------------------------
class LoginView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        if not user:
            return Response({'detail': 'Invalid username or password.'},
                            status=status.HTTP_401_UNAUTHORIZED)
        token, _ = Token.objects.get_or_create(user=user)
        log_action(user, 'viewed', 'Logged in')
        return Response({'token': token.key, 'user': UserSerializer(user).data})


class LogoutView(APIView):
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response({'detail': 'Logged out.'})


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated, IsStaffRole]

    def post(self, request):
        current = request.data.get('current_password') or ''
        new = request.data.get('new_password') or ''
        if not request.user.check_password(current):
            return Response({'detail': 'Current password is incorrect.'}, status=400)
        try:
            validate_password(new, user=request.user)
        except DjangoValidationError as e:
            return Response({'detail': ' '.join(e.messages)}, status=400)
        request.user.set_password(new)
        request.user.save()
        Token.objects.filter(user=request.user).delete()
        token = Token.objects.create(user=request.user)
        log_action(request.user, 'edited', 'Changed own password')
        return Response({'detail': 'Password updated.', 'token': token.key})


class MeView(APIView):
    def get(self, request):
        data = UserSerializer(request.user).data
        role = data.get('role')
        data['permissions'] = {
            'can_view_audit': can_view_audit(request.user),
            'can_signoff_checklist': can_signoff_checklist(request.user),
            'can_edit_records': can_edit_records(request.user),
            'can_edit_checklist_evidence': can_signoff_checklist(request.user),
            'can_manage_staff': user_role(request.user) == ROLE_ADMIN,
        }
        return Response(data)


# ------------------------------ Household ------------------------------
class HouseholdViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get_queryset(self):
        return scoped_household_qs(self.request.user).prefetch_related(
            'members', 'caregiver', 'assigned_to', 'checklist_items'
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return HouseholdListSerializer
        if self.action == 'retrieve':
            return HouseholdDetailSerializer
        return HouseholdSerializer

    @action(detail=False, methods=['get'], url_path='next-file-number')
    def next_file_number(self, request):
        return Response({
            'org_household_number': Household.next_file_number(
                training=is_training_user(request.user)
            ),
        })

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        q = request.query_params.get('q') or request.query_params.get('search')
        if q:
            qs = household_text_search(qs, q)
        unconfirmed = request.query_params.get('unconfirmed')
        if unconfirmed in ('id_number', 'surname', 'date_of_birth'):
            qs = filter_unconfirmed(qs, unconfirmed)
        if request.query_params.get('assigned_to_me'):
            qs = qs.filter(assigned_to=request.user)
        assigned_to = request.query_params.get('assigned_to')
        if assigned_to and assigned_to.isdigit():
            qs = qs.filter(assigned_to__id=assigned_to).distinct()
        case_status = request.query_params.get('status')
        if case_status:
            qs = qs.filter(status=case_status)
        if request.query_params.get('signed'):
            qs = qs.filter(checklist_signed_at__isnull=False)
        band = request.query_params.get('band')
        if band in ('ready', 'in_progress', 'needs_attention'):
            qs = annotate_completeness(qs)
            if band == 'ready':
                qs = qs.filter(_pct__gte=90)
            elif band == 'in_progress':
                qs = qs.filter(_pct__gte=50, _pct__lt=90)
            else:
                qs = qs.filter(_pct__lt=50)
        ordering = request.query_params.get('ordering')
        if ordering in ('completeness', '-completeness'):
            qs = annotate_completeness(qs)
            qs = qs.order_by('_pct' if ordering == 'completeness' else '-_pct', '-id')
        page = self.paginate_queryset(qs)
        serializer = HouseholdListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        log_action(request.user, 'viewed', f'Household #{instance.pk} ({instance.org_household_number})')
        return Response(HouseholdDetailSerializer(instance).data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        client_version = request.data.get('version')
        # DB-level guard: lock the row for the duration of the transaction so two
        # concurrent writers cannot both read the same version and both win.
        with transaction.atomic():
            instance = self.get_queryset().select_for_update().filter(pk=kwargs['pk']).first()
            if instance is None:
                raise Http404
            if client_version is not None and str(client_version) != str(instance.version):
                return Response(
                    {'detail': 'This record was modified by another user. Please refresh and re-apply your changes.',
                     'code': 'version_conflict', 'current_version': instance.version},
                    status=status.HTTP_409_CONFLICT,
                )
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            data = serializer.data
        return Response(data)

    def perform_create(self, serializer):
        if not can_edit_records(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Your login can view this file but cannot change it.')
        obj = serializer.save()
        _ensure_checklist(obj)
        log_action(self.request.user, 'created', f'Household #{obj.pk} ({obj.org_household_number})')

    def perform_update(self, serializer):
        if not can_edit_records(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Your login can view this file but cannot change it.')
        obj = serializer.save(version=serializer.instance.version + 1)
        log_action(self.request.user, 'edited', f'Household #{obj.pk} ({obj.org_household_number})')

    def perform_destroy(self, instance):
        if not can_edit_records(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Your login can view this file but cannot change it.')
        desc = f'Household #{instance.pk} ({instance.org_household_number})'
        instance.delete()
        log_action(self.request.user, 'deleted', desc)

    @action(detail=True, methods=['post'])
    def print(self, request, pk=None):
        instance = self.get_object()
        log_action(request.user, 'printed', f'Household #{instance.pk} ({instance.org_household_number})')
        return Response({'detail': 'Print action logged.'})

    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        """Activity timeline for a household, drawn from the audit log."""
        instance = self.get_object()  # enforces RBAC scoping
        entries = AuditLogEntry.objects.select_related('user').filter(
            target_description__regex=rf'Household #{instance.pk}([^0-9]|$)'
        )[:200]
        log_action(request.user, 'viewed', f'Timeline for Household #{instance.pk}')
        return Response(AuditLogSerializer(entries, many=True).data)

    @action(detail=True, methods=['post'])
    def sign_checklist(self, request, pk=None):
        """Supervisor/admin stamps their sign-off on the case-file checklist."""
        if not can_signoff_checklist(request.user):
            return Response({'detail': 'Only supervisors/administrators may sign off the checklist.'},
                            status=status.HTTP_403_FORBIDDEN)
        instance = self.get_object()
        instance.checklist_signed_by = request.user
        instance.checklist_signed_name = request.user.get_full_name() or request.user.username
        instance.checklist_signed_sacssp = request.data.get('sacssp', '')
        instance.checklist_signed_at = timezone.now()
        instance.save()
        log_action(request.user, 'confirmed', f'Signed off checklist for Household #{instance.pk}')
        return Response(HouseholdDetailSerializer(instance).data)

    @action(detail=False, methods=['get'])
    def lookup(self, request):
        """Type an ID number (or household number) and open the matching case file."""
        raw = (request.query_params.get('q') or request.query_params.get('id_number') or '').strip()
        if not raw:
            return Response({'q': '', 'digits': '', 'match': 'none', 'opened_by': None,
                             'matched_label': '', 'households': []})
        qs = scoped_household_qs(request.user)
        match, opened_by, label, households = lookup_households_for_query(qs, raw)
        data = HouseholdListSerializer(households, many=True).data
        return Response({
            'q': raw,
            'digits': digits_only(raw),
            'match': match,
            'opened_by': opened_by,
            'matched_label': label,
            'households': data,
        })

    @action(detail=False, methods=['get'])
    def verification_count(self, request):
        """Count of households (in scope) with any unconfirmed surname/id/dob."""
        qs = scoped_household_qs(request.user)
        by_field = {}
        for field in ('id_number', 'surname', 'date_of_birth'):
            by_field[field] = qs.filter(_unconfirmed_q(field)).distinct().count()
        combined = _unconfirmed_q('id_number') | _unconfirmed_q('surname') | _unconfirmed_q('date_of_birth')
        total = qs.filter(combined).distinct().count()
        return Response({'total': total, 'by_field': by_field})

    @action(detail=False, methods=['post'])
    def bulk_reassign(self, request):
        """Supervisor/admin: move households between case workers in bulk."""
        if user_role(request.user) not in ('admin', 'supervisor'):
            return Response({'detail': 'Only supervisors/administrators may reassign caseloads.'},
                            status=status.HTTP_403_FORBIDDEN)
        to_user_id = request.data.get('to_user')
        from_user_id = request.data.get('from_user')
        household_ids = request.data.get('household_ids')
        if not to_user_id:
            return Response({'detail': 'to_user is required.'}, status=400)
        try:
            to_user = User.objects.get(pk=to_user_id)
        except User.DoesNotExist:
            return Response({'detail': 'Target user not found.'}, status=404)
        from_user = None
        if from_user_id:
            from_user = User.objects.filter(pk=from_user_id).first()

        households = Household.objects.all()
        if household_ids:
            households = households.filter(pk__in=household_ids)
        elif from_user:
            households = households.filter(assigned_to=from_user)
        else:
            return Response({'detail': 'Provide household_ids or from_user.'}, status=400)

        count = 0
        for hh in households:
            if from_user:
                hh.assigned_to.remove(from_user)
            hh.assigned_to.add(to_user)
            count += 1
            log_action(request.user, 'edited',
                       f'Reassigned Household #{hh.pk} to {to_user.get_full_name() or to_user.username}')
        return Response({'reassigned': count,
                         'to_user': to_user.get_full_name() or to_user.username})


# ------------------------------ Person base viewset ------------------------------
class _PersonViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsStaffRole]
    label = 'record'

    def get_queryset(self):
        households = scoped_household_qs(self.request.user)
        qs = self.model.objects.filter(household__in=households)
        household_id = self.request.query_params.get('household')
        if household_id:
            qs = qs.filter(household_id=household_id)
        return qs

    def _desc(self, obj):
        return f'{self.label}: {obj.name} {obj.surname} (Household #{obj.household_id})'

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        log_action(request.user, 'viewed', self._desc(instance))
        return Response(self.get_serializer(instance).data)

    def perform_create(self, serializer):
        if not can_edit_records(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Your login can view this file but cannot change it.')
        obj = serializer.save()
        log_action(self.request.user, 'created', self._desc(obj))

    def perform_update(self, serializer):
        if not can_edit_records(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Your login can view this file but cannot change it.')
        obj = serializer.save()
        log_action(self.request.user, 'edited', self._desc(obj))

    def perform_destroy(self, instance):
        if not can_edit_records(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Your login can view this file but cannot change it.')
        desc = self._desc(instance)
        instance.delete()
        log_action(self.request.user, 'deleted', desc)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm a single field (surname/id_number/date_of_birth)."""
        obj = self.get_object()
        field = request.data.get('field')
        if field not in CONFIRM_FIELDS:
            return Response({'detail': 'Invalid field.'}, status=400)
        setattr(obj, f'{field}_confirmed', True)
        setattr(obj, f'{field}_confirmed_by', request.user)
        setattr(obj, f'{field}_confirmed_at', timezone.now())
        obj.save()
        log_action(request.user, 'confirmed', f'{field} for {self._desc(obj)}')
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'])
    def suggest(self, request, pk=None):
        """INTEGRATION POINT for the future offline OCR pipeline.

        A suggested value for surname/id_number/date_of_birth is written and the
        corresponding *_confirmed flag is RESET to False (requires re-confirmation).
        Requires authentication.
        """
        obj = self.get_object()
        field = request.data.get('field')
        value = request.data.get('value')
        if field not in CONFIRM_FIELDS:
            return Response({'detail': 'Invalid field.'}, status=400)
        setattr(obj, field, value)
        setattr(obj, f'{field}_confirmed', False)
        setattr(obj, f'{field}_confirmed_by', None)
        setattr(obj, f'{field}_confirmed_at', None)
        obj.save()
        log_action(request.user, 'suggested', f'{field} suggestion for {self._desc(obj)}')
        return Response(self.get_serializer(obj).data)


class CaregiverViewSet(_PersonViewSet):
    model = Caregiver
    serializer_class = CaregiverSerializer
    label = 'Caregiver'

    @action(detail=True, methods=['post'], url_path='set-login')
    def set_login(self, request, pk=None):
        """Administrator: give this household caregiver a login, or update the password."""
        if user_role(request.user) != ROLE_ADMIN:
            return Response({'detail': 'Only administrators can set caregiver logins.'}, status=403)
        cg = self.get_object()
        username = (request.data.get('username') or '').strip()
        password = request.data.get('password') or ''
        if cg.user_id:
            login = cg.user
            if username and username != login.username:
                if User.objects.filter(username=username).exclude(pk=login.pk).exists():
                    return Response({'detail': 'That username is already in use.'}, status=400)
                login.username = username
            if password:
                try:
                    validate_password(password, user=login)
                except DjangoValidationError as e:
                    return Response({'detail': ' '.join(e.messages)}, status=400)
                login.set_password(password)
                Token.objects.filter(user=login).delete()
            login.first_name = login.first_name or cg.name
            login.last_name = login.last_name or cg.surname
            login.save()
            _set_user_role(login, ROLE_CAREGIVER)
            log_action(request.user, 'edited', f'Caregiver login {login.username}')
            return Response(UserSerializer(login).data)
        if not username or not password:
            return Response({'detail': 'Username and password are required for a new caregiver login.'}, status=400)
        if User.objects.filter(username=username).exists():
            return Response({'detail': 'That username is already in use.'}, status=400)
        try:
            validate_password(password)
        except DjangoValidationError as e:
            return Response({'detail': ' '.join(e.messages)}, status=400)
        login = User.objects.create_user(
            username=username,
            password=password,
            first_name=cg.name or '',
            last_name=cg.surname or '',
            is_active=True,
        )
        _set_user_role(login, ROLE_CAREGIVER)
        cg.user = login
        cg.save(update_fields=['user'])
        log_action(request.user, 'created', f'Caregiver login {login.username} for Household #{cg.household_id}')
        return Response(UserSerializer(login).data, status=201)


class HouseholdMemberViewSet(_PersonViewSet):
    model = HouseholdMember
    serializer_class = HouseholdMemberSerializer
    label = 'Household member'

    @action(detail=False, methods=['get'])
    def missing_dob(self, request):
        """Members (in scope) with no date of birth captured yet."""
        qs = self.get_queryset().filter(date_of_birth__isnull=True).select_related('household')
        data = [{
            'id': m.id,
            'name': f'{m.name} {m.surname}'.strip(),
            'household_id': m.household_id,
            'org_household_number': m.household.org_household_number,
        } for m in qs[:100]]
        return Response(data)


# ------------------------------ Supporting documents ------------------------------
class SupportingDocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsStaffRole]
    serializer_class = SupportingDocumentSerializer

    def get_queryset(self):
        from django.contrib.contenttypes.models import ContentType
        households = scoped_household_qs(self.request.user)
        hh_ids = households.values('id')
        cg_ids = Caregiver.objects.filter(household_id__in=hh_ids).values('id')
        mem_ids = HouseholdMember.objects.filter(household_id__in=hh_ids).values('id')
        ct_h = ContentType.objects.get_for_model(Household)
        ct_c = ContentType.objects.get_for_model(Caregiver)
        ct_m = ContentType.objects.get_for_model(HouseholdMember)
        qs = SupportingDocument.objects.filter(
            Q(content_type=ct_h, object_id__in=hh_ids)
            | Q(content_type=ct_c, object_id__in=cg_ids)
            | Q(content_type=ct_m, object_id__in=mem_ids)
        )
        parent_type = self.request.query_params.get('parent_type')
        parent_id = self.request.query_params.get('parent_id')
        if parent_type and parent_id:
            ct_map = {'household': ct_h, 'caregiver': ct_c, 'householdmember': ct_m}
            if parent_type in ct_map:
                qs = qs.filter(content_type=ct_map[parent_type], object_id=parent_id)

        household_id = self.request.query_params.get('household')
        if household_id and household_id.isdigit():
            hid = int(household_id)
            hh_cg_ids = Caregiver.objects.filter(household_id=hid).values('id')
            hh_mem_ids = HouseholdMember.objects.filter(household_id=hid).values('id')
            qs = qs.filter(
                Q(content_type=ct_h, object_id=hid)
                | Q(content_type=ct_c, object_id__in=hh_cg_ids)
                | Q(content_type=ct_m, object_id__in=hh_mem_ids)
            )
        return qs

    def perform_create(self, serializer):
        obj = serializer.save()
        log_action(self.request.user, 'created', f'Document "{obj.label}" ({obj.get_category_display()})')

    def perform_destroy(self, instance):
        desc = f'Document "{instance.label}"'
        instance.file.delete(save=False)
        instance.delete()
        log_action(self.request.user, 'deleted', desc)

    def _get_file_response(self, request, pk, as_attachment):
        try:
            obj = self.get_queryset().get(pk=pk)
        except SupportingDocument.DoesNotExist:
            raise Http404
        if not obj.file:
            raise Http404
        action_name = 'downloaded' if as_attachment else 'viewed'
        log_action(request.user, action_name, f'Document "{obj.label}" (#{obj.pk})')
        return FileResponse(obj.file.open('rb'), as_attachment=as_attachment,
                            filename=obj.file.name.split('/')[-1])

    @action(detail=True, methods=['get'])
    def view(self, request, pk=None):
        return self._get_file_response(request, pk, as_attachment=False)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        return self._get_file_response(request, pk, as_attachment=True)


# ------------------------------ Checklist ------------------------------
class ChecklistViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsStaffRole]
    serializer_class = ChecklistItemSerializer

    def get_queryset(self):
        households = scoped_household_qs(self.request.user)
        qs = CaseFileChecklistItem.objects.filter(household__in=households)
        household_id = self.request.query_params.get('household')
        if household_id:
            qs = qs.filter(household_id=household_id)
        return qs

    def _check_signoff_permission(self, request):
        if not can_signoff_checklist(request.user):
            return Response(
                {'detail': 'Only supervisors/administrators may sign off checklist items.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def update(self, request, *args, **kwargs):
        denied = self._check_signoff_permission(request)
        if denied:
            return denied
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
        serializer.is_valid(raise_exception=True)
        obj = serializer.save(checked_by=request.user, checked_at=timezone.now())
        log_action(request.user, 'edited', f'Checklist "{obj.sub_item}" for Household #{obj.household_id}')
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)


# ------------------------------ Audit log (admin only) ------------------------------
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        qs = AuditLogEntry.objects.select_related('user').all()
        user_id = self.request.query_params.get('user')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        action_q = self.request.query_params.get('action')
        if user_id:
            qs = qs.filter(user_id=user_id)
        if action_q:
            qs = qs.filter(action=action_q)
        if date_from:
            qs = qs.filter(timestamp__date__gte=date_from)
        if date_to:
            qs = qs.filter(timestamp__date__lte=date_to)
        return qs

    @action(detail=False, methods=['get'])
    def export(self, request):
        qs = self.get_queryset()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit_log.csv"'
        writer = csv.writer(response)
        writer.writerow(['ID', 'User', 'Action', 'Target', 'Timestamp'])
        for e in qs:
            uname = (e.user.get_full_name() or e.user.username) if e.user else 'system'
            writer.writerow([e.id, uname, e.action, e.target_description,
                             e.timestamp.strftime('%Y-%m-%d %H:%M:%S')])
        log_action(request.user, 'downloaded', 'Audit log CSV export')
        return response


class ProcessNoteViewSet(viewsets.ModelViewSet):
    """CW 11 structured process notes, scoped to households the user can see."""
    permission_classes = [IsAuthenticated, IsStaffRole]
    serializer_class = ProcessNoteSerializer

    def get_queryset(self):
        households = scoped_household_qs(self.request.user)
        qs = ProcessNote.objects.filter(household__in=households).select_related('created_by')
        household_id = self.request.query_params.get('household')
        if household_id:
            qs = qs.filter(household_id=household_id)
        return qs

    def perform_create(self, serializer):
        obj = serializer.save(created_by=self.request.user)
        log_action(self.request.user, 'created',
                   f'Process note for Household #{obj.household_id}')

    def perform_update(self, serializer):
        obj = serializer.save()
        log_action(self.request.user, 'edited',
                   f'Process note #{obj.pk} for Household #{obj.household_id}')

    def perform_destroy(self, instance):
        hid = instance.household_id
        instance.delete()
        log_action(self.request.user, 'deleted', f'Process note for Household #{hid}')


class AssessmentViewSet(viewsets.ModelViewSet):
    """CW 09 assessments, scoped to households the user can see."""
    permission_classes = [IsAuthenticated, IsStaffRole]
    serializer_class = AssessmentSerializer

    def get_queryset(self):
        households = scoped_household_qs(self.request.user)
        qs = Assessment.objects.filter(household__in=households).select_related('created_by')
        household_id = self.request.query_params.get('household')
        if household_id:
            qs = qs.filter(household_id=household_id)
        return qs

    def perform_create(self, serializer):
        household = serializer.validated_data['household']
        last = Assessment.objects.filter(household=household).aggregate(m=Max('version_number'))['m'] or 0
        obj = serializer.save(created_by=self.request.user, version_number=last + 1)
        log_action(self.request.user, 'created', f'Assessment v{obj.version_number} for Household #{obj.household_id}')

    def perform_update(self, serializer):
        obj = serializer.save()
        log_action(self.request.user, 'edited', f'Assessment for Household #{obj.household_id}')


class _HouseholdChildViewSet(viewsets.ModelViewSet):
    """CRUD for household-scoped case records (consent, care plan, Form 22, etc.)."""
    permission_classes = [IsAuthenticated, IsStaffRole]
    audit_label = 'Record'

    def get_queryset(self):
        households = scoped_household_qs(self.request.user)
        qs = self.model.objects.filter(household__in=households)
        household_id = self.request.query_params.get('household')
        if household_id:
            qs = qs.filter(household_id=household_id)
        return qs

    def perform_create(self, serializer):
        obj = serializer.save(created_by=self.request.user)
        log_action(self.request.user, 'created',
                   f'{self.audit_label} for Household #{obj.household_id}')

    def perform_update(self, serializer):
        obj = serializer.save()
        log_action(self.request.user, 'edited',
                   f'{self.audit_label} #{obj.pk} for Household #{obj.household_id}')

    def perform_destroy(self, instance):
        hid = instance.household_id
        instance.delete()
        log_action(self.request.user, 'deleted', f'{self.audit_label} for Household #{hid}')


class ConsentRecordViewSet(_HouseholdChildViewSet):
    model = ConsentRecord
    serializer_class = ConsentRecordSerializer
    audit_label = 'Consent'


class FamilyCarePlanViewSet(_HouseholdChildViewSet):
    model = FamilyCarePlan
    serializer_class = FamilyCarePlanSerializer
    audit_label = 'Family care plan'


class ProtectionIncidentViewSet(_HouseholdChildViewSet):
    model = ProtectionIncident
    serializer_class = ProtectionIncidentSerializer
    audit_label = 'Form 22 protection incident'


class Cow1PlanViewSet(_HouseholdChildViewSet):
    model = Cow1Plan
    serializer_class = Cow1PlanSerializer
    audit_label = 'COW 1 plan'


class EvaluationViewSet(_HouseholdChildViewSet):
    model = Evaluation
    serializer_class = EvaluationSerializer
    audit_label = 'CW 12 evaluation'


class GroupWorkSessionViewSet(_HouseholdChildViewSet):
    model = GroupWorkSession
    serializer_class = GroupWorkSessionSerializer
    audit_label = 'GRW group session'


class ReferralViewSet(_HouseholdChildViewSet):
    model = Referral
    serializer_class = ReferralSerializer
    audit_label = 'Referral'

    def get_queryset(self):
        return super().get_queryset().select_related('household', 'household__caregiver', 'partner', 'member', 'created_by')


class PlannedVisitViewSet(_HouseholdChildViewSet):
    model = PlannedVisit
    serializer_class = PlannedVisitSerializer
    audit_label = 'Planned visit'

    def get_queryset(self):
        qs = super().get_queryset().select_related('household', 'household__caregiver', 'assigned_to', 'created_by')
        status = self.request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    @action(detail=True, methods=['post'])
    def mark_done(self, request, pk=None):
        visit = self.get_object()
        visit.status = 'done'
        visit.completed_at = timezone.localdate()
        visit.save()
        log_action(request.user, 'edited', f'Completed visit #{visit.pk} for Household #{visit.household_id}')
        return Response(PlannedVisitSerializer(visit).data)

    @action(detail=True, methods=['post'])
    def mark_missed(self, request, pk=None):
        visit = self.get_object()
        visit.status = 'missed'
        visit.save()
        log_action(request.user, 'edited', f'Missed visit #{visit.pk} for Household #{visit.household_id}')
        return Response(PlannedVisitSerializer(visit).data)


class PartnerAgencyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsStaffRole]
    serializer_class = PartnerAgencySerializer

    def get_queryset(self):
        qs = PartnerAgency.objects.all()
        if is_training_user(self.request.user):
            return qs.filter(is_training=True)
        return qs.filter(is_training=False)

    def perform_create(self, serializer):
        obj = serializer.save(is_training=is_training_user(self.request.user))
        log_action(self.request.user, 'created', f'Partner {obj.name}')

    def perform_destroy(self, instance):
        name = instance.name
        instance.delete()
        log_action(self.request.user, 'deleted', f'Partner {name}')


def _unlink_caregiver_login(user):
    try:
        cg = user.household_caregiver
    except Exception:
        return
    cg.user = None
    cg.save(update_fields=['user'])


def _link_caregiver_household(user, household_id):
    from .models import Caregiver
    hh = Household.objects.filter(pk=household_id).select_related('caregiver').first()
    if not hh:
        return 'Household not found.'
    cg = getattr(hh, 'caregiver', None)
    if not cg:
        return 'Add the caregiver on that household file first, then give them a login.'
    if cg.user_id and cg.user_id != user.pk:
        return 'That caregiver already has a login.'
    other = Caregiver.objects.filter(user=user).exclude(pk=cg.pk).first()
    if other:
        other.user = None
        other.save(update_fields=['user'])
    cg.user = user
    cg.save(update_fields=['user'])
    return None


def _set_user_role(user, role):
    if role not in settings.ALL_ROLES:
        raise ValueError(f'Unknown role: {role}')
    if is_system_builder(user) and role != ROLE_ADMIN:
        raise ValueError('The administrator keeps administrator privileges.')
    previous = user_role(user)
    user.groups.clear()
    group, _ = Group.objects.get_or_create(name=role)
    user.groups.add(group)
    user.is_staff = role == ROLE_ADMIN or is_system_builder(user)
    user.is_superuser = role == ROLE_ADMIN or is_system_builder(user)
    user.save()
    if previous == ROLE_CAREGIVER and role != ROLE_CAREGIVER:
        _unlink_caregiver_login(user)


class StaffViewSet(viewsets.ViewSet):
    """Create and manage real office logins (admin only)."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def list(self, request):
        users = User.objects.all().select_related('household_caregiver__household').order_by('username')
        if not is_training_user(request.user):
            users = users.exclude(username__in=settings.TRAINING_USERNAMES)
        return Response(UserSerializer(users, many=True).data)

    def create(self, request):
        username = (request.data.get('username') or '').strip()
        password = request.data.get('password') or ''
        role = request.data.get('role') or request.data.get('job_title') or ROLE_CYCW
        if not username:
            return Response({'detail': 'Username is required.'}, status=400)
        if User.objects.filter(username=username).exists():
            return Response({'detail': 'That username is already in use.'}, status=400)
        if role not in settings.ALL_ROLES:
            return Response({'detail': 'Choose a valid title.'}, status=400)
        try:
            validate_password(password)
        except DjangoValidationError as e:
            return Response({'detail': ' '.join(e.messages)}, status=400)
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=request.data.get('first_name') or '',
            last_name=request.data.get('last_name') or '',
            email=request.data.get('email') or '',
            is_active=request.data.get('is_active', True) is not False,
        )
        _set_user_role(user, role)
        household_id = request.data.get('household') or request.data.get('household_id')
        if household_id in ('', None):
            household_id = None
        if role == ROLE_CAREGIVER and household_id:
            err = _link_caregiver_household(user, household_id)
            if err:
                user.delete()
                return Response({'detail': err}, status=400)
        log_action(request.user, 'created', f'Staff account {user.username} ({role})')
        return Response(UserSerializer(user).data, status=201)

    def partial_update(self, request, pk=None):
        user = User.objects.filter(pk=pk).first()
        if not user:
            return Response({'detail': 'Staff member not found.'}, status=404)
        if 'first_name' in request.data:
            user.first_name = request.data.get('first_name') or ''
        if 'last_name' in request.data:
            user.last_name = request.data.get('last_name') or ''
        if 'email' in request.data:
            user.email = request.data.get('email') or ''
        if 'username' in request.data:
            new_name = (request.data.get('username') or '').strip()
            if is_system_builder(user) and new_name.lower() != user.username.lower():
                return Response(
                    {'detail': 'The live office administrator username cannot be changed.'},
                    status=400,
                )
            if not new_name:
                return Response({'detail': 'Username is required.'}, status=400)
            if User.objects.filter(username=new_name).exclude(pk=user.pk).exists():
                return Response({'detail': 'That username is already in use.'}, status=400)
            user.username = new_name
        if 'is_active' in request.data:
            active = bool(request.data.get('is_active'))
            if not active and is_system_builder(user):
                return Response(
                    {'detail': 'The administrator account cannot be deactivated.'},
                    status=400,
                )
            if not active and user.pk == request.user.pk:
                return Response({'detail': 'You cannot deactivate your own account.'}, status=400)
            if not active and user_role(user) == ROLE_ADMIN:
                others = User.objects.filter(is_active=True).exclude(pk=user.pk)
                if not any(user_role(u) == ROLE_ADMIN for u in others):
                    return Response({'detail': 'Keep at least one active administrator.'}, status=400)
            user.is_active = active
            if not active:
                Token.objects.filter(user=user).delete()
        user.save()
        role = request.data.get('role') or request.data.get('job_title')
        if role:
            if role not in settings.ALL_ROLES:
                return Response({'detail': 'Choose a valid title.'}, status=400)
            if is_system_builder(user) and role != ROLE_ADMIN:
                return Response(
                    {'detail': 'The live office administrator keeps administrator privileges.'},
                    status=400,
                )
            if user_role(user) == ROLE_ADMIN and role != ROLE_ADMIN:
                others = User.objects.filter(is_active=True).exclude(pk=user.pk)
                if not any(user_role(u) == ROLE_ADMIN for u in others):
                    return Response({'detail': 'Keep at least one administrator.'}, status=400)
            _set_user_role(user, role)
        household_id = request.data.get('household') or request.data.get('household_id')
        if household_id in ('', None):
            household_id = None
        if household_id and user_role(user) == ROLE_CAREGIVER:
            err = _link_caregiver_household(user, household_id)
            if err:
                return Response({'detail': err}, status=400)
        log_action(request.user, 'edited', f'Staff account {user.username}')
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=['post'], url_path='set-password')
    def set_password(self, request, pk=None):
        user = User.objects.filter(pk=pk).first()
        if not user:
            return Response({'detail': 'Staff member not found.'}, status=404)
        password = request.data.get('password') or ''
        try:
            validate_password(password, user=user)
        except DjangoValidationError as e:
            return Response({'detail': ' '.join(e.messages)}, status=400)
        user.set_password(password)
        user.save()
        Token.objects.filter(user=user).delete()
        log_action(request.user, 'edited', f'Set password for {user.username}')
        return Response({'detail': 'Password set. They will sign in with the new password.'})


# ------------------------------ Service delivery ------------------------------
def _month_bounds(ref=None):
    ref = ref or timezone.localdate()
    start = ref.replace(day=1)
    if start.month == 12:
        nxt = start.replace(year=start.year + 1, month=1)
    else:
        nxt = start.replace(month=start.month + 1)
    return start, nxt


class ServiceDeliveryViewSet(viewsets.ModelViewSet):
    """Daily service-delivery log, scoped to households the user can see."""
    permission_classes = [IsAuthenticated, IsStaffRole]
    serializer_class = ServiceDeliverySerializer

    def get_queryset(self):
        households = scoped_household_qs(self.request.user)
        qs = ServiceDelivery.objects.filter(household__in=households).select_related(
            'delivered_by', 'created_by', 'household'
        )
        household_id = self.request.query_params.get('household')
        if household_id:
            qs = qs.filter(household_id=household_id)
        month = self.request.query_params.get('month')  # YYYY-MM
        if month:
            try:
                y, m = month.split('-')
                start = timezone.datetime(int(y), int(m), 1).date()
                _, nxt = _month_bounds(start)
                qs = qs.filter(service_date__gte=start, service_date__lt=nxt)
            except Exception:
                pass
        date = self.request.query_params.get('date')
        if date:
            qs = qs.filter(service_date=date)
        return qs

    def _check_caseload(self, household):
        """Field workers may only log for households assigned to them."""
        if is_field_worker(self.request.user):
            if not household.assigned_to.filter(pk=self.request.user.pk).exists():
                return False
        return True

    def perform_create(self, serializer):
        household = serializer.validated_data['household']
        if not self._check_caseload(household):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You may only log services for households assigned to you.')
        obj = serializer.save(created_by=self.request.user, delivered_by=self.request.user)
        log_action(self.request.user, 'created',
                   f'Service "{obj.service_type}" for Household #{obj.household_id}')

    def perform_destroy(self, instance):
        hid = instance.household_id
        instance.delete()
        log_action(self.request.user, 'deleted', f'Service for Household #{hid}')

    @action(detail=False, methods=['post'])
    def bulk_log(self, request):
        """Log the same service for many households on a date (daily log screen)."""
        household_ids = request.data.get('household_ids') or []
        service_type = request.data.get('service_type')
        service_date = request.data.get('service_date') or str(timezone.localdate())
        notes = request.data.get('notes', '')
        if not service_type:
            return Response({'detail': 'service_type is required.'}, status=400)
        if service_date > str(timezone.localdate()):
            return Response({'detail': 'Service date cannot be in the future.'}, status=400)
        scoped = scoped_household_qs(request.user)
        created = 0
        for hh in scoped.filter(pk__in=household_ids):
            if not self._check_caseload(hh):
                continue
            ServiceDelivery.objects.create(
                household=hh, service_type=service_type, service_date=service_date,
                notes=notes, created_by=request.user, delivered_by=request.user,
            )
            created += 1
            log_action(request.user, 'created', f'Service "{service_type}" for Household #{hh.pk}')
        return Response({'logged': created})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Monthly service-delivery progress (staff + organisation + ranking + missed)."""
        start, nxt = _month_bounds()
        role = user_role(request.user)

        def served_ids(household_qs):
            hh_ids = list(household_qs.values_list('id', flat=True))
            served = set(
                ServiceDelivery.objects.filter(
                    household_id__in=hh_ids, service_date__gte=start, service_date__lt=nxt
                ).values_list('household_id', flat=True)
            )
            return hh_ids, served

        def bar(household_qs):
            hh_ids, served = served_ids(household_qs)
            total = len(hh_ids)
            n = len(served & set(hh_ids))
            pct = round(n * 100 / total) if total else 0
            return {'served': n, 'total': total, 'percent': pct}

        # Staff bar (households assigned to me) + my by-type breakdown.
        my_hh = scoped_household_qs(request.user).filter(assigned_to=request.user)
        staff = bar(my_hh)
        by_type = {}
        for row in ServiceDelivery.objects.filter(
            delivered_by=request.user, service_date__gte=start, service_date__lt=nxt
        ).values('service_type').annotate(c=Count('id')):
            by_type[row['service_type']] = row['c']
        staff['by_type'] = by_type
        staff_delivered = ServiceDelivery.objects.filter(
            delivered_by=request.user, service_date__gte=start, service_date__lt=nxt).count()
        staff_goal = getattr(getattr(request.user, 'service_target', None), 'monthly_goal', 0)
        staff['delivered'] = staff_delivered
        staff['goal'] = staff_goal
        staff['goal_percent'] = round(staff_delivered * 100 / staff_goal) if staff_goal else None

        org = None
        ranking = []
        if role in ('admin', 'supervisor'):
            org = bar(scoped_household_qs(request.user))
            delivered_map = {r['delivered_by']: r['c'] for r in ServiceDelivery.objects.filter(
                household__in=scoped_household_qs(request.user),
                service_date__gte=start, service_date__lt=nxt).values('delivered_by').annotate(c=Count('id'))}
            targets = {t.user_id: t.monthly_goal for t in ServiceTarget.objects.all()}
            workers = User.objects.filter(is_active=True, groups__name__in=FIELD_WORKER_ROLES).distinct()
            names = settings.TRAINING_USERNAMES
            if is_training_user(request.user):
                workers = workers.filter(username__in=names)
            else:
                workers = workers.exclude(username__in=names)
            for w in workers:
                b = bar(scoped_household_qs(request.user).filter(assigned_to=w))
                if b['total'] == 0:
                    continue
                dv = delivered_map.get(w.id, 0)
                g = targets.get(w.id, 0)
                ranking.append({
                    'user_id': w.id,
                    'name': w.get_full_name() or w.username,
                    'delivered': dv, 'goal': g,
                    'goal_percent': round(dv * 100 / g) if g else None,
                    **b,
                })
            ranking.sort(key=lambda r: r['percent'], reverse=True)

        # Weekly trend (last 4 weeks) over households in scope.
        today = timezone.localdate()
        trend = []
        for i in range(3, -1, -1):
            wk_start = today - timedelta(days=7 * i + 6)
            wk_end = today - timedelta(days=7 * i)
            count = ServiceDelivery.objects.filter(
                household__in=scoped_household_qs(request.user),
                service_date__gte=wk_start, service_date__lte=wk_end,
            ).count()
            trend.append({'label': wk_start.strftime('%d %b'), 'count': count})

        return Response({
            'month': start.strftime('%Y-%m'),
            'staff': staff, 'org': org, 'ranking': ranking, 'trend': trend,
        })

    @action(detail=False, methods=['get'])
    def beneficiary_reminders(self, request):
        """Children (members < 18) overdue for HIV testing or counselling."""
        from django.contrib.contenttypes.models import ContentType
        THRESHOLD_DAYS = 90
        TRACKED = ['HIV Testing Referral', 'Individual Counselling']
        scoped = scoped_household_qs(request.user)
        ct_member = ContentType.objects.get_for_model(HouseholdMember)
        today = timezone.localdate()
        out = []
        members = HouseholdMember.objects.filter(household__in=scoped).select_related('household')
        for m in members:
            if m.date_of_birth:
                age = today.year - m.date_of_birth.year - (
                    (today.month, today.day) < (m.date_of_birth.month, m.date_of_birth.day))
                if age >= 18:
                    continue
            for st in TRACKED:
                last = ServiceDelivery.objects.filter(
                    beneficiary_content_type=ct_member, beneficiary_object_id=m.id, service_type=st,
                ).order_by('-service_date').first()
                days = (today - last.service_date).days if last else None
                if days is None or days >= THRESHOLD_DAYS:
                    out.append({
                        'member_id': m.id,
                        'name': f'{m.name} {m.surname}'.strip(),
                        'household_id': m.household_id,
                        'org_household_number': m.household.org_household_number,
                        'service_type': st,
                        'last_service_date': str(last.service_date) if last else None,
                        'days_since': days,
                        'dob_missing': m.date_of_birth is None,
                    })
        # Children with a known DOB and a real overdue status are the most
        # actionable, so surface them first; DOB-missing rows sort last.
        out.sort(key=lambda r: (r['dob_missing'], -(10 ** 9 if r['days_since'] is None else r['days_since'])))
        return Response(out)

    @action(detail=False, methods=['get'])
    def export(self, request):
        """CSV export of a month's service delivery (supervisor/admin, donor reporting)."""
        if user_role(request.user) not in ('admin', 'supervisor'):
            return Response({'detail': 'Only supervisors/administrators may export service reports.'},
                            status=status.HTTP_403_FORBIDDEN)
        month = request.query_params.get('month')
        if month:
            y, m = month.split('-')
            start = timezone.datetime(int(y), int(m), 1).date()
        else:
            start = timezone.localdate().replace(day=1)
        _, nxt = _month_bounds(start)
        scoped = scoped_household_qs(request.user)
        qs = ServiceDelivery.objects.filter(
            household__in=scoped, service_date__gte=start, service_date__lt=nxt,
        ).select_related('household', 'delivered_by').order_by('service_date')

        def _beneficiary(s):
            b = s.beneficiary
            return f'{b.name} {b.surname}'.strip() if b else 'Whole household'

        def _delivered_by(s):
            return (s.delivered_by.get_full_name() or s.delivered_by.username) if s.delivered_by else ''

        COLUMNS = {
            'date': ('Date', lambda s: s.service_date.strftime('%Y-%m-%d')),
            'household': ('Household Number', lambda s: s.household.org_household_number),
            'beneficiary': ('Beneficiary', _beneficiary),
            'service_type': ('Service Type', lambda s: s.service_type),
            'delivered_by': ('Delivered By', _delivered_by),
            'notes': ('Notes', lambda s: s.notes),
        }
        requested = request.query_params.get('columns')
        keys = [k for k in requested.split(',') if k in COLUMNS] if requested else list(COLUMNS)
        if not keys:
            keys = list(COLUMNS)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="service_report_{start:%Y_%m}.csv"'
        writer = csv.writer(response)
        writer.writerow([COLUMNS[k][0] for k in keys])
        for s in qs:
            writer.writerow([COLUMNS[k][1](s) for k in keys])
        log_action(request.user, 'downloaded', f'Service report CSV export ({start:%Y-%m})')
        return response

    @action(detail=False, methods=['get'])
    def monthly_detail(self, request):
        """Per-household served/not-served detail for the current month (in scope)."""
        start, nxt = _month_bounds()
        scoped = scoped_household_qs(request.user).prefetch_related('caregiver')
        counts = {}
        last = {}
        for row in ServiceDelivery.objects.filter(
            household__in=scoped, service_date__gte=start, service_date__lt=nxt
        ).values('household_id').annotate(c=Count('id'), latest=Max('service_date')):
            counts[row['household_id']] = row['c']
            last[row['household_id']] = row['latest']
        # last-ever service date (for missed >30 days)
        ever = {}
        for row in ServiceDelivery.objects.filter(household__in=scoped).values(
            'household_id').annotate(latest=Max('service_date')):
            ever[row['household_id']] = row['latest']
        today = timezone.localdate()
        rows = []
        missed = []
        for hh in scoped:
            cg = getattr(hh, 'caregiver', None)
            cg_name = f'{cg.name} {cg.surname}'.strip() if cg else ''
            served = hh.id in counts
            last_ever = ever.get(hh.id)
            days = (today - last_ever).days if last_ever else None
            item = {
                'id': hh.id, 'org_household_number': hh.org_household_number,
                'caregiver_name': cg_name, 'served': served,
                'count': counts.get(hh.id, 0),
                'last_service_date': str(last.get(hh.id)) if last.get(hh.id) else (str(last_ever) if last_ever else None),
            }
            rows.append(item)
            if days is None or days >= 30:
                missed.append({
                    'id': hh.id, 'org_household_number': hh.org_household_number,
                    'caregiver_name': cg_name,
                    'last_service_date': str(last_ever) if last_ever else None,
                    'days_since': days,
                })
        rows.sort(key=lambda r: (r['served'], r['org_household_number']))
        return Response({'month': start.strftime('%Y-%m'), 'households': rows, 'missed': missed})


# ------------------------------ Users (for assignment dropdowns) ------------------------------
def users_list(request):
    users = User.objects.filter(is_active=True).order_by('username')
    names = settings.TRAINING_USERNAMES
    if is_training_user(request.user):
        users = users.filter(username__in=names)
    else:
        users = users.exclude(username__in=names)
    return Response(UserSerializer(users, many=True).data)


# ------------------------------ Dashboard ------------------------------
def dashboard(request):
    user = request.user
    role = user_role(user)
    qs = scoped_household_qs(user)

    q = request.query_params.get('q')
    search_results = None
    if q:
        results = household_text_search(qs, q).prefetch_related(
            'members', 'caregiver', 'assigned_to', 'checklist_items'
        )[:50]
        search_results = HouseholdListSerializer(results, many=True).data

    recent = qs.prefetch_related('members', 'caregiver', 'assigned_to', 'checklist_items').order_by('-id')[:10]
    recent_data = HouseholdListSerializer(recent, many=True).data

    stats = {'total_households': qs.count()}
    status_counts = {c[0]: 0 for c in choices.CASE_STATUS_CHOICES}
    for row in qs.values('status').annotate(n=Count('id')):
        status_counts[row['status']] = row['n']
    stats['by_status'] = status_counts
    stats['open_households'] = status_counts.get('open', 0)
    stats['total_people'] = (
        Caregiver.objects.filter(household__in=qs).count()
        + HouseholdMember.objects.filter(household__in=qs).count()
    )
    stats['document_count'] = SupportingDocument.objects.filter(
        # documents viewset scope is heavier; count files on households in this file set
        Q(content_type__model='household', object_id__in=qs.values('id'))
        | Q(content_type__model='caregiver', object_id__in=Caregiver.objects.filter(household__in=qs).values('id'))
        | Q(content_type__model='householdmember', object_id__in=HouseholdMember.objects.filter(household__in=qs).values('id'))
    ).count()
    today = timezone.localdate()
    stats['overdue_visits'] = PlannedVisit.objects.filter(
        household__in=qs, status='planned', visit_date__lt=today
    ).count()
    stats['open_referrals'] = Referral.objects.filter(household__in=qs).exclude(
        status__in=('completed', 'declined', 'no_show')
    ).count()

    completeness_bands = None
    if role in ('supervisor', 'admin'):
        banded = annotate_completeness(qs)
        ready = banded.filter(_pct__gte=90).count()
        in_progress = banded.filter(_pct__gte=50, _pct__lt=90).count()
        needs = banded.filter(_pct__lt=50).count()
        completeness_bands = {'ready': ready, 'in_progress': in_progress, 'needs_attention': needs}

    unconfirmed = {'id_number': 0, 'surname': 0, 'date_of_birth': 0}
    if role in ('supervisor', 'admin'):
        def _unc(field):
            if field == 'date_of_birth':
                cg = Caregiver.objects.filter(
                    household_id=OuterRef('pk'), date_of_birth__isnull=False, date_of_birth_confirmed=False
                )
                mem = HouseholdMember.objects.filter(
                    household_id=OuterRef('pk'), date_of_birth__isnull=False, date_of_birth_confirmed=False
                )
            else:
                cg = Caregiver.objects.filter(household_id=OuterRef('pk'), **{f'{field}_confirmed': False}).exclude(**{field: ''})
                mem = HouseholdMember.objects.filter(household_id=OuterRef('pk'), **{f'{field}_confirmed': False}).exclude(**{field: ''})
            return qs.filter(Exists(cg) | Exists(mem)).count()

        unconfirmed = {
            'id_number': _unc('id_number'),
            'surname': _unc('surname'),
            'date_of_birth': _unc('date_of_birth'),
        }

    return Response({
        'role': role,
        'recent': recent_data,
        'search_results': search_results,
        'stats': stats,
        'unconfirmed_counts': unconfirmed,
        'completeness_bands': completeness_bands,
    })


def choices_view(request):
    """Expose choice lists so the frontend dropdowns stay in sync."""
    return Response({
        'id_type': [c[0] for c in choices.ID_TYPE_CHOICES],
        'sex': [c[0] for c in choices.SEX_CHOICES],
        'race': [c[0] for c in choices.RACE_CHOICES],
        'marital_status': [c[0] for c in choices.MARITAL_STATUS_CHOICES],
        'headship_type': [c[0] for c in choices.HEADSHIP_TYPE_CHOICES],
        'category': [{'value': c[0], 'label': c[1]} for c in choices.CATEGORY_CHOICES],
        'has_evidence': ['Yes', 'No', ''],
        'problem_codes': [{'value': c[0], 'label': c[1]} for c in choices.PROBLEM_CODES],
        'intervention_codes': [{'value': c[0], 'label': c[1]} for c in choices.INTERVENTION_CODES],
        'risk_level': [{'value': c[0], 'label': c[1]} for c in choices.RISK_LEVEL_CHOICES],
        'service_types': [c[0] for c in choices.SERVICE_TYPE_CHOICES],
        'case_status': [{'value': c[0], 'label': c[1]} for c in choices.CASE_STATUS_CHOICES],
        'hiv_status': [{'value': c[0], 'label': c[1]} for c in choices.HIV_STATUS_CHOICES],
        'on_art': [{'value': c[0], 'label': c[1]} for c in choices.ON_ART_CHOICES],
        'grant_types': [{'value': c[0], 'label': c[1]} for c in choices.GRANT_TYPE_CHOICES],
        'consent_types': [{'value': c[0], 'label': c[1]} for c in choices.CONSENT_TYPE_CHOICES],
        'protection_types': [{'value': c[0], 'label': c[1]} for c in choices.PROTECTION_TYPE_CHOICES],
        'incident_status': [{'value': c[0], 'label': c[1]} for c in choices.INCIDENT_STATUS_CHOICES],
        'evaluation_recommendation': [{'value': c[0], 'label': c[1]} for c in choices.EVALUATION_RECOMMENDATION_CHOICES],
        'staff_roles': [
            {
                'value': r,
                'label': {
                    'cycw': 'CYCW',
                    'auxiliary': 'Auxiliary',
                    'caregiver': 'Caregiver',
                    'data-capturer': 'Data capturer',
                    'case-worker': 'Case worker (SSP)',
                    'supervisor': 'Supervisor (QA)',
                    'admin': 'Administrator',
                }.get(r, r),
                'permissions': ROLE_PERMISSION_TEXT.get(r, ''),
                'live_office': r in getattr(settings, 'LIVE_OFFICE_TITLES', []),
            }
            for r in settings.ALL_ROLES
        ],
        'partner_kinds': [{'value': c[0], 'label': c[1]} for c in choices.PARTNER_KIND_CHOICES],
        'referral_status': [{'value': c[0], 'label': c[1]} for c in choices.REFERRAL_STATUS_CHOICES],
        'referral_reasons': [{'value': c[0], 'label': c[1]} for c in choices.REFERRAL_REASON_CHOICES],
        'visit_types': [{'value': c[0], 'label': c[1]} for c in choices.VISIT_TYPE_CHOICES],
        'visit_status': [{'value': c[0], 'label': c[1]} for c in choices.VISIT_STATUS_CHOICES],
    })


class UsersListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request):
        return users_list(request)


class BrandingView(APIView):
    """Public org branding (name + logo + login tagline) for the login screen."""
    permission_classes = [AllowAny]

    def get(self, request):
        org = Organisation.get_solo()
        cfg = SiteConfig.get_solo()
        return Response({
            'name': org.name or 'Sebueng Itumeleng',
            'logo': org.logo.url if org.logo else '/emblem.jpg',
            'login_tagline': cfg.login_tagline or 'Re Emisa Sechaba',
        })


class SiteConfigView(APIView):
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request):
        return Response(SiteConfigSerializer(SiteConfig.get_solo()).data)

    def put(self, request):
        if user_role(request.user) != ROLE_ADMIN:
            return Response({'detail': 'Only administrators can edit site configuration.'},
                            status=status.HTTP_403_FORBIDDEN)
        cfg = SiteConfig.get_solo()
        serializer = SiteConfigSerializer(cfg, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_action(request.user, 'edited', 'Updated site configuration')
        return Response(serializer.data)


class ServiceTargetView(APIView):
    """Per-worker monthly service goals (supervisor/admin only)."""
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request):
        if user_role(request.user) not in (ROLE_ADMIN, 'supervisor'):
            return Response({'detail': 'Only supervisors/administrators may view service targets.'},
                            status=status.HTTP_403_FORBIDDEN)
        targets = {t.user_id: t.monthly_goal for t in ServiceTarget.objects.all()}
        workers = User.objects.filter(is_active=True, groups__name__in=FIELD_WORKER_ROLES).distinct().order_by('username')
        names = settings.TRAINING_USERNAMES
        if is_training_user(request.user):
            workers = workers.filter(username__in=names)
        else:
            workers = workers.exclude(username__in=names)
        return Response([{
            'user_id': w.id,
            'name': w.get_full_name() or w.username,
            'username': w.username,
            'monthly_goal': targets.get(w.id, 0),
        } for w in workers])

    def put(self, request):
        if user_role(request.user) not in (ROLE_ADMIN, 'supervisor'):
            return Response({'detail': 'Only supervisors/administrators may set service targets.'},
                            status=status.HTTP_403_FORBIDDEN)
        uid = request.data.get('user_id')
        try:
            goal = max(0, int(request.data.get('monthly_goal') or 0))
        except (TypeError, ValueError):
            return Response({'detail': 'monthly_goal must be a number.'}, status=400)
        if not User.objects.filter(pk=uid, groups__name__in=FIELD_WORKER_ROLES).exists():
            return Response({'detail': 'Targets can only be set for field workers (CYCW / Auxiliary).'}, status=404)
        ServiceTarget.objects.update_or_create(user_id=uid, defaults={'monthly_goal': goal})
        log_action(request.user, 'edited', f'Set monthly service target ({goal}) for user #{uid}')
        return Response({'user_id': uid, 'monthly_goal': goal})


class OrganisationView(APIView):
    permission_classes = [IsAuthenticated, IsStaffRole]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        return Response(OrganisationSerializer(Organisation.get_solo(), context={'request': request}).data)

    def put(self, request):
        if user_role(request.user) != ROLE_ADMIN:
            return Response({'detail': 'Only administrators can edit the organisation profile.'},
                            status=status.HTTP_403_FORBIDDEN)
        org = Organisation.get_solo()
        serializer = OrganisationSerializer(org, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_action(request.user, 'edited', 'Updated organisation profile')
        return Response(serializer.data)


class DashboardView(APIView):
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request):
        return dashboard(request)


class ChoicesView(APIView):
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request):
        return choices_view(request)


class IdCheckView(APIView):
    """Checksum / DOB from an SA ID, plus duplicate people already on file."""
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request):
        raw = request.query_params.get('q') or request.query_params.get('id_number') or ''
        parsed = parse_sa_id(raw)
        digits = parsed['digits']
        duplicates = []
        exclude_hh = request.query_params.get('exclude_household')
        exclude_cg = request.query_params.get('exclude_caregiver')
        exclude_mem = request.query_params.get('exclude_member')
        if len(digits) >= 6:
            hh_qs = scoped_household_qs(request.user)
            cg_qs = Caregiver.objects.filter(household__in=hh_qs, id_number_digits=digits)
            mem_qs = HouseholdMember.objects.filter(household__in=hh_qs, id_number_digits=digits)
            if exclude_hh and exclude_hh.isdigit():
                cg_qs = cg_qs.exclude(household_id=int(exclude_hh))
                mem_qs = mem_qs.exclude(household_id=int(exclude_hh))
            if exclude_cg and exclude_cg.isdigit():
                cg_qs = cg_qs.exclude(pk=int(exclude_cg))
            if exclude_mem and exclude_mem.isdigit():
                mem_qs = mem_qs.exclude(pk=int(exclude_mem))
            for p in cg_qs.select_related('household')[:10]:
                duplicates.append({
                    'role': 'caregiver',
                    'name': f'{p.name} {p.surname}'.strip(),
                    'id_number': p.id_number,
                    'household_id': p.household_id,
                    'org_household_number': p.household.org_household_number,
                })
            for p in mem_qs.select_related('household')[:10]:
                duplicates.append({
                    'role': 'member',
                    'name': f'{p.name} {p.surname}'.strip(),
                    'id_number': p.id_number,
                    'household_id': p.household_id,
                    'org_household_number': p.household.org_household_number,
                })
        parsed['duplicates'] = duplicates
        return Response(parsed)


class WorkDiaryView(APIView):
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request):
        hh = scoped_household_qs(request.user)
        today = timezone.localdate()
        horizon = today + timedelta(days=14)
        visits = PlannedVisit.objects.filter(household__in=hh).select_related(
            'household', 'household__caregiver', 'assigned_to'
        )
        overdue = visits.filter(status='planned', visit_date__lt=today).order_by('visit_date')
        upcoming = visits.filter(status='planned', visit_date__gte=today, visit_date__lte=horizon).order_by('visit_date')
        open_ref = Referral.objects.filter(household__in=hh).exclude(
            status__in=('completed', 'declined', 'no_show')
        ).select_related('household', 'household__caregiver', 'partner', 'member').order_by('follow_up_date', '-referred_on')
        overdue_ref = open_ref.filter(follow_up_date__isnull=False, follow_up_date__lt=today)
        return Response({
            'counts': {
                'overdue_visits': overdue.count(),
                'upcoming_visits': upcoming.count(),
                'open_referrals': open_ref.count(),
                'overdue_referrals': overdue_ref.count(),
            },
            'overdue_visits': PlannedVisitSerializer(overdue[:50], many=True).data,
            'upcoming_visits': PlannedVisitSerializer(upcoming[:50], many=True).data,
            'open_referrals': ReferralSerializer(open_ref[:50], many=True).data,
        })


class BackupListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        return Response({
            'engine': settings.DATABASES['default']['ENGINE'],
            'sqlite': settings.DATABASES['default']['ENGINE'].endswith('sqlite3'),
            'backups': list_backups(),
        })


class BackupCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        path = create_backup_zip()
        log_action(request.user, 'downloaded', f'Created office backup {path.name}')
        return FileResponse(open(path, 'rb'), as_attachment=True, filename=path.name)


class BackupDownloadView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, name):
        path = (backup_dir() / name).resolve()
        if path.parent != backup_dir().resolve() or not path.name.startswith('ovc-backup-') or path.suffix != '.zip':
            return Response({'detail': 'Invalid backup name.'}, status=400)
        if not path.exists():
            raise Http404
        log_action(request.user, 'downloaded', f'Downloaded office backup {path.name}')
        return FileResponse(open(path, 'rb'), as_attachment=True, filename=path.name)


class BackupRestoreView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': 'Choose a backup zip created by this office.'}, status=400)
        dest = backup_dir() / f'uploaded-{Path(upload.name).name}'
        with dest.open('wb') as out:
            for chunk in upload.chunks():
                out.write(chunk)
        try:
            restore_from_zip(dest)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=400)
        log_action(request.user, 'edited', f'Restored office file from {dest.name}')
        return Response({'detail': 'Office file restored. Refresh the page.'})
