"""API views enforcing server-side RBAC + audit logging."""
import csv

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Case, Count, F, FloatField, Max, Q, Value, When
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
from .models import (
    AuditLogEntry,
    Assessment,
    Caregiver,
    CaseFileChecklistItem,
    Household,
    HouseholdMember,
    Organisation,
    ProcessNote,
    SupportingDocument,
)
from .permissions import (
    IsAdminRole,
    IsStaffRole,
    ROLE_ADMIN,
    ROLE_CASE_WORKER,
    can_signoff_checklist,
    user_role,
)
from .serializers import (
    AssessmentSerializer,
    AuditLogSerializer,
    CaregiverSerializer,
    ChecklistItemSerializer,
    HouseholdDetailSerializer,
    HouseholdListSerializer,
    HouseholdSerializer,
    HouseholdMemberSerializer,
    OrganisationSerializer,
    ProcessNoteSerializer,
    SupportingDocumentSerializer,
    UserSerializer,
)

CONFIRM_FIELDS = ['surname', 'id_number', 'date_of_birth']


def scoped_household_qs(user):
    """Case-workers only see their assigned households."""
    qs = Household.objects.all()
    if user_role(user) == ROLE_CASE_WORKER:
        qs = qs.filter(assigned_to=user)
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


class MeView(APIView):
    def get(self, request):
        data = UserSerializer(request.user).data
        role = data.get('role')
        data['permissions'] = {
            'can_view_audit': role == 'admin',
            'can_signoff_checklist': role in ('admin', 'supervisor'),
            'can_edit_records': role in ('admin', 'supervisor', 'case-worker', 'data-capturer'),
            'can_edit_checklist_evidence': role in ('admin', 'supervisor'),
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

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        q = request.query_params.get('q') or request.query_params.get('search')
        if q:
            qs = qs.filter(
                Q(org_household_number__icontains=q)
                | Q(caregiver__surname__icontains=q)
                | Q(caregiver__id_number__icontains=q)
                | Q(caregiver__name__icontains=q)
                | Q(members__surname__icontains=q)
                | Q(members__id_number__icontains=q)
            ).distinct()
        unconfirmed = request.query_params.get('unconfirmed')
        if unconfirmed in ('id_number', 'surname', 'date_of_birth'):
            qs = filter_unconfirmed(qs, unconfirmed)
        if request.query_params.get('assigned_to_me'):
            qs = qs.filter(assigned_to=request.user)
        assigned_to = request.query_params.get('assigned_to')
        if assigned_to and assigned_to.isdigit():
            qs = qs.filter(assigned_to__id=assigned_to).distinct()
        if request.query_params.get('signed'):
            qs = qs.filter(checklist_signed_at__isnull=False)
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

    def perform_create(self, serializer):
        obj = serializer.save()
        _ensure_checklist(obj)
        log_action(self.request.user, 'created', f'Household #{obj.pk} ({obj.org_household_number})')

    def perform_update(self, serializer):
        obj = serializer.save()
        log_action(self.request.user, 'edited', f'Household #{obj.pk} ({obj.org_household_number})')

    def perform_destroy(self, instance):
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
        obj = serializer.save()
        log_action(self.request.user, 'created', self._desc(obj))

    def perform_update(self, serializer):
        obj = serializer.save()
        log_action(self.request.user, 'edited', self._desc(obj))

    def perform_destroy(self, instance):
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


class HouseholdMemberViewSet(_PersonViewSet):
    model = HouseholdMember
    serializer_class = HouseholdMemberSerializer
    label = 'Household member'


# ------------------------------ Supporting documents ------------------------------
class SupportingDocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsStaffRole]
    serializer_class = SupportingDocumentSerializer

    def get_queryset(self):
        from django.contrib.contenttypes.models import ContentType
        households = scoped_household_qs(self.request.user)
        allowed_household_ids = list(households.values_list('id', flat=True))
        cg_ids = list(Caregiver.objects.filter(household_id__in=allowed_household_ids).values_list('id', flat=True))
        mem_ids = list(HouseholdMember.objects.filter(household_id__in=allowed_household_ids).values_list('id', flat=True))
        ct_h = ContentType.objects.get_for_model(Household)
        ct_c = ContentType.objects.get_for_model(Caregiver)
        ct_m = ContentType.objects.get_for_model(HouseholdMember)
        qs = SupportingDocument.objects.filter(
            Q(content_type=ct_h, object_id__in=allowed_household_ids)
            | Q(content_type=ct_c, object_id__in=cg_ids)
            | Q(content_type=ct_m, object_id__in=mem_ids)
        )
        parent_type = self.request.query_params.get('parent_type')
        parent_id = self.request.query_params.get('parent_id')
        if parent_type and parent_id:
            ct_map = {'household': ct_h, 'caregiver': ct_c, 'householdmember': ct_m}
            if parent_type in ct_map:
                qs = qs.filter(content_type=ct_map[parent_type], object_id=parent_id)

        # All documents for a single household (household + its caregiver + members).
        household_id = self.request.query_params.get('household')
        if household_id and household_id.isdigit():
            hid = int(household_id)
            hh_cg_ids = list(Caregiver.objects.filter(household_id=hid).values_list('id', flat=True))
            hh_mem_ids = list(HouseholdMember.objects.filter(household_id=hid).values_list('id', flat=True))
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


# ------------------------------ Users (for assignment dropdowns) ------------------------------
def users_list(request):
    users = User.objects.filter(is_active=True).order_by('username')
    return Response(UserSerializer(users, many=True).data)


# ------------------------------ Dashboard ------------------------------
def dashboard(request):
    user = request.user
    role = user_role(user)
    qs = scoped_household_qs(user).prefetch_related('members', 'caregiver')

    q = request.query_params.get('q')
    search_results = None
    if q:
        results = qs.filter(
            Q(org_household_number__icontains=q)
            | Q(caregiver__surname__icontains=q)
            | Q(caregiver__id_number__icontains=q)
            | Q(caregiver__name__icontains=q)
            | Q(members__surname__icontains=q)
            | Q(members__id_number__icontains=q)
        ).distinct()[:50]
        search_results = HouseholdListSerializer(results, many=True).data

    recent = qs.order_by('-id')[:10]
    recent_data = HouseholdListSerializer(recent, many=True).data

    stats = {'total_households': qs.count()}

    # Unconfirmed field counts (visible to supervisors/admin).
    unconfirmed = {'id_number': 0, 'surname': 0, 'date_of_birth': 0}
    if role in ('supervisor', 'admin'):
        for hh in qs:
            people = ([hh.caregiver] if hasattr(hh, 'caregiver') and hh.caregiver else []) + list(hh.members.all())
            flags = {'id_number': False, 'surname': False, 'date_of_birth': False}
            for p in people:
                for f in ['surname', 'id_number', 'date_of_birth']:
                    val = getattr(p, f)
                    has_val = (val.strip() != '') if isinstance(val, str) else (val is not None)
                    if has_val and not getattr(p, f'{f}_confirmed'):
                        flags[f] = True
            for f in flags:
                if flags[f]:
                    unconfirmed[f] += 1

    return Response({
        'role': role,
        'recent': recent_data,
        'search_results': search_results,
        'stats': stats,
        'unconfirmed_counts': unconfirmed,
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
    })


class UsersListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request):
        return users_list(request)


class BrandingView(APIView):
    """Public org branding (name + logo) for the login screen."""
    permission_classes = [AllowAny]

    def get(self, request):
        org = Organisation.get_solo()
        return Response({'name': org.name, 'logo': org.logo.url if org.logo else None})


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
