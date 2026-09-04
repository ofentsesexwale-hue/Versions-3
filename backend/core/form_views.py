"""Official-form canvas API: atlas, blank PNG, fill values, print HTML."""
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import render
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .audit import log_action
from .form_atlas import ATLAS_FORMS, fields_for, form_meta
from .form_io import apply_buckets, buckets_from_values, values_for_household
from .official_blanks import ATLAS_VERSION, blank_path
from .permissions import ROLE_CAREGIVER, can_edit_records, user_role
from .print_views import _auth_user
from .views import scoped_household_qs


class OfficialFormListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        forms = [form_meta(code) | {'fields': fields_for(code)} for code in ATLAS_FORMS]
        return Response({'atlas_version': ATLAS_VERSION, 'forms': forms})


class OfficialFormDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, code):
        if code not in ATLAS_FORMS:
            return Response({'detail': 'No official canvas for that form.'}, status=404)
        meta = form_meta(code)
        meta['fields'] = fields_for(code)
        hid = request.GET.get('household') or request.GET.get('household_id')
        household = None
        if hid:
            household = scoped_household_qs(request.user).filter(pk=hid).first()
            if not household:
                return Response({'detail': 'That household is not on your caseload.'}, status=404)
        meta['values'] = values_for_household(household) if household else {}
        meta['household'] = household.pk if household else None
        meta['can_edit'] = can_edit_records(request.user) and user_role(request.user) != ROLE_CAREGIVER
        return Response(meta)


def official_blank(request, code, page):
    user = request.user if getattr(request.user, 'is_authenticated', False) else None
    if not user:
        user = _auth_user(request)
    if not user:
        return HttpResponse('Authentication required.', status=401)
    path = blank_path(code, int(page))
    if not path or not path.exists():
        raise Http404('No official blank for that page.')
    return FileResponse(open(path, 'rb'), content_type='image/png')


class OfficialFormValuesView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, code):
        if user_role(request.user) == ROLE_CAREGIVER or not can_edit_records(request.user):
            return Response({'detail': 'Your login cannot edit official forms.'}, status=403)
        if code not in ATLAS_FORMS:
            return Response({'detail': 'No official canvas for that form.'}, status=404)
        hid = request.data.get('household') or request.GET.get('household_id')
        household = None
        if hid:
            household = scoped_household_qs(request.user).filter(pk=hid).first()
            if not household:
                return Response({'detail': 'That household is not on your caseload.'}, status=404)
        buckets = buckets_from_values(request.data.get('values') or {})
        # Typing a value onto the official sheet and saving it *is* the staff
        # sign-off, so these targets count as confirmed. Scan Intake does not
        # get that shortcut — it must carry a per-field confirm from the user.
        household = apply_buckets(request, household, buckets, confirmed_targets=set(buckets))
        log_action(request.user, 'edited', f'Filled official {code} for Household #{household.pk}')
        return Response({
            'household': household.pk,
            'org_household_number': household.org_household_number,
            'values': values_for_household(household),
        })


WORD_PRINT_FORMS = {
    'c01': ('fill_c01_docx', 'C01', 'C01'),
    'c02': ('fill_c02_docx', 'C02', 'C02'),
    'c03': ('fill_c03_docx', 'C03', 'C03'),
    'intake': ('fill_cw05_docx', 'CW05', 'CW 05'),
    'family_care_plan': ('fill_fcp_docx', 'FCP', 'Family Care Plan'),
    'hiv_risk': ('fill_hiv_risk_docx', 'HIV_Risk', 'HIV Risk Assessment'),
    'consent': ('fill_consent_docx', 'HIV_Consent', 'HIV Consent Forms'),
    'client_referral': ('fill_client_referral_docx', 'Client_Referral', 'Client Referral Form'),
    'hivstat': ('fill_hivstat_docx', 'HTS', 'HTS Tracking Form'),
    'monthly_report': ('fill_c06_docx', 'C06', 'C06 Monthly Services'),
    'educational': ('fill_educational_docx', 'Educational', 'Educational Progress Record'),
    'site_visit': ('fill_site_visit_docx', 'Site_Visit', 'Site Visit Form'),
    'exit': ('fill_exit_docx', 'Family_Exit', 'Family Exit Form'),
    'checklist': ('fill_checklist_docx', 'NPO_Check_List', 'NPO Check List'),
    'content_page': ('fill_content_page_docx', 'Content_Page', 'Content Page'),
    'process_note': ('fill_process_note_docx', 'CW11', 'CW 11 Process Note'),
    'termination': ('fill_termination_docx', 'CW13', 'CW 13 Termination'),
    'internal_referral': ('fill_internal_referral_docx', 'CW4A', 'CW 4a Internal Referral'),
    'referral': ('fill_referral_docx', 'CW4B', 'CW 4b External Referral'),
    'cow2_note': ('fill_cow2_docx', 'COW02', 'COW 02 Process Note'),
}


def print_official(request, form):
    """Official print: Word forms download filled .docx; other atlas forms stay on canvas."""
    user = _auth_user(request)
    if not user:
        return HttpResponse('Authentication required.', status=401)
    if form not in ATLAS_FORMS:
        raise Http404('Unknown official form')
    hid = request.GET.get('household_id')
    household = scoped_household_qs(user).filter(pk=hid).first() if hid else None
    if not household:
        raise Http404('No household in scope')

    # Phase 1+: official Word templates — never the NPO PDF overlay.
    if form in WORD_PRINT_FORMS:
        from django.http import HttpResponse as DjangoResponse
        from . import word_forms
        from .word_forms import values_from_household

        values = values_from_household(household)
        fill_name, file_stem, label = WORD_PRINT_FORMS[form]
        fill_fn = getattr(word_forms, fill_name)
        if form == 'c03':
            payload = fill_fn(values, member_slot=request.GET.get('member'))
        else:
            payload = fill_fn(values)
        filename = f"{file_stem}_{household.org_household_number or household.pk}.docx"
        log_action(user, 'printed', f'Printed official {label} Word for Household #{household.pk}')
        response = DjangoResponse(
            payload,
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    meta = form_meta(form)
    token = request.GET.get('token') or ''
    pages = []
    for i, blank in enumerate(meta.get('blanks') or []):
        pages.append({
            'index': i,
            'blank_url': f'/api/official-forms/{form}/blank/{i}/?token={token}',
            'orientation': blank.get('orientation') or meta.get('orientation'),
            'fields': fields_for(form, i),
        })
    values = values_for_household(household)
    log_action(user, 'printed', f'Printed official "{meta["title"]}" for Household #{household.pk}')
    return render(request, 'print/official_canvas.html', {
        'form_title': meta['title'],
        'household': household,
        'atlas_version': ATLAS_VERSION,
        'auto_print': request.GET.get('auto') == '1',
        'landscape': meta.get('orientation') == 'landscape',
        'payload_json': {'pages': pages, 'values': values},
    })
