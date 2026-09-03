"""DSD form types for Scan Intake.

Labels follow the print templates in core/templates/print/ (field names on the
official layouts). Do not invent alternate field names.
"""
from .form_labels import EXTRACTION_LABELS, looks_like_form_label
from .print_views import FORMS
from .sa_id import parse_sa_id
from .scan_text import sanitize_ocr_value

# Print-form key -> checklist (category, sub_item) when a scan is confirmed.
CHECKLIST_FOR_FORM = {
    'intake': ('intake_form', 'CW05'),
    'c01': ('intake_form', 'C01'),
    'c02': ('intake_form', 'C02'),
    'c03': ('intake_form', 'C03'),
    'family_care_plan': ('family_care_plan', 'Family Care Plan'),
    'hiv_risk': ('family_care_plan', 'Risk Assessment Form'),
    'consent': ('family_care_plan', 'Consent form'),
    'process_note': ('process_note', 'SAW Process note - CW 11'),
    'termination': ('process_note', 'Termination report / Exit forms - CW 13'),
    'educational': ('school_report', 'Educational Plan'),
    'referral': ('referral_form', 'Referral form'),
    'success_story': ('success_story', 'Success story'),
    'monthly_report': ('monthly_report', 'Monthly Household Services Report - C06'),
}

# Extra types that appear on the physical file but are not print keys.
EXTRA_FORM_LABELS = {
    'c01': 'C01',
    'c02': 'C02',
    'c03': 'C03',
    'unknown': 'Unrecognised page',
}

# Keywords scored against OCR text (uppercase). Drawn from print titles / headings.
CLASSIFY_KEYWORDS = {
    'intake': ['CW 05', 'CW05', 'INTAKE FORM', 'PRIMARY CLIENT SURNAME', 'INTAKE REF NUMBER'],
    'assessment': ['CW 09', 'CW09', 'ASSESSMENT, PLANNING', 'PLANNING AND CONTRACTING'],
    'process_note': ['CW 11', 'CW11', 'CASE WORK PROCESS NOTE', 'PURPOSE AND WHAT TRANSPIRED'],
    'family_care_plan': ['FAMILY CARE PLAN', 'NEEDS / ACTIONS', 'OVERALL GOAL'],
    'hiv_risk': ['HIV RISK ASSESSMENT', 'HIV RISK'],
    'hivstat': ['HIVSTAT', 'ON ART', 'VIRAL LOAD'],
    'consent': ['CONSENT RECORD', 'CONSENT TO SERVICES', 'PHOTOGRAPH'],
    'referral': ['CW 04B', 'CW04B', 'EXTERNAL REFERRAL'],
    'educational': ['EDUCATIONAL PROGRESS', 'SCHOOL NAME', 'GRADE'],
    'termination': ['CW 13', 'CW13', 'TERMINATION REPORT'],
    'monthly_report': ['C06', 'MONTHLY HOUSEHOLD SERVICES'],
    'success_story': ['SUCCESS STORY'],
    'cow1': ['COW 1', 'COW1', 'COMMUNITY WORK PLAN'],
    'evaluation': ['CW 12', 'CW12', 'EVALUATION'],
    'reporter': ['CW 02', 'CW02', 'REPORTER FORM'],
    'c01': ['C01', 'C 01', 'HOUSEHOLD DETAILS', 'HEAD OF HOUSEHOLD', 'ORG HOUSEHOLD'],
    'c02': ['C02', 'C 02'],
    'c03': ['C03', 'C 03'],
    'checklist': ['CASE FILE CHECKLIST'],
    'form22': ['FORM 22', 'PROTECTION INCIDENT'],
}


def form_label(form_type):
    if form_type in FORMS:
        return FORMS[form_type][1]
    return EXTRA_FORM_LABELS.get(form_type, form_type or 'Unrecognised page')


def classify_text(text):
    blob = (text or '').upper()
    best, score = 'unknown', 0
    for form_type, words in CLASSIFY_KEYWORDS.items():
        hits = sum(1 for w in words if w in blob)
        if hits > score:
            best, score = form_type, hits
    confidence = 0.0 if score == 0 else min(0.95, 0.35 + 0.2 * score)
    return best, round(confidence, 2)


def _after_label(text, labels):
    """Text following the first matching label in the flattened page text.

    A weak reading of a dense sheet: what follows a label in the blob is very
    often the NEXT label rather than an answer, and RapidOCR's reading order is
    not reliably left-to-right, so on C02 the columns come back reversed. It is
    a last resort for sheets with no measured atlas, and a candidate that is
    itself printed wording is refused so one label cannot answer another.
    """
    upper = text or ''
    lowered = upper.lower()
    for label in labels:
        idx = lowered.find(label.lower())
        if idx < 0:
            continue
        rest = upper[idx + len(label):]
        rest = rest.replace(':', ' ').replace('|', ' ')
        line = rest.split('\n', 1)[0].strip()
        line = ' '.join(line.split()[:6])
        if not line:
            continue
        if looks_like_form_label(line):
            continue
        return line[:200]
    return ''


def _first_sa_id(text):
    digits = ''.join(ch if ch.isdigit() else ' ' for ch in (text or ''))
    for token in digits.split():
        parsed = parse_sa_id(token)
        if parsed['valid']:
            return parsed
    for token in digits.split():
        if len(token) == 13:
            return parse_sa_id(token)
    return None


def extract_fields(form_type, text, confidence=0.6):
    """Map full-page OCR text onto model fields, where no atlas box covers them.

    This is the fallback for sheets Scan Intake has no measured geometry for.
    On a sheet that does have an atlas, the per-field crops are the answer -
    including a blank crop, which means nothing was written in that box - so
    scraping the flattened page text is switched off rather than allowed to
    guess over them. The atlas decides that, not the caller.
    """
    from .form_atlas import atlas_coverage

    atlas_covered, atlas_targets = atlas_coverage(form_type)
    fields = []
    labels = EXTRACTION_LABELS

    def add(label, value, target, conf=None):
        if target and target in atlas_targets:
            return
        value = sanitize_ocr_value(target, value)
        if not value:
            return
        c = conf if conf is not None else confidence
        fields.append({
            'label': label,
            'value': value,
            'target': target,
            'confidence': round(float(c), 2),
            'low_confidence': float(c) < 0.72,
            'confirmed': False,
        })

    def scrape(label, target, conf=None):
        if atlas_covered or target in atlas_targets:
            return
        add(label, _after_label(text, labels[target]), target, conf)

    parsed = _first_sa_id(text)
    if parsed and parsed['digits']:
        _add_page_id(add, fields, parsed, atlas_covered)

    if form_type in ('intake', 'c01', 'c02', 'c03', 'unknown'):
        scrape('Primary Client Surname', 'caregiver.surname')
        scrape('Primary Client First name', 'caregiver.name')
        scrape('Intake Ref Number', 'household.org_household_number')
        scrape('House Number', 'household.house_number')
        scrape('Street', 'household.street')
        scrape('Town', 'household.town')
        scrape('Province', 'household.province')
        scrape('District', 'household.district')
        scrape('Municipality', 'household.municipality')
        scrape('Ward', 'household.ward')
        scrape('Cell number', 'caregiver.cell_number')
        scrape('Known As', 'caregiver.known_as')
        scrape('Home Language', 'caregiver.home_language')

    if form_type == 'process_note':
        scrape('Client surname', 'process_note.client_surname')
        scrape('Client first name', 'process_note.client_first_name')
        scrape('File no', 'process_note.file_no')
        scrape('Purpose and what transpired', 'process_note.purpose_and_what_transpired')
        scrape('Outcome and follow up', 'process_note.outcome_and_follow_up')
        scrape('Problem code', 'process_note.problem_code')

    if form_type == 'family_care_plan':
        scrape('Overall goal', 'care_plan.overall_goal')
        scrape('SSP name', 'care_plan.ssp_name')

    if form_type in ('hiv_risk', 'hivstat'):
        scrape('HIV status', 'member.hiv_status')
        scrape('On ART', 'member.on_art')
        scrape('Last viral load', 'member.last_viral_load')

    if form_type == 'assessment':
        scrape('Overview of the situation', 'assessment.overview_situation')
        scrape('Primary Problem Code (see CW 06)', 'assessment.problem_codes')
        scrape('Overall goal', 'assessment.overall_goal')

    if form_type == 'educational':
        scrape('School name', 'member.school_name')
        scrape('Grade', 'member.grade')

    # Deduplicate by target keeping the higher confidence. Unassigned
    # candidates have no target to collide on and are all kept.
    by_target = {}
    out = []
    for item in fields:
        if not item['target']:
            out.append(item)
            continue
        prev = by_target.get(item['target'])
        if not prev or item['confidence'] > prev['confidence']:
            by_target[item['target']] = item
    return out + list(by_target.values())


def _add_page_id(add, fields, parsed, atlas_covered):
    """Place a 13-digit run found loose in the page text, or hand it to staff.

    The scan is page-wide and knows nothing about whose section of the sheet
    the number sat in. On a C01 members page it picked up a child's ID, wrote
    it to the caregiver, and derived a date of birth and a sex from it. So on
    any sheet with an atlas the number is offered as an unassigned reading for
    staff to place, and names nobody. Sheets with no atlas keep the old
    behaviour, because scraping is all they have.
    """
    digits = parsed['digits']
    if atlas_covered:
        fields.append({
            'label': 'ID number read on this page - not placed',
            'value': digits,
            'target': '',
            'kind': 'sa_id',
            'confidence': 0.55,
            'low_confidence': True,
            'confirmed': False,
            'unassigned': True,
            'note': (
                'A 13-digit ID was read somewhere on this page, but nothing says whose '
                'it is. Type it onto the right person.'
            ),
        })
        return
    if not parsed['valid']:
        add('SA ID Number', digits, 'caregiver.id_number', 0.5)
        for item in fields:
            if item['target'] == 'caregiver.id_number':
                item['low_confidence'] = True
                item['invalid_id'] = True
                item['note'] = 'Not a valid SA ID: ' + '; '.join(parsed['problems'])
        return
    add('SA ID Number', digits, 'caregiver.id_number', 0.9)
    if parsed['dob']:
        add('Date of birth (from ID)', parsed['dob'], 'caregiver.date_of_birth', 0.85)
    if parsed['sex']:
        add('Sex (from ID)', parsed['sex'], 'caregiver.sex', 0.8)


def form_choices():
    keys = list(FORMS.keys()) + list(EXTRA_FORM_LABELS.keys())
    seen = []
    out = []
    for key in keys:
        if key in seen or key == 'full':
            continue
        seen.append(key)
        out.append({'value': key, 'label': form_label(key)})
    return out
