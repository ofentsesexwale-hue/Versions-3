"""Server-rendered print/export views that replicate official DSD form layouts.

Fully offline: no external calls. Output is print-optimised HTML that the browser
prints (or 'saves as PDF'). Authentication accepts a DRF token via the
Authorization header OR a `token` query param (so links open in a new tab).
"""
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from rest_framework.authtoken.models import Token

from . import choices
from .audit import log_action
from .models import Organisation
from .serializers import checklist_progress
from .views import scoped_household_qs

CAT_LABELS = dict(choices.CATEGORY_CHOICES)


def _age(dob, ref):
    if not dob:
        return ''
    return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))

# form key -> (template, human title)
FORMS = {
    'checklist': ('print/checklist.html', 'Case File Checklist (NPO)'),
    'intake': ('print/intake.html', 'CW 05 Intake Form'),
    'reporter': ('print/reporter.html', 'CW 02 Reporter Form'),
    'assessment': ('print/assessment.html', 'CW 09 Assessment, Planning & Contracting'),
    'family_care_plan': ('print/family_care_plan.html', 'Family Care Plan'),
    'educational': ('print/educational.html', 'Educational Progress Record'),
    'referral': ('print/referral.html', 'CW 04B External Referral Form'),
    'process_note': ('print/process_note.html', 'CW 11 Case Work Process Note'),
    'cow2_note': ('print/cow2_note.html', 'COW 2 Community Work Process Note'),
    'termination': ('print/termination.html', 'CW 13 Termination Report'),
    'site_visit': ('print/site_visit.html', 'Site Visit Form'),
    'exit': ('print/exit.html', 'Family Exit Form'),
    'success_story': ('print/success_story.html', 'Success Story'),
    'monthly_report': ('print/monthly_report.html', 'C06 Monthly Household Services Report'),
    'hiv_risk': ('print/hiv_risk.html', 'HIV Risk Assessment Form'),
    'full': ('print/full.html', 'Full Case File'),
}


def _auth_user(request):
    auth = request.headers.get('Authorization', '')
    key = None
    if auth.startswith('Token '):
        key = auth.split(' ', 1)[1].strip()
    if not key:
        key = request.GET.get('token')
    if not key:
        return None
    try:
        return Token.objects.select_related('user').get(key=key).user
    except Token.DoesNotExist:
        return None


def print_form(request, form):
    user = _auth_user(request)
    if not user:
        return HttpResponse('Authentication required.', status=401)
    if form not in FORMS:
        raise Http404('Unknown form')
    template, title = FORMS[form]

    qs = scoped_household_qs(user).prefetch_related(
        'members', 'caregiver', 'checklist_items', 'process_notes', 'assessments'
    )
    hid = request.GET.get('household_id')
    ids = request.GET.get('household_ids')
    if hid:
        qs = qs.filter(pk=hid)
    elif ids:
        pks = [i for i in ids.split(',') if i.strip().isdigit()]
        qs = qs.filter(pk__in=pks)
    households = list(qs)
    if not households:
        raise Http404('No households in scope')

    org = Organisation.get_solo()
    org_name = request.GET.get('org') or org.name
    # Relative URL: the print page is served from the public origin, so a
    # relative src resolves correctly. build_absolute_uri() would use the
    # internal cluster Host header and break the image in the browser.
    org_logo = org.logo.url if org.logo else None
    aid = request.GET.get('assessment_id')
    today = timezone.localdate()
    for hh in households:
        hh.cg = getattr(hh, 'caregiver', None)
        if hh.cg:
            hh.cg.age = _age(hh.cg.date_of_birth, today)
        hh.member_list = list(hh.members.all())
        for m in hh.member_list:
            m.age = _age(m.date_of_birth, today)
        groups = {}
        for it in hh.checklist_items.all():
            groups.setdefault(it.category, []).append(it)
        hh.cl_groups = [(CAT_LABELS.get(c, c), groups.get(c, [])) for c, _ in choices.CATEGORY_CHOICES]
        hh.notes_list = list(hh.process_notes.all())
        try:
            hh.cl_pct = checklist_progress(hh).get('percent', 0)
        except Exception:
            hh.cl_pct = 0
        assessments = list(hh.assessments.all())
        hh.assessment = (next((a for a in assessments if str(a.pk) == aid), None)
                         if aid else (assessments[0] if assessments else None))
        log_action(user, 'printed', f'Printed "{title}" for Household #{hh.pk} ({hh.org_household_number})')

    ctx = {
        'households': households,
        'org_name': org_name,
        'org_logo': org_logo,
        'org': org,
        'show_cover': len(households) > 1 and request.GET.get('cover') != '0',
        'cover_avg': round(sum(getattr(h, 'cl_pct', 0) for h in households) / len(households)) if households else 0,
        'now': timezone.now(),
        'user': user,
        'form_title': title,
        'auto_print': request.GET.get('auto') == '1',
    }
    return render(request, template, ctx)


def print_timeline(request, form=None):
    """Print-friendly household activity timeline (from the audit log)."""
    from .models import AuditLogEntry
    user = _auth_user(request)
    if not user:
        return HttpResponse('Authentication required.', status=401)
    hid = request.GET.get('household_id')
    qs = scoped_household_qs(user).prefetch_related('caregiver')
    hh = qs.filter(pk=hid).first() if hid else None
    if not hh:
        raise Http404('No household in scope')
    cg = getattr(hh, 'caregiver', None)
    hh.cg = cg
    entries = list(AuditLogEntry.objects.select_related('user').filter(
        target_description__regex=rf'Household #{hh.pk}([^0-9]|$)'
    ).order_by('timestamp'))
    org = Organisation.get_solo()
    log_action(user, 'printed', f'Printed activity timeline for Household #{hh.pk}')
    ctx = {
        'hh': hh, 'entries': entries,
        'org_name': request.GET.get('org') or org.name,
        'org_logo': org.logo.url if org.logo else None,
        'now': timezone.now(), 'user': user,
        'form_title': 'Household Activity Timeline',
        'auto_print': request.GET.get('auto') == '1',
    }
    return render(request, 'print/timeline.html', ctx)


def print_service_report(request, form=None):
    """Print service-delivery reports: per-household history, missed, or monthly summary."""
    from .models import ServiceDelivery
    from .views import _month_bounds
    user = _auth_user(request)
    if not user:
        return HttpResponse('Authentication required.', status=401)
    org = Organisation.get_solo()
    report = request.GET.get('report', 'household')
    month = request.GET.get('month')
    if month:
        y, m = month.split('-')
        start = timezone.datetime(int(y), int(m), 1).date()
    else:
        start = None
    if start:
        _, nxt = _month_bounds(start)
    scoped = scoped_household_qs(user).prefetch_related('caregiver')
    ctx = {
        'org_name': request.GET.get('org') or org.name,
        'org_logo': org.logo.url if org.logo else None,
        'now': timezone.now(), 'user': user,
        'auto_print': request.GET.get('auto') == '1',
        'report': report,
        'month_label': start.strftime('%B %Y') if start else 'All time',
    }

    if report == 'household':
        hid = request.GET.get('household_id')
        hh = scoped.filter(pk=hid).first()
        if not hh:
            raise Http404('No household in scope')
        cg = getattr(hh, 'caregiver', None)
        hh.cg = cg
        svc = ServiceDelivery.objects.filter(household=hh).select_related('delivered_by')
        if start:
            svc = svc.filter(service_date__gte=start, service_date__lt=nxt)
        rows = list(svc.order_by('service_date'))
        for r in rows:
            b = r.beneficiary
            r.beneficiary_label = f'{b.name} {b.surname}'.strip() if b else 'Household'
        ctx.update({'hh': hh, 'rows': rows, 'form_title': 'Household Service History'})
        log_action(user, 'printed', f'Printed service history for Household #{hh.pk}')
        return render(request, 'print/service_household.html', ctx)

    # Organisation-wide reports need supervisor/admin scope (scoped_household_qs
    # already limits case workers, so this is naturally safe).
    if not start:
        start, nxt = _month_bounds()
        ctx['month_label'] = start.strftime('%B %Y')
    svc = ServiceDelivery.objects.filter(
        household__in=scoped, service_date__gte=start, service_date__lt=nxt
    ).select_related('delivered_by', 'household')

    if report == 'missed':
        served = set(svc.values_list('household_id', flat=True))
        missed = []
        for hh in scoped:
            if hh.id in served:
                continue
            last = ServiceDelivery.objects.filter(household=hh).order_by('-service_date').first()
            cg = getattr(hh, 'caregiver', None)
            missed.append({
                'org_household_number': hh.org_household_number,
                'caregiver_name': f'{cg.name} {cg.surname}'.strip() if cg else '',
                'last_service_date': last.service_date if last else None,
            })
        ctx.update({'missed': missed, 'form_title': 'Households Not Served This Month'})
        log_action(user, 'printed', 'Printed missed-households report')
        return render(request, 'print/service_missed.html', ctx)

    # Monthly summary: grouped by staff + by service type.
    by_staff = {}
    by_type = {}
    for s in svc:
        name = (s.delivered_by.get_full_name() or s.delivered_by.username) if s.delivered_by else 'Unknown'
        by_staff[name] = by_staff.get(name, 0) + 1
        by_type[s.service_type] = by_type.get(s.service_type, 0) + 1
    total_hh = scoped.count()
    served_hh = len(set(svc.values_list('household_id', flat=True)))
    ctx.update({
        'by_staff': sorted(by_staff.items(), key=lambda x: -x[1]),
        'by_type': sorted(by_type.items(), key=lambda x: -x[1]),
        'total_hh': total_hh, 'served_hh': served_hh,
        'served_pct': round(served_hh * 100 / total_hh) if total_hh else 0,
        'total_services': svc.count(),
        'form_title': 'Monthly Service Delivery Report',
    })
    log_action(user, 'printed', 'Printed monthly service delivery report')
    return render(request, 'print/service_summary.html', ctx)
