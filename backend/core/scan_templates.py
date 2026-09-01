"""DSD form types for Scan Intake.

Labels follow the print templates in core/templates/print/ (field names on the
official layouts). Do not invent alternate field names.
"""
from .print_views import FORMS
from .sa_id import parse_sa_id

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
    """Return text following the first matching label (print-template wording)."""
    upper = text or ''
    lowered = upper.lower()
    for label in labels:
        idx = lowered.find(label.lower())
        if idx < 0:
            continue
        rest = upper[idx + len(label):]
        rest = rest.replace(':', ' ').replace('|', ' ')
        line = rest.split('\n', 1)[0].strip()
        line = ' '.join(line.split())
        if line:
            return line[:200]
    return ''


def _first_sa_id(text):
    digits = ''.join(ch if ch.isdigit() else ' ' for ch in (text or ''))
    for token in digits.split():
        parsed = parse_sa_id(token)
        if parsed['is_sa_length'] and parsed['luhn_ok']:
            return parsed
    for token in digits.split():
        if len(token) == 13:
            return parse_sa_id(token)
    return None


def extract_fields(form_type, text, confidence=0.6):
    """Map OCR text onto existing model fields. Labels match print templates."""
    fields = []

    def add(label, value, target, conf=None):
        value = (value or '').strip()
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

    parsed = _first_sa_id(text)
    if parsed and parsed.get('digits'):
        add('SA ID Number', parsed['digits'], 'caregiver.id_number', 0.9 if parsed.get('luhn_ok') else 0.55)
        if parsed.get('dob'):
            add('Date of birth (from ID)', parsed['dob'], 'caregiver.date_of_birth', 0.85 if parsed.get('luhn_ok') else 0.5)
        if parsed.get('sex'):
            add('Sex (from ID)', parsed['sex'], 'caregiver.sex', 0.8 if parsed.get('luhn_ok') else 0.45)

    if form_type in ('intake', 'c01', 'c02', 'c03', 'unknown'):
        add(
            'Primary Client Surname',
            _after_label(text, ['Primary Client Surname', 'Caregiver Surname', 'Surname']),
            'caregiver.surname',
        )
        add(
            'Primary Client First name',
            _after_label(text, ['Primary Client First name', 'Caregiver First name', 'First name', 'Name']),
            'caregiver.name',
        )
        add(
            'Intake Ref Number',
            _after_label(text, ['Intake Ref Number', 'Org Household Nr', 'Org Household Number', 'Org Household Nr.']),
            'household.org_household_number',
        )
        add(
            'House Number',
            _after_label(text, ['House Number']),
            'household.house_number',
        )
        add(
            'Street',
            _after_label(text, ['Street']),
            'household.street',
        )
        add(
            'Town',
            _after_label(text, ['Town', 'Town / City']),
            'household.town',
        )
        add(
            'Province',
            _after_label(text, ['Province']),
            'household.province',
        )
        add(
            'District',
            _after_label(text, ['District']),
            'household.district',
        )
        add(
            'Municipality',
            _after_label(text, ['Municipality']),
            'household.municipality',
        )
        add(
            'Ward',
            _after_label(text, ['Ward']),
            'household.ward',
        )
        add(
            'Cell number',
            _after_label(text, ['Cell', 'Cell number', 'Cell Number', 'Contact']),
            'caregiver.cell_number',
        )
        add(
            'Known As',
            _after_label(text, ['Known As']),
            'caregiver.known_as',
        )
        add(
            'Home Language',
            _after_label(text, ['Home Language']),
            'caregiver.home_language',
        )

    if form_type == 'process_note':
        add('Client surname', _after_label(text, ['Client surname', 'Surname']), 'process_note.client_surname')
        add('Client first name', _after_label(text, ['Client first name', 'First name']), 'process_note.client_first_name')
        add('File no', _after_label(text, ['File no', 'File number']), 'process_note.file_no')
        add(
            'Purpose and what transpired',
            _after_label(text, ['Purpose and what transpired', 'What transpired']),
            'process_note.purpose_and_what_transpired',
        )
        add(
            'Outcome and follow up',
            _after_label(text, ['Outcome and follow up', 'Follow up']),
            'process_note.outcome_and_follow_up',
        )
        add('Problem code', _after_label(text, ['Problem code', 'Primary Problem Code']), 'process_note.problem_code')

    if form_type == 'family_care_plan':
        add('Overall goal', _after_label(text, ['Overall goal', 'Overall Goal']), 'care_plan.overall_goal')
        add('SSP name', _after_label(text, ['SSP Name', 'SSP name']), 'care_plan.ssp_name')

    if form_type in ('hiv_risk', 'hivstat'):
        add('HIV status', _after_label(text, ['HIV status', 'HIV Status']), 'member.hiv_status')
        add('On ART', _after_label(text, ['On ART']), 'member.on_art')
        add('Last viral load', _after_label(text, ['Viral load', 'Last viral load']), 'member.last_viral_load')

    if form_type == 'assessment':
        add(
            'Overview of the situation',
            _after_label(text, ['Overview', 'Situation']),
            'assessment.overview_situation',
        )
        add('Primary Problem Code (see CW 06)', _after_label(text, ['Primary Problem Code', 'Problem Code']), 'assessment.problem_codes')
        add('Overall goal', _after_label(text, ['Overall goal']), 'assessment.overall_goal')

    if form_type == 'educational':
        add('School name', _after_label(text, ['School name', 'School Name']), 'member.school_name')
        add('Grade', _after_label(text, ['Grade']), 'member.grade')

    # Deduplicate by target keeping the higher confidence.
    by_target = {}
    for item in fields:
        prev = by_target.get(item['target'])
        if not prev or item['confidence'] > prev['confidence']:
            by_target[item['target']] = item
    return list(by_target.values())


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
