"""One field atlas for fill, print, and Scan Intake.

Boxes are normalised 0–1 on the official blank PNG (same file print uses).
Labels follow the NPO PDF. Do not rename them.
"""
from .official_blanks import ATLAS_VERSION, load_meta, page_count

# form code -> metadata. `intake` is CW 05 (existing print/scan key).
ATLAS_FORMS = {
    'c01': {
        'title': 'C01: Household Details',
        'official_title': 'C01: Household Details CCG Form v.1.2',
        'header': 'ccg',
        'orientation': 'portrait',
        'keywords': ['C01', 'C 01', 'HOUSEHOLD DETAILS', 'CCG FORM', 'HEAD OF HOUSEHOLD'],
        'checklist_item': ('intake_form', 'C01'),
        'geometry': 'pdf',
    },
    'intake': {
        'title': 'CW 05: Intake Form',
        'official_title': 'CW 05: INTAKE FORM',
        'header': 'dsd',
        'orientation': 'portrait',
        'keywords': ['CW 05', 'CW05', 'INTAKE FORM', 'PRIMARY CLIENT SURNAME', 'INTAKE REF NUMBER'],
        'checklist_item': ('intake_form', 'CW05'),
        'geometry': 'pdf',
    },
    'c02': {
        'title': 'C02 ADULT Assessment Form',
        'official_title': 'C02 ADULT Assessment Form',
        'header': 'ccg',
        'orientation': 'landscape',
        'keywords': ['C02', 'C 02', 'ADULT ASSESSMENT', 'CCG FORM'],
        'checklist_item': ('intake_form', 'C02'),
        'geometry': 'pdf',
        'identity_only': True,
    },
    'c03': {
        'title': 'C03 CHILD Beneficiary Assessment',
        'official_title': 'C03 CHILD Beneficiary Assessment',
        'header': 'ccg',
        'orientation': 'landscape',
        'keywords': ['C03', 'C 03', 'CHILD BENEFICIARY', 'CCG FORM'],
        'checklist_item': ('intake_form', 'C03'),
        'geometry': 'pdf',
        'identity_only': True,
    },
    'family_care_plan': {
        'title': 'Family Care Plan',
        'official_title': 'Family Care Plan',
        'header': 'dsd',
        'orientation': 'landscape',
        'keywords': ['FAMILY CARE PLAN', 'FAMILY REGISTRATION', 'IDENTIFIED NEEDS'],
        'checklist_item': ('family_care_plan', 'Family Care Plan'),
        'geometry': 'pdf',
        'header_only': True,
    },
    'process_note': {
        'title': 'CW 11: Case Work Process Note',
        'official_title': 'CW 11: Case Work Process Note',
        'header': 'dsd',
        'orientation': 'portrait',
        'keywords': ['CW 11', 'CW11', 'CASE WORK PROCESS NOTE', 'PURPOSE AND WHAT TRANSPIRED'],
        'checklist_item': ('process_note', 'SAW Process note - CW 11'),
        'geometry': 'missing',
    },
}


def _box(x0, y0, x1, y1):
    return (round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4))


def _f(target, label, page, box, kind, **extra):
    item = {
        'target': target,
        'label': label,
        'page': page,
        'box': _box(*box),
        'kind': kind,
    }
    item.update(extra)
    return item


def _id_cells(target, label, page, x0, y0, x1, y1):
    return _f(target, label, page, (x0, y0, x1, y1), 'sa_id', cells=13)


def _c01_member(page, slot, y0):
    """Member identity block. y0 = grey 'Add member' bar."""
    p = f'member.{slot}.'
    return [
        _f(p + 'id_type', 'Type of ID', page, (0.33, y0 + 0.018, 0.36, y0 + 0.032), 'checkbox', option='SA ID Number', group=p + 'id_type'),
        _f(p + 'id_type', 'Type of ID', page, (0.59, y0 + 0.018, 0.62, y0 + 0.032), 'checkbox', option='Passport Number', group=p + 'id_type'),
        _f(p + 'id_type', 'Type of ID', page, (0.76, y0 + 0.018, 0.79, y0 + 0.032), 'checkbox', option='Permit', group=p + 'id_type'),
        _id_cells(p + 'id_number', 'ID Number', page, 0.25, y0 + 0.040, 0.83, y0 + 0.058),
        _f(p + 'name', 'Name', page, (0.25, y0 + 0.060, 0.83, y0 + 0.076), 'handwrite'),
        _f(p + 'surname', 'Surname', page, (0.25, y0 + 0.076, 0.83, y0 + 0.092), 'handwrite'),
        _f(p + 'known_as', 'Known As', page, (0.25, y0 + 0.092, 0.83, y0 + 0.108), 'handwrite'),
        _f(p + 'nationality', 'Nationality', page, (0.25, y0 + 0.108, 0.83, y0 + 0.124), 'handwrite'),
        _f(p + 'date_of_birth', 'Date of Birth', page, (0.25, y0 + 0.124, 0.83, y0 + 0.140), 'date'),
        _f(p + 'sex', 'Sex', page, (0.28, y0 + 0.144, 0.31, y0 + 0.160), 'checkbox', option='Male', group=p + 'sex'),
        _f(p + 'sex', 'Sex', page, (0.57, y0 + 0.144, 0.60, y0 + 0.160), 'checkbox', option='Female', group=p + 'sex'),
        _f(p + 'race', 'Race', page, (0.28, y0 + 0.164, 0.31, y0 + 0.180), 'checkbox', option='African', group=p + 'race'),
        _f(p + 'race', 'Race', page, (0.40, y0 + 0.164, 0.43, y0 + 0.180), 'checkbox', option='White', group=p + 'race'),
        _f(p + 'race', 'Race', page, (0.57, y0 + 0.164, 0.60, y0 + 0.180), 'checkbox', option='Coloured', group=p + 'race'),
        _f(p + 'race', 'Race', page, (0.76, y0 + 0.164, 0.79, y0 + 0.180), 'checkbox', option='Indian', group=p + 'race'),
        _f(p + 'disability', 'Disability', page, (0.28, y0 + 0.188, 0.31, y0 + 0.204), 'checkbox', option='false', group=p + 'disability'),
        _f(p + 'disability', 'Disability', page, (0.40, y0 + 0.188, 0.43, y0 + 0.204), 'checkbox', option='true', group=p + 'disability'),
        _f(p + 'disability_description', 'Describe', page, (0.55, y0 + 0.186, 0.83, y0 + 0.204), 'handwrite'),
        _f(p + 'date_joined', 'Date Joined', page, (0.25, y0 + 0.208, 0.83, y0 + 0.224), 'date'),
        _f(p + 'relationship_to_head', 'Relationship to Head of Household', page, (0.42, y0 + 0.226, 0.83, y0 + 0.244), 'handwrite'),
    ]


def _build_fields():
    c01 = [
        _f('household.org_household_number', 'Org Household Nr', 0, (0.275, 0.090, 0.575, 0.110), 'printed'),
        _f('household.province', 'Province', 0, (0.625, 0.090, 0.833, 0.110), 'printed'),
        _f('household.house_number', 'House Number', 0, (0.275, 0.110, 0.575, 0.126), 'printed'),
        _f('household.district', 'District', 0, (0.625, 0.110, 0.833, 0.126), 'printed'),
        _f('household.street', 'Street', 0, (0.275, 0.126, 0.575, 0.142), 'printed'),
        _f('household.municipality', 'Municipality', 0, (0.625, 0.126, 0.833, 0.142), 'printed'),
        _f('household.town', 'Town', 0, (0.275, 0.142, 0.500, 0.156), 'printed'),
        _f('household.ward', 'Ward', 0, (0.625, 0.139, 0.833, 0.156), 'printed'),
        _f('', 'Personnel', 0, (0.275, 0.156, 0.833, 0.172), 'printed', display='assigned_to'),
        _f('caregiver.id_type', 'Type of ID', 0, (0.348, 0.186, 0.372, 0.202), 'checkbox', option='SA ID Number', group='caregiver.id_type'),
        _f('caregiver.id_type', 'Type of ID', 0, (0.604, 0.186, 0.628, 0.202), 'checkbox', option='Passport Number', group='caregiver.id_type'),
        _f('caregiver.id_type', 'Type of ID', 0, (0.766, 0.186, 0.790, 0.202), 'checkbox', option='Permit', group='caregiver.id_type'),
        _id_cells('caregiver.id_number', 'ID Number', 0, 0.248, 0.208, 0.830, 0.228),
        _f('caregiver.headship_type', 'Headship', 0, (0.395, 0.248, 0.418, 0.264), 'checkbox', option='Parent Headed', group='caregiver.headship_type'),
        _f('caregiver.headship_type', 'Headship', 0, (0.655, 0.248, 0.678, 0.264), 'checkbox', option='Grand Parent Headed', group='caregiver.headship_type'),
        _f('caregiver.headship_type', 'Headship', 0, (0.395, 0.266, 0.418, 0.282), 'checkbox', option='Youth Headed', group='caregiver.headship_type'),
        _f('caregiver.headship_type', 'Headship', 0, (0.655, 0.266, 0.678, 0.282), 'checkbox', option='Child Headed', group='caregiver.headship_type'),
        _f('caregiver.headship_type', 'Headship', 0, (0.395, 0.284, 0.418, 0.300), 'checkbox', option='Relative Headed', group='caregiver.headship_type'),
        _f('caregiver.headship_type', 'Headship', 0, (0.655, 0.284, 0.678, 0.300), 'checkbox', option='Other', group='caregiver.headship_type'),
        _f('caregiver.name', 'Name', 0, (0.220, 0.305, 0.830, 0.322), 'handwrite'),
        _f('caregiver.surname', 'Surname', 0, (0.220, 0.324, 0.830, 0.340), 'handwrite'),
        _f('caregiver.known_as', 'Known As', 0, (0.220, 0.343, 0.830, 0.360), 'handwrite'),
        _f('caregiver.nationality', 'Nationality', 0, (0.413, 0.365, 0.440, 0.382), 'checkbox', option='South African', group='caregiver.nationality'),
        _f('caregiver.nationality', 'Nationality', 0, (0.529, 0.365, 0.556, 0.382), 'checkbox', option='Other', group='caregiver.nationality'),
        _f('caregiver.nationality', 'Describe', 0, (0.669, 0.363, 0.831, 0.379), 'handwrite', role='nationality_describe'),
        _f('caregiver.date_of_birth', 'Date of Birth', 0, (0.220, 0.384, 0.830, 0.405), 'date'),
        _f('caregiver.sex', 'Sex', 0, (0.292, 0.408, 0.318, 0.428), 'checkbox', option='Male', group='caregiver.sex'),
        _f('caregiver.sex', 'Sex', 0, (0.432, 0.406, 0.461, 0.430), 'checkbox', option='Female', group='caregiver.sex'),
        _f('caregiver.race', 'Race', 0, (0.292, 0.432, 0.317, 0.450), 'checkbox', option='African', group='caregiver.race'),
        _f('caregiver.race', 'Race', 0, (0.435, 0.432, 0.461, 0.450), 'checkbox', option='White', group='caregiver.race'),
        _f('caregiver.race', 'Race', 0, (0.592, 0.429, 0.622, 0.452), 'checkbox', option='Coloured', group='caregiver.race'),
        _f('caregiver.race', 'Race', 0, (0.755, 0.428, 0.786, 0.451), 'checkbox', option='Indian', group='caregiver.race'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.434, 0.458, 0.460, 0.476), 'checkbox', option='Married', group='caregiver.marital_status'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.592, 0.455, 0.621, 0.479), 'checkbox', option='Divorced', group='caregiver.marital_status'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.755, 0.454, 0.785, 0.479), 'checkbox', option='Widowed', group='caregiver.marital_status'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.434, 0.481, 0.460, 0.499), 'checkbox', option='Single', group='caregiver.marital_status'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.592, 0.478, 0.621, 0.502), 'checkbox', option='Cohabiting', group='caregiver.marital_status'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.755, 0.477, 0.785, 0.502), 'checkbox', option='Separated', group='caregiver.marital_status'),
        _f('caregiver.disability', 'Disability', 0, (0.289, 0.504, 0.315, 0.523), 'checkbox', option='false', group='caregiver.disability'),
        _f('caregiver.disability', 'Disability', 0, (0.434, 0.504, 0.459, 0.523), 'checkbox', option='true', group='caregiver.disability'),
        _f('caregiver.disability_description', 'Describe', 0, (0.597, 0.504, 0.830, 0.521), 'handwrite'),
        _f('caregiver.cell_number', 'Cell', 0, (0.220, 0.528, 0.830, 0.546), 'printed'),
        _f('caregiver.home_language', 'Home Language', 0, (0.250, 0.547, 0.830, 0.564), 'handwrite'),
        _f('caregiver.date_joined', 'Date Joined', 0, (0.220, 0.565, 0.830, 0.582), 'date'),
        _f('member.0.relationship_to_head', 'Relationship to Member 1', 0, (0.360, 0.585, 0.520, 0.606), 'handwrite'),
        _f('member.1.relationship_to_head', 'Relationship to Member 2', 0, (0.710, 0.585, 0.830, 0.606), 'handwrite'),
        _f('member.2.relationship_to_head', 'Relationship to Member 3', 0, (0.360, 0.609, 0.520, 0.627), 'handwrite'),
        _f('member.3.relationship_to_head', 'Relationship to Member 4', 0, (0.710, 0.609, 0.830, 0.627), 'handwrite'),
    ]
    c01 += _c01_member(0, 0, 0.635)
    c01 += _c01_member(1, 1, 0.052)
    c01 += _c01_member(1, 2, 0.298)
    c01 += _c01_member(1, 3, 0.541)

    intake = [
        _f('household.org_household_number', 'Intake Ref Number', 0, (0.700, 0.125, 0.935, 0.168), 'printed'),
        _f('caregiver.surname', 'Primary Client Surname', 0, (0.055, 0.198, 0.360, 0.238), 'handwrite'),
        _f('caregiver.name', 'Primary Client First name', 0, (0.360, 0.198, 0.640, 0.238), 'handwrite'),
        _f('caregiver.id_number', 'Primary Client ID Number / Date of Birth', 0, (0.640, 0.198, 0.935, 0.300), 'printed'),
        _f('', 'Caregiver Surname', 0, (0.055, 0.355, 0.360, 0.395), 'handwrite'),
        _f('', 'Caregiver First name', 0, (0.360, 0.355, 0.640, 0.395), 'handwrite'),
        _f('', 'Caregiver ID Number / Date of Birth', 0, (0.640, 0.355, 0.935, 0.430), 'printed'),
        _f('', 'Presenting problem(s) and expectations of the client', 0, (0.055, 0.500, 0.935, 0.900), 'narrative'),
        _f('', 'Primary Problem Code (see CW 06)', 1, (0.055, 0.355, 0.470, 0.410), 'printed'),
        _f('', 'Other Problem Codes', 1, (0.500, 0.355, 0.935, 0.410), 'printed'),
        _f('', 'Risk Level Emergency', 1, (0.355, 0.455, 0.385, 0.480), 'checkbox', option='Emergency'),
        _f('', 'Risk Level High', 1, (0.560, 0.455, 0.590, 0.480), 'checkbox', option='High'),
        _f('', 'Risk Level Mild', 1, (0.770, 0.455, 0.800, 0.480), 'checkbox', option='Mild'),
        _f('', 'Intake Action Emergency Action', 1, (0.430, 0.505, 0.455, 0.525), 'checkbox'),
        _f('', 'Do you consent to the recommended Intake Action above Yes', 2, (0.430, 0.095, 0.458, 0.118), 'checkbox', option='Yes'),
        _f('', 'Do you consent to the recommended Intake Action above No', 2, (0.500, 0.095, 0.528, 0.118), 'checkbox', option='No'),
        _f('', 'Open file', 2, (0.430, 0.805, 0.458, 0.828), 'checkbox', option='Open file'),
    ]

    c02 = [
        _f('caregiver.name', 'Name', 0, (0.12, 0.20, 0.48, 0.255), 'handwrite'),
        _f('caregiver.surname', 'Surname', 0, (0.12, 0.255, 0.48, 0.305), 'handwrite'),
        _f('household.org_household_number', 'Org Household Number', 0, (0.12, 0.305, 0.48, 0.355), 'printed'),
        _f('caregiver.nationality', 'Nationality', 0, (0.12, 0.355, 0.48, 0.400), 'handwrite'),
        _id_cells('caregiver.id_number', 'ID number', 0, 0.12, 0.400, 0.48, 0.455),
    ]
    c03 = [
        _f('caregiver.name', 'Name', 0, (0.18, 0.08, 0.42, 0.12), 'handwrite'),
        _f('caregiver.surname', 'Surname', 0, (0.18, 0.12, 0.42, 0.16), 'handwrite'),
        _f('household.org_household_number', 'HH number', 0, (0.18, 0.16, 0.42, 0.20), 'printed'),
        _f('caregiver.id_number', 'Beneficiary ID', 0, (0.18, 0.04, 0.42, 0.08), 'printed'),
    ]
    fcp = [
        _f('caregiver.surname', 'Family Name', 0, (0.08, 0.05, 0.34, 0.12), 'handwrite'),
        _f('household.org_household_number', 'Family Registration number', 0, (0.38, 0.05, 0.62, 0.12), 'printed'),
        _f('household.date_registered', 'Date of Registration', 0, (0.68, 0.05, 0.92, 0.12), 'date'),
    ]
    return {
        'c01': c01,
        'intake': intake,
        'c02': c02,
        'c03': c03,
        'family_care_plan': fcp,
        'process_note': [
            _f('process_note.client_surname', 'Client(s) Surname', 0, (0.28, 0.18, 0.50, 0.22), 'handwrite'),
            _f('process_note.client_first_name', 'Client(s) First name', 0, (0.72, 0.18, 0.94, 0.22), 'handwrite'),
            _f('process_note.client_id_number', 'Client(s) ID Number', 0, (0.28, 0.22, 0.50, 0.26), 'printed'),
            _f('process_note.file_no', 'File No', 0, (0.72, 0.22, 0.94, 0.26), 'printed'),
            _f('process_note.problem_code', 'Problem Code', 0, (0.28, 0.32, 0.50, 0.36), 'printed'),
            _f('process_note.intervention_code', 'Intervention Code', 0, (0.72, 0.32, 0.94, 0.36), 'printed'),
            _f('process_note.type_of_engagement', 'Office', 0, (0.28, 0.38, 0.31, 0.41), 'checkbox', option='Office', group='process_note.type_of_engagement'),
            _f('process_note.type_of_engagement', 'Home', 0, (0.38, 0.38, 0.41, 0.41), 'checkbox', option='Home', group='process_note.type_of_engagement'),
            _f('process_note.type_of_engagement', 'School', 0, (0.48, 0.38, 0.51, 0.41), 'checkbox', option='School', group='process_note.type_of_engagement'),
            _f('process_note.type_of_engagement', 'Court', 0, (0.58, 0.38, 0.61, 0.41), 'checkbox', option='Court', group='process_note.type_of_engagement'),
            _f('process_note.type_of_engagement', 'Telephone', 0, (0.70, 0.38, 0.73, 0.41), 'checkbox', option='Telephone', group='process_note.type_of_engagement'),
            _f('process_note.type_of_engagement', 'Other', 0, (0.84, 0.38, 0.87, 0.41), 'checkbox', option='Other', group='process_note.type_of_engagement'),
            _f('process_note.purpose_and_what_transpired', 'Purpose of engagement and what transpired', 0, (0.06, 0.46, 0.94, 0.62), 'narrative'),
        ],
    }


FIELDS = _build_fields()


def form_meta(code):
    meta = dict(ATLAS_FORMS.get(code) or {})
    meta['code'] = code
    meta['pages'] = page_count(code) or meta.get('pages') or 1
    meta['atlas_version'] = ATLAS_VERSION
    blanks = load_meta()['pages']
    meta['blanks'] = [blanks[f'{code}:{i}'] for i in range(meta['pages']) if f'{code}:{i}' in blanks]
    return meta


def fields_for(code, page=None):
    items = FIELDS.get(code) or []
    if page is None:
        return items
    return [f for f in items if f['page'] == page]


def has_geometry(code):
    return form_meta(code).get('geometry') == 'pdf' and bool(form_meta(code).get('blanks'))
