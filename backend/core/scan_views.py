"""Scan Intake: OCR a photographed DSD file, then confirm before any household write."""
from io import BytesIO
from typing import NamedTuple

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
from .form_io import apply_buckets, needs_staff_confirmation
from .official_blanks import ATLAS_VERSION
from .sa_id import id_digits
from .scan_ocr import (
    engine_status,
    job_has_pending_handwrite,
    ocr_available,
    process_upload,
    start_handwrite_job,
)
from .scan_handwrite_engines import cancel_handwrite_session
from .scan_templates import CHECKLIST_FOR_FORM, extract_fields, form_choices, form_label
from .serializers import CaregiverSerializer, HouseholdMemberSerializer, HouseholdSerializer
from .views import _ensure_checklist, duplicate_id_matches, scoped_household_qs


def _deny_edit(user):
    from rest_framework.exceptions import PermissionDenied
    if user_role(user) == ROLE_CAREGIVER or not can_edit_records(user):
        raise PermissionDenied('Your login cannot add or change household files from a scan.')


# Which person each kind of sheet describes. Sheets sharing a subject are the
# same person's page-set and may be merged (C01 page 1 + page 2, C01 + CW 05,
# C01 + C02 for the same adult). A C03 child sheet is a different person.
# C03 identity is assembled onto a member slot at save, never onto caregiver.*.
PERSON_SUBJECT_BY_FORM = {
    'c01': 'adult',
    'intake': 'adult',
    'c02': 'adult',
    'family_care_plan': 'adult',
    'c03': 'child',
}
# The subject whose identity fields own the caregiver record, best first.
SUBJECT_PRIORITY = ('adult', 'child')

# Identity fields on C03 that describe the child beneficiary.
C03_IDENTITY_FIELDS = {
    'name', 'surname', 'known_as', 'id_number', 'date_of_birth',
    'nationality', 'sex', 'id_type',
}


class ResolvedScan(NamedTuple):
    """What one scan job wants to write, after grouping pages by person."""

    values: dict          # target -> value, ready for apply_buckets
    confirmed: set        # targets a staff member explicitly signed off
    labels: dict          # target -> human label, for messages
    conflicts: list       # same person, same field, two different readings
    held_back: list       # another person's identity values, not written
    child_identities: list  # C03 children, slotted onto member.N at save
    needs_review: list    # pre-Phase-6 caregiver.* data that must not be moved


def _person_subject(page):
    """Which person this sheet is about. Unidentified sheets stand alone."""
    return PERSON_SUBJECT_BY_FORM.get(page.form_type) or f'sheet-{page.pk}'


def _is_person_target(target):
    return target.startswith('caregiver.') or target.startswith('member.')


def _c03_identity_field(target):
    """If this C03 target is the child's identity, return the field name."""
    parts = (target or '').split('.')
    if len(parts) == 2 and parts[0] == 'caregiver' and parts[1] in C03_IDENTITY_FIELDS:
        return parts[1]
    if len(parts) == 3 and parts[0] == 'member' and parts[1].isdigit() and parts[2] in C03_IDENTITY_FIELDS:
        return parts[2]
    return ''


def resolve_buckets(pages, household=None):
    """Group the values read off each photo by the person that photo is about.

    Household-level values (address, reference numbers, notes) merge across
    every sheet. Adult identity (caregiver.*, and member.N.* from C01) merge
    only inside the adult subject. C03 child identity is collected separately
    and written onto a member slot at save, so a lone C03 cannot create a
    caregiver row.
    """
    shared = {}
    subjects = {}
    order = []
    conflicts = []
    child_pages = []

    def record(store, target, field, page):
        value = (field.get('value') or '').strip()
        label = field.get('label') or target
        entry = store.get(target)
        if entry is None:
            store[target] = {
                'value': value,
                'label': label,
                'confirmed': bool(field.get('confirmed')),
                'page_id': page.pk,
                'page_index': page.index,
                'form_label': form_label(page.form_type),
            }
            return
        if entry['value'] == value or entry['page_id'] == page.pk:
            entry['confirmed'] = entry['confirmed'] or bool(field.get('confirmed'))
            return
        conflicts.append({
            'target': target,
            'label': entry['label'],
            'values': [
                {
                    'value': entry['value'],
                    'page_index': entry['page_index'],
                    'form_label': entry['form_label'],
                },
                {
                    'value': value,
                    'page_index': page.index,
                    'form_label': form_label(page.form_type),
                },
            ],
        })

    for page in pages:
        subject = _person_subject(page)
        if page.form_type == 'c03':
            child_pages.append(page)
        for field in page.fields or []:
            target = (field.get('target') or '').strip()
            if not target or not (field.get('value') or '').strip():
                continue
            if page.form_type == 'c03' and _c03_identity_field(target):
                continue
            if _is_person_target(target):
                if subject not in subjects:
                    subjects[subject] = {}
                    order.append(subject)
                record(subjects[subject], target, field, page)
            else:
                record(shared, target, field, page)

    primary = next((s for s in SUBJECT_PRIORITY if s in subjects), None)
    if primary is None and order:
        primary = order[0]

    values = {t: e['value'] for t, e in shared.items()}
    labels = {t: e['label'] for t, e in shared.items()}
    confirmed = {t for t, e in shared.items() if e['confirmed']}
    for target, entry in (subjects.get(primary) or {}).items():
        values[target] = entry['value']
        labels[target] = entry['label']
        if entry['confirmed']:
            confirmed.add(target)

    held_back = []
    for subject in order:
        if subject == primary:
            continue
        for target, entry in sorted(subjects[subject].items()):
            held_back.append({
                'target': target,
                'label': entry['label'],
                'value': entry['value'],
                'form_label': entry['form_label'],
                'page_index': entry['page_index'],
            })

    child_identities = _collect_c03_children(child_pages)
    needs_review = []
    _bind_c03_children(values, confirmed, labels, conflicts, child_identities, household, needs_review)

    _drop_unreadable_ids(values, confirmed)
    return ResolvedScan(values, confirmed, labels, conflicts, held_back, child_identities, needs_review)


def _collect_c03_children(pages):
    """One child identity per C03 sheet, from member.N.* or legacy caregiver.*."""
    children = []
    for page in pages:
        fields = {}
        confirmed = set()
        labels = {}
        legacy = False
        for field in page.fields or []:
            target = (field.get('target') or '').strip()
            value = (field.get('value') or '').strip()
            name = _c03_identity_field(target)
            if not name or not value:
                continue
            if target.startswith('caregiver.'):
                legacy = True
            if name in fields and fields[name] != value:
                # Two readings on the same sheet; keep the first, staff can edit.
                continue
            fields[name] = value
            labels[name] = field.get('label') or name
            if field.get('confirmed'):
                confirmed.add(name)
        if not fields:
            continue
        children.append({
            'fields': fields,
            'confirmed': confirmed,
            'labels': labels,
            'legacy_caregiver_targets': legacy,
            'page_index': page.index,
            'form_label': form_label(page.form_type),
        })
    return children


def _bind_c03_children(values, confirmed, labels, conflicts, children, household, needs_review):
    """Put each C03 child onto a member slot, or flag a pre-Phase-6 caregiver hit."""

    existing_members = []
    caregiver = None
    if household is not None:
        existing_members = list(household.members.order_by('id'))
        caregiver = getattr(household, 'caregiver', None)

    def used_slots():
        slots = {i for i in range(len(existing_members))}
        for key in values:
            parts = key.split('.')
            if parts[0] == 'member' and len(parts) >= 2 and parts[1].isdigit():
                slots.add(int(parts[1]))
        return slots

    def id_on_job_member(digits):
        for key, value in values.items():
            parts = key.split('.')
            if (
                parts[0] == 'member' and len(parts) == 3 and parts[1].isdigit()
                and parts[2] == 'id_number' and id_digits(value) == digits
            ):
                return int(parts[1])
        return None

    for child in children:
        fields = child['fields']
        digits = id_digits(fields.get('id_number') or '')
        cg_digits = id_digits(getattr(caregiver, 'id_number', '') or '') if caregiver else ''
        cg_name = (
            f'{(caregiver.name or "").strip()} {(caregiver.surname or "").strip()}'.lower()
            if caregiver else ''
        )
        child_name = f'{fields.get("name", "").strip()} {fields.get("surname", "").strip()}'.lower()

        if caregiver and digits and cg_digits and digits == cg_digits:
            needs_review.append({
                'reason': 'legacy_c03_on_caregiver',
                'detail': (
                    'This C03 identity is already on the caregiver record from a '
                    'scan before Phase 6. It was not moved onto a member and the '
                    'caregiver row was not changed.'
                ),
                'page_index': child['page_index'],
                'id_number': fields.get('id_number'),
                'name': fields.get('name'),
                'surname': fields.get('surname'),
            })
            continue
        if caregiver and child_name.strip() and child_name == cg_name:
            needs_review.append({
                'reason': 'legacy_c03_on_caregiver',
                'detail': (
                    'This C03 name already sits on the caregiver record from a '
                    'scan before Phase 6. It was not moved onto a member and the '
                    'caregiver row was not changed.'
                ),
                'page_index': child['page_index'],
                'name': fields.get('name'),
                'surname': fields.get('surname'),
            })
            continue

        slot = None
        if digits:
            for index, member in enumerate(existing_members):
                if id_digits(member.id_number or '') == digits:
                    slot = index
                    break
            if slot is None:
                slot = id_on_job_member(digits)
        if slot is None:
            taken = used_slots()
            slot = 0
            while slot in taken:
                slot += 1

        for name, value in fields.items():
            target = f'member.{slot}.{name}'
            if target in values and values[target] != value:
                conflicts.append({
                    'target': target,
                    'label': child['labels'].get(name, name),
                    'values': [
                        {'value': values[target], 'page_index': None, 'form_label': 'Already on file'},
                        {
                            'value': value,
                            'page_index': child['page_index'],
                            'form_label': child['form_label'],
                        },
                    ],
                })
                continue
            values[target] = value
            labels[target] = child['labels'].get(name, name)
            if name in child['confirmed']:
                confirmed.add(target)
        if child.get('legacy_caregiver_targets'):
            needs_review.append({
                'reason': 'c03_targets_rewritten',
                'detail': (
                    'This C03 sheet still had caregiver.* field names from before '
                    'Phase 6. They were written to a household member, not the '
                    'caregiver.'
                ),
                'page_index': child['page_index'],
                'member_slot': slot,
            })


def _drop_unreadable_ids(values, confirmed):
    """A part-read SA ID is not a short ID, so it must not reach the file.

    The OCR sanitiser already refuses partial digit strings, but page fields
    come back through the request body on save, so the rule is enforced again
    here. A number under a Passport or Permit tick is left alone - only an SA
    ID has to be 13 digits.
    """
    for target in [t for t in values if t.endswith('id_number')]:
        prefix = target.rsplit('.', 1)[0]
        id_type = (values.get(f'{prefix}.id_type') or 'SA ID Number').strip()
        if id_type and id_type != 'SA ID Number':
            continue
        if id_digits(values[target]):
            continue
        values.pop(target)
        confirmed.discard(target)


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
    pending_handwrite = job_has_pending_handwrite(job)
    return {
        'id': job.id,
        'status': job.status,
        'household': job.household_id,
        'ocr_engine': job.ocr_engine,
        'ocr_available': ocr_available(),
        'engine': engine_status(),
        'handwriting_warning': job.handwriting_warning,
        'handwrite_pending': pending_handwrite,
        'handwrite_session_id': str(job.id),
        'form_types': form_choices(),
        'forms_found': [{'value': code, 'label': form_label(code)} for code in found],
        'pages': pages,
        'created_at': job.created_at,
    }


def _truthy(value):
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _scanned_id_duplicates(user, resolved, household):
    """ID numbers on this scan that already belong to somebody on another file.

    Manual entry warns about this while the number is being typed (IdCheckHint);
    a scan has nobody typing, so the same warning is raised here, before
    anything is written. Same query, so live and TEST- files stay apart.
    """
    wanted = {}
    for target in sorted(resolved.values):
        if not target.endswith('id_number') or target not in resolved.confirmed:
            continue
        digits = id_digits(resolved.values[target])
        if digits:
            wanted.setdefault(digits, []).append(target)

    out = []
    for digits, targets in wanted.items():
        matches = duplicate_id_matches(
            user, digits, exclude_household=household.pk if household else None,
        )
        for target in targets:
            # One number read onto two people in the same scan is the same
            # question, and no household query would catch it.
            others = [t for t in targets if t != target]
            if not matches and not others:
                continue
            out.append({
                'target': target,
                'label': resolved.labels.get(target, target),
                'id_number': digits,
                'matches': matches,
                'same_scan': [resolved.labels.get(t, t) for t in others],
            })
    return out


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
            pages, _ = process_upload(uploaded, defer_handwrite=True)
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
        # Handwriting OCR continues in a background worker so this response is
        # not held open while TrOCR/LightOnOCR run. The UI polls for progress.
        if job_has_pending_handwrite(job):
            start_handwrite_job(job.id, session_id=str(job.id))
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
    def cancel_handwrite(self, request, pk=None):
        """Stop in-flight handwriting OCR for this scan (window closed / new scan)."""
        _deny_edit(request.user)
        job = ScanIntakeJob.objects.filter(pk=pk, created_by=request.user).first()
        if not job:
            return Response({'detail': 'Scan not found.'}, status=404)
        cancel_handwrite_session(str(job.id))
        # Mark any still-queued fields so the UI clears spinners.
        for page in job.pages.all():
            fields = list(page.fields or [])
            changed = False
            for field in fields:
                if field.get('kind') == 'handwrite' and field.get('ocr_status') in ('queued', 'running'):
                    field['ocr_status'] = 'cancelled'
                    changed = True
            if changed:
                page.fields = fields
                page.save(update_fields=['fields'])
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

        resolved = resolve_buckets(job.pages.all(), household=job.household)

        if resolved.conflicts:
            return Response({
                'detail': 'Two photos read different values for the same field. '
                          'Fix one of them, then save.',
                'conflicts': resolved.conflicts,
            }, status=400)

        unconfirmed = [
            resolved.labels.get(target, target)
            for target in sorted(resolved.values)
            if needs_staff_confirmation(target) and target not in resolved.confirmed
        ]
        if unconfirmed:
            return Response({
                'detail': 'Confirm the highlighted surname, ID and date of birth before saving.',
                'unconfirmed': unconfirmed,
            }, status=400)

        duplicates = _scanned_id_duplicates(request.user, resolved, job.household)
        if duplicates and not _truthy(request.data.get('accept_duplicates')):
            on_file = any(d['matches'] for d in duplicates)
            return Response({
                'detail': (
                    'One of the ID numbers on this scan is already on another file. '
                    'Check whether this is the same person before saving.'
                    if on_file else
                    'The same ID number was read onto two different people on this scan. '
                    'Correct the wrong one before saving.'
                ),
                'duplicates': duplicates,
            }, status=400)

        with transaction.atomic():
            household = self._write_buckets(request, job, resolved)
            job.household = household
            job.status = 'confirmed'
            job.confirmed_at = timezone.now()
            job.save(update_fields=['household', 'status', 'confirmed_at'])
            self._attach_pages(request.user, job, household)
            self._tick_checklist(request.user, job, household)

        note = f'Scan intake #{job.pk} into Household #{household.pk}'
        if resolved.held_back:
            note += f' ({len(resolved.held_back)} value(s) from another person left for typing)'
        log_action(request.user, 'confirmed', note)
        payload = {
            'id': job.id,
            'status': job.status,
            'household': household.id,
            'org_household_number': household.org_household_number,
        }
        if resolved.held_back:
            payload['held_back'] = resolved.held_back
            payload['detail'] = (
                f'Saved. {len(resolved.held_back)} value(s) came off a sheet about a different '
                'person and were not written to this file — open the household and type them '
                'onto the right person.'
            )
        if resolved.needs_review:
            payload['needs_review'] = resolved.needs_review
            extra = (
                f'{len(resolved.needs_review)} value(s) from a C03 sheet need a person to '
                'check — they were not silently moved off the caregiver record.'
            )
            payload['detail'] = f"{payload['detail']} {extra}".strip() if payload.get('detail') else extra
        return Response(payload)

    def _write_buckets(self, request, job, resolved):
        buckets = resolved.values
        household = job.household
        if household and not scoped_household_qs(request.user).filter(pk=household.pk).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('That household is not on your caseload.')
        household = apply_buckets(
            request, household, buckets, confirmed_targets=resolved.confirmed,
        )

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

    def _attach_pages(self, user, job, household):
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Household)
        for page in job.pages.all():
            if not page.image:
                continue
            pair = CHECKLIST_FOR_FORM.get(page.form_type)
            category = pair[0] if pair else 'intake_form'
            sub_item = pair[1] if pair else ''
            SupportingDocument.objects.create(
                content_type=ct,
                object_id=household.pk,
                parent_kind='household',
                category=category,
                sub_item=sub_item,
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

