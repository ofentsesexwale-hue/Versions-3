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

    org_name = request.GET.get('org') or 'OVC Organisation'
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
        hh.assessment = hh.assessments.all().first() if hasattr(hh, 'assessments') else None
        log_action(user, 'printed', f'Printed "{title}" for Household #{hh.pk} ({hh.org_household_number})')

    ctx = {
        'households': households,
        'org_name': org_name,
        'now': timezone.now(),
        'user': user,
        'form_title': title,
        'auto_print': request.GET.get('auto') == '1',
    }
    return render(request, template, ctx)
