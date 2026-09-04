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


def print_official(request, form):
    """Official print: C01/C02/C03 are filled Word files; other atlas forms stay on canvas for now."""
    user = _auth_user(request)
    if not user:
        return HttpResponse('Authentication required.', status=401)
    if form not in ATLAS_FORMS:
        raise Http404('Unknown official form')
    hid = request.GET.get('household_id')
    household = scoped_household_qs(user).filter(pk=hid).first() if hid else None
    if not household:
        raise Http404('No household in scope')

    # Phase 1+: C01–C03 print into official Word templates — never the NPO PDF.
    if form in ('c01', 'c02', 'c03'):
        from django.http import HttpResponse as DjangoResponse
        from .word_forms import fill_c01_docx, fill_c02_docx, fill_c03_docx, values_from_household

        values = values_from_household(household)
        if form == 'c01':
            payload = fill_c01_docx(values)
            filename = f"C01_{household.org_household_number or household.pk}.docx"
            label = 'C01'
        elif form == 'c02':
            payload = fill_c02_docx(values)
            filename = f"C02_{household.org_household_number or household.pk}.docx"
            label = 'C02'
        else:
            payload = fill_c03_docx(values, member_slot=request.GET.get('member'))
            filename = f"C03_{household.org_household_number or household.pk}.docx"
            label = 'C03'
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
