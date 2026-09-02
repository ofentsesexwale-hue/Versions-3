"""Scan Intake: OCR a photographed DSD file, then confirm before any household write."""
from io import BytesIO

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .audit import log_action
from .models import (
    Assessment,
    Caregiver,
    CaseFileChecklistItem,
    FamilyCarePlan,
    Household,
    HouseholdMember,
    ProcessNote,
    ScanIntakeJob,
    ScanIntakePage,
    SupportingDocument,
)
from .permissions import (
    IsStaffRole,
    ROLE_CAREGIVER,
    can_edit_records,
    is_field_worker,
    is_training_user,
    user_role,
)
from .form_io import apply_buckets
from .official_blanks import ATLAS_VERSION
from .scan_ocr import engine_status, ocr_available, process_upload
from .scan_templates import CHECKLIST_FOR_FORM, extract_fields, form_choices, form_label
from .serializers import CaregiverSerializer, HouseholdMemberSerializer, HouseholdSerializer
from .views import _ensure_checklist, scoped_household_qs


def _deny_edit(user):
    from rest_framework.exceptions import PermissionDenied
    if user_role(user) == ROLE_CAREGIVER or not can_edit_records(user):
        raise PermissionDenied('Your login cannot add or change household files from a scan.')


def _page_payload(page, request):
    image_url = f'/api/scan-intake/{page.job_id}/pages/{page.id}/image/'
    warped_url = ''
    if page.warped_image:
        warped_url = f'/api/scan-intake/{page.job_id}/pages/{page.id}/image/?which=warped'
    return {
        'id': page.id,
        'index': page.index,
        'image_url': image_url if page.image else '',
        'warped_url': warped_url,
        'original_name': page.original_name,
        'form_type': page.form_type,
        'form_page': page.form_page,
        'form_label': form_label(page.form_type),
        'form_confidence': page.form_confidence,
        'ocr_text': page.ocr_text,
        'ocr_confidence': page.ocr_confidence,
        'fields': page.fields or [],
        'alignment_failed': page.alignment_failed,
        'geometry_missing': page.geometry_missing,
        'template_version': page.template_version,
    }


def _job_payload(job, request):
    pages = [_page_payload(p, request) for p in job.pages.all()]
    found = []
    for page in pages:
        code = page.get('form_type')
        if code and code != 'unknown' and code not in found:
            found.append(code)
    return {
        'id': job.id,
        'status': job.status,
        'household': job.household_id,
        'ocr_engine': job.ocr_engine,
        'ocr_available': ocr_available(),
        'engine': engine_status(),
        'handwriting_warning': job.handwriting_warning,
        'form_types': form_choices(),
        'forms_found': [{'value': code, 'label': form_label(code)} for code in found],
        'pages': pages,
        'created_at': job.created_at,
    }


class ScanIntakeViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsStaffRole]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def list(self, request):
        _deny_edit(request.user)
        jobs = ScanIntakeJob.objects.filter(created_by=request.user, status='pending')[:20]
        return Response([_job_payload(j, request) for j in jobs])

    @action(detail=False, methods=['get'])
    def engine(self, request):
        return Response(engine_status())

    def retrieve(self, request, pk=None):
        _deny_edit(request.user)
        job = ScanIntakeJob.objects.filter(pk=pk, created_by=request.user).first()
        if not job:
            return Response({'detail': 'Scan not found.'}, status=404)
        return Response(_job_payload(job, request))

    def create(self, request):
        _deny_edit(request.user)
        files = request.FILES.getlist('files') or request.FILES.getlist('file')
        if not files:
            one = request.FILES.get('file')
            files = [one] if one else []
        if not files:
            return Response({'detail': 'Photograph every page in the physical file with your phone and upload the pictures here.'}, status=400)

        household = None
        hid = request.data.get('household') or request.data.get('household_id')
        if hid:
            household = scoped_household_qs(request.user).filter(pk=hid).first()
            if not household:
                return Response({'detail': 'That household is not on your caseload.'}, status=404)

        job = ScanIntakeJob.objects.create(
            created_by=request.user,
            household=household,
            ocr_engine='tesseract' if ocr_available() else 'pdf-text',
            handwriting_warning=True,
        )
        index = 0
        engines = set()
        for uploaded in files:
            pages, _ = process_upload(uploaded)
            if not pages:
                continue
            for rendered in pages:
                page = ScanIntakePage(
                    job=job,
                    index=index,
                    original_name=getattr(uploaded, 'name', '') or '',
                    form_type=rendered['form_type'],
                    form_page=int(rendered.get('form_page') or 0),
                    form_confidence=rendered['form_confidence'],
                    ocr_text=rendered['ocr_text'],
                    ocr_confidence=rendered['ocr_confidence'],
                    fields=rendered['fields'],
                    alignment_failed=bool(rendered.get('alignment_failed')),
                    geometry_missing=bool(rendered.get('geometry_missing')),
                    template_version=rendered.get('atlas_version') or ATLAS_VERSION,
                )
                page.save()
                image = rendered.get('image')
                if image is not None:
                    buf = BytesIO()
                    image.convert('RGB').save(buf, format='JPEG', quality=78)
                    page.image.save(f'page-{index}.jpg', ContentFile(buf.getvalue()), save=True)
                warped = rendered.get('warped')
                if warped is not None:
                    buf = BytesIO()
                    warped.convert('RGB').save(buf, format='JPEG', quality=78)
                    page.warped_image.save(f'page-{index}-aligned.jpg', ContentFile(buf.getvalue()), save=True)
                engines.add(rendered.get('ocr_engine') or '')
                index += 1
        if index == 0:
            job.delete()
            return Response({'detail': 'Could not read any pages from that file.'}, status=400)
        job.ocr_engine = ','.join(sorted(e for e in engines if e))[:32]
        job.save(update_fields=['ocr_engine'])
        log_action(request.user, 'created', f'Scan intake #{job.pk} ({index} pages)')
        return Response(_job_payload(job, request), status=201)

    def partial_update(self, request, pk=None):
        _deny_edit(request.user)
        job = ScanIntakeJob.objects.filter(pk=pk, created_by=request.user).first()
        if not job:
            return Response({'detail': 'Scan not found.'}, status=404)
        if job.status != 'pending':
            return Response({'detail': 'This scan has already been confirmed.'}, status=400)
        pages_data = request.data.get('pages')
        if isinstance(pages_data, list):
            by_id = {p.id: p for p in job.pages.all()}
            for item in pages_data:
                page = by_id.get(item.get('id'))
                if not page:
                    continue
                if item.get('form_type') and item['form_type'] != page.form_type:
                    page.form_type = item['form_type']
                    page.fields = extract_fields(page.form_type, page.ocr_text, page.ocr_confidence or 0.55)
                if 'fields' in item:
                    page.fields = item['fields']
                page.save()
        hid = request.data.get('household')
        if hid:
            household = scoped_household_qs(request.user).filter(pk=hid).first()
            if not household:
                return Response({'detail': 'That household is not on your caseload.'}, status=404)
            job.household = household
            job.save(update_fields=['household'])
        return Response(_job_payload(job, request))

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        _deny_edit(request.user)
        job = ScanIntakeJob.objects.filter(pk=pk, created_by=request.user).first()
        if not job:
            return Response({'detail': 'Scan not found.'}, status=404)
        if job.status != 'pending':
            return Response({'detail': 'This scan has already been confirmed.'}, status=400)

        # Apply latest field edits from the request body if sent.
        pages_data = request.data.get('pages')
        if isinstance(pages_data, list):
            by_id = {p.id: p for p in job.pages.all()}
            for item in pages_data:
                page = by_id.get(item.get('id'))
                if not page:
                    continue
                if item.get('form_type'):
                    page.form_type = item['form_type']
                if 'fields' in item:
                    page.fields = item['fields']
                page.save()

        buckets = {}
        unconfirmed = []
        for page in job.pages.all():
            for field in page.fields or []:
                value = (field.get('value') or '').strip()
                target = field.get('target') or ''
                if not value or not target:
                    continue
                if target in (
                    'caregiver.surname', 'caregiver.id_number', 'caregiver.date_of_birth',
                    'member.surname', 'member.id_number', 'member.date_of_birth',
                ) and not field.get('confirmed'):
                    unconfirmed.append(field.get('label') or target)
                buckets[target] = value
        if unconfirmed:
            return Response({
                'detail': 'Confirm the highlighted surname, ID and date of birth before saving.',
                'unconfirmed': unconfirmed,
            }, status=400)

        with transaction.atomic():
            household = self._write_buckets(request, job, buckets)
            job.household = household
            job.status = 'confirmed'
            job.confirmed_at = timezone.now()
            job.save(update_fields=['household', 'status', 'confirmed_at'])
            self._attach_pages(request.user, job, household)
            self._tick_checklist(request.user, job, household)

        log_action(request.user, 'confirmed', f'Scan intake #{job.pk} into Household #{household.pk}')
        return Response({
            'id': job.id,
            'status': job.status,
            'household': household.id,
            'org_household_number': household.org_household_number,
        })

    def _write_buckets(self, request, job, buckets):
        household = job.household
        if household and not scoped_household_qs(request.user).filter(pk=household.pk).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('That household is not on your caseload.')
        household = apply_buckets(request, household, buckets)

        pn = {k.split('.', 1)[1]: v for k, v in buckets.items() if k.startswith('process_note.')}
        if pn:
            ProcessNote.objects.create(household=household, created_by=request.user, **{
                k: v for k, v in pn.items() if k in {
                    'client_surname', 'client_first_name', 'client_id_number', 'file_no',
                    'person_engaged_name', 'person_engaged_contact', 'problem_code',
                    'intervention_code', 'type_of_engagement', 'purpose_and_what_transpired',
                    'outcome_and_follow_up', 'evaluation_reflection', 'ssp_name',
                }
            })

        cp = {k.split('.', 1)[1]: v for k, v in buckets.items() if k.startswith('care_plan.')}
        if cp:
            FamilyCarePlan.objects.create(
                household=household, created_by=request.user,
                overall_goal=cp.get('overall_goal') or '',
                ssp_name=cp.get('ssp_name') or '',
            )

        ass = {k.split('.', 1)[1]: v for k, v in buckets.items() if k.startswith('assessment.')}
        if ass:
            Assessment.objects.create(
                household=household, created_by=request.user,
                overview_situation=ass.get('overview_situation') or '',
                problem_codes=ass.get('problem_codes') or '',
                overall_goal=ass.get('overall_goal') or '',
            )
        return household
        if pn:
            ProcessNote.objects.create(household=household, created_by=request.user, **{
                k: v for k, v in pn.items() if k in {
                    'client_surname', 'client_first_name', 'client_id_number', 'file_no',
                    'person_engaged_name', 'person_engaged_contact', 'problem_code',
                    'intervention_code', 'type_of_engagement', 'purpose_and_what_transpired',
                    'outcome_and_follow_up', 'evaluation_reflection', 'ssp_name',
                }
            })

        cp = {k.split('.', 1)[1]: v for k, v in buckets.items() if k.startswith('care_plan.')}
        if cp:
            FamilyCarePlan.objects.create(
                household=household, created_by=request.user,
                overall_goal=cp.get('overall_goal') or '',
                ssp_name=cp.get('ssp_name') or '',
            )

        ass = {k.split('.', 1)[1]: v for k, v in buckets.items() if k.startswith('assessment.')}
        if ass:
            Assessment.objects.create(
                household=household, created_by=request.user,
                overview_situation=ass.get('overview_situation') or '',
                problem_codes=ass.get('problem_codes') or '',
                overall_goal=ass.get('overall_goal') or '',
            )
        return household

    def _attach_pages(self, user, job, household):
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Household)
        for page in job.pages.all():
            if not page.image:
                continue
            pair = CHECKLIST_FOR_FORM.get(page.form_type)
            category = pair[0] if pair else 'intake_form'
            SupportingDocument.objects.create(
                content_type=ct,
                object_id=household.pk,
                parent_kind='household',
                category=category,
                file=page.image,
                label=f'Scan · {form_label(page.form_type)} · page {page.index + 1}',
                attached_name=household.org_household_number,
                uploaded_by=user,
            )

    def _tick_checklist(self, user, job, household):
        seen = set()
        now = timezone.now()
        for page in job.pages.all():
            pair = CHECKLIST_FOR_FORM.get(page.form_type)
            if not pair or pair in seen:
                continue
            seen.add(pair)
            item = household.checklist_items.filter(category=pair[0], sub_item=pair[1]).first()
            if not item:
                continue
            item.has_evidence = 'Yes'
            item.checked_by = user
            item.checked_at = now
            item.save(update_fields=['has_evidence', 'checked_by', 'checked_at'])


def scan_page_image(request, job_id, page_id):
    """Pending scans are not public media. Only the staff who uploaded them."""
    from django.http import FileResponse, HttpResponse
    user = request.user if getattr(request.user, 'is_authenticated', False) else None
    if not user or not user.is_authenticated:
        from .print_views import _auth_user
        user = _auth_user(request)
    if not user:
        return HttpResponse('Authentication required.', status=401)
    _deny_edit(user)
    job = ScanIntakeJob.objects.filter(pk=job_id, created_by=user).first()
    if not job:
        return HttpResponse('Scan not found.', status=404)
    page = job.pages.filter(pk=page_id).first()
    if not page:
        return HttpResponse('Page not found.', status=404)
    which = request.GET.get('which') or 'image'
    fh = page.warped_image if which == 'warped' and page.warped_image else page.image
    if not fh:
        return HttpResponse('No image.', status=404)
    return FileResponse(fh.open('rb'), content_type='image/jpeg')

