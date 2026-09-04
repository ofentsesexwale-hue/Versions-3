"""One field atlas for fill, print, and Scan Intake.

Boxes are normalised 0–1 on the official blank PNG (same file print uses).
C01 geometry is measured on Official_C01_Template.docx blanks. Other forms
still use the NPO PDF blanks. Do not rename field labels.
"""
from functools import lru_cache

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
        # Boxes measured on Official_C01_Template.docx blank PNGs (scale 2.0).
        'geometry': 'word',
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
        # C02 is the adult assessment of the C01 head of household
        # (caregiver), not an extra member. Other adults already sit on
        # C01 as member.N.
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
    'cow2_note': {
        'title': 'COW 02: Community Work Process Note',
        'official_title': 'COMMUNITY WORK PROCESS NOTE COW 02',
        'header': 'dsd',
        'orientation': 'portrait',
        'keywords': ['COW 02', 'COW 2', 'COMMUNITY WORK PROCESS NOTE', 'NAME OF COMMUNITY'],
        'checklist_item': ('process_note', 'SAW Process note - CW 11'),
        'geometry': 'pdf',
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


def _inset(box, x=0.04, y=0.18):
    """Shrink a cell so OCR and ink-fill see paper, not the printed ruling.

    Inset beats expand: a slightly small crop of the right cell is readable,
    a crop that includes the grid line is not.
    """
    x0, y0, x1, y1 = box
    dx = (x1 - x0) * x
    dy = (y1 - y0) * y
    nx0, ny0, nx1, ny1 = x0 + dx, y0 + dy, x1 - dx, y1 - dy
    if nx1 - nx0 < 0.012:
        nx0, nx1 = x0, x1
    if ny1 - ny0 < 0.005:
        ny0, ny1 = y0, y1
    return _box(nx0, ny0, nx1, ny1)


def _id_strip(box):
    """13-cell SA ID row: cover every cell and pad past the last ruling.

    RapidOCR drops the 13th digit when the crop ends on that cell's right
    edge. A small pad past the last grid line keeps the digit inside the
    picture without taking the passport grid that sits to the right.
    """
    x0, y0, x1, y1 = box
    return _inset((x0, y0, min(0.999, x1 + 0.014), y1), 0.018, 0.12)


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


def _c01_member(page, slot, id_ticks, id_box, name, surname, known, nationality, dob,
                sex_m, sex_f, race_a, race_w, race_c, race_i, dis_no, dis_yes, describe, joined, rel):
    """Member identity block. Boxes are the measured input rectangles on the blank PNG."""
    p = f'member.{slot}.'
    return [
        _f(p + 'id_type', 'Type of ID', page, id_ticks[0], 'checkbox', option='SA ID Number', group=p + 'id_type'),
        _f(p + 'id_type', 'Type of ID', page, id_ticks[1], 'checkbox', option='Passport Number', group=p + 'id_type'),
        _f(p + 'id_type', 'Type of ID', page, id_ticks[2], 'checkbox', option='Permit', group=p + 'id_type'),
        _id_cells(p + 'id_number', 'ID Number', page, *_word_cell(id_box, x=0.015)),
        _f(p + 'name', 'Name', page, _word_cell(name), 'handwrite'),
        _f(p + 'surname', 'Surname', page, _word_cell(surname), 'handwrite'),
        _f(p + 'known_as', 'Known As', page, _word_cell(known), 'handwrite'),
        _f(p + 'nationality', 'Nationality', page, _word_cell(nationality), 'handwrite'),
        _f(p + 'date_of_birth', 'Date of Birth', page, _word_cell(dob), 'date'),
        _f(p + 'sex', 'Sex', page, sex_m, 'checkbox', option='Male', group=p + 'sex'),
        _f(p + 'sex', 'Sex', page, sex_f, 'checkbox', option='Female', group=p + 'sex'),
        _f(p + 'race', 'Race', page, race_a, 'checkbox', option='African', group=p + 'race'),
        _f(p + 'race', 'Race', page, race_w, 'checkbox', option='White', group=p + 'race'),
        _f(p + 'race', 'Race', page, race_c, 'checkbox', option='Coloured', group=p + 'race'),
        _f(p + 'race', 'Race', page, race_i, 'checkbox', option='Indian', group=p + 'race'),
        _f(p + 'disability', 'Disability', page, dis_no, 'checkbox', option='false', group=p + 'disability'),
        _f(p + 'disability', 'Disability', page, dis_yes, 'checkbox', option='true', group=p + 'disability'),
        _f(p + 'disability_description', 'Describe', page, _word_cell(describe), 'handwrite'),
        _f(p + 'date_joined', 'Date Joined', page, _word_cell(joined), 'date'),
        _f(p + 'relationship_to_head', 'Relationship to Head of Household', page, _word_cell(rel), 'handwrite'),
    ]


def _word_cell(box, x=0.02, grow_top=0.0015, grow_bottom=0.0035):
    """Crop a Word-table value cell with a little vertical room for ink.

    Measured cells are ~25px tall and handwriting often touches both rulings.
    Growing mostly downward recovers names like Sisi Lettie without pulling as
    much ink from the row above (Known As stays empty via the ink gate).
    """
    x0, y0, x1, y1 = box
    y0 = max(0.0, y0 - grow_top)
    y1 = min(1.0, y1 + grow_bottom)
    dx = (x1 - x0) * x
    return _box(x0 + dx, y0, x1 - dx, y1)


def _build_fields():
    # Value cells measured on Official_C01_Template.docx blank PNGs (scale 2.0).
    # Left label column ends ~0.275; value cells run to ~0.967 (or mid for
    # the four-column address block).
    c01 = [
        _f('household.org_household_number', 'Org Household Nr', 0,
           _word_cell((0.2754, 0.1110, 0.5416, 0.1259)), 'printed'),
        _f('household.province', 'Province', 0,
           _word_cell((0.6952, 0.1110, 0.9673, 0.1259)), 'printed'),
        _f('household.house_number', 'House Number', 0,
           _word_cell((0.2754, 0.1277, 0.5416, 0.1431)), 'printed'),
        _f('household.district', 'District', 0,
           _word_cell((0.6952, 0.1277, 0.9673, 0.1431)), 'printed'),
        # Street handwriting often crosses the Municipality label divider.
        _f('household.street', 'Street', 0,
           _word_cell((0.2754, 0.1449, 0.6900, 0.1597), x=0.015), 'printed'),
        _f('household.municipality', 'Municipality', 0,
           _word_cell((0.6952, 0.1449, 0.9673, 0.1597)), 'printed'),
        _f('household.town', 'Town', 0,
           _word_cell((0.2754, 0.1615, 0.5416, 0.1764)), 'printed'),
        _f('household.ward', 'Ward', 0,
           _word_cell((0.6952, 0.1615, 0.9673, 0.1764)), 'printed'),
        _f('__display.personnel', 'Personnel', 0,
           _word_cell((0.2754, 0.1781, 0.9673, 0.1948)), 'printed'),
        _f('caregiver.id_type', 'Type of ID', 0, (0.3959, 0.2180, 0.4085, 0.2269), 'checkbox',
           option='SA ID Number', group='caregiver.id_type'),
        _f('caregiver.id_type', 'Type of ID', 0, (0.5743, 0.2180, 0.5869, 0.2269), 'checkbox',
           option='Passport Number', group='caregiver.id_type'),
        _f('caregiver.id_type', 'Type of ID', 0, (0.6709, 0.2180, 0.6835, 0.2269), 'checkbox',
           option='Permit', group='caregiver.id_type'),
        _id_cells('caregiver.id_number', 'ID Number', 0,
                  *_word_cell((0.2754, 0.2328, 0.7200, 0.2488), x=0.015)),
        _f('caregiver.organisation_beneficiary_number', 'Organisation beneficiary', 0,
           _word_cell((0.2754, 0.2506, 0.9673, 0.2785)), 'printed'),
        _f('caregiver.headship_type', 'Headship', 0, (0.4005, 0.2821, 0.4131, 0.2912), 'checkbox',
           option='Parent Headed', group='caregiver.headship_type'),
        _f('caregiver.headship_type', 'Headship', 0, (0.6130, 0.2821, 0.6255, 0.2912), 'checkbox',
           option='Grand Parent Headed', group='caregiver.headship_type'),
        _f('caregiver.headship_type', 'Headship', 0, (0.7679, 0.2821, 0.7805, 0.2912), 'checkbox',
           option='Youth Headed', group='caregiver.headship_type'),
        _f('caregiver.headship_type', 'Headship', 0, (0.3896, 0.2949, 0.4022, 0.3040), 'checkbox',
           option='Child Headed', group='caregiver.headship_type'),
        _f('caregiver.headship_type', 'Headship', 0, (0.5613, 0.2949, 0.5739, 0.3040), 'checkbox',
           option='Relative Headed', group='caregiver.headship_type'),
        _f('caregiver.headship_type', 'Headship', 0, (0.6512, 0.2949, 0.6638, 0.3040), 'checkbox',
           option='Other', group='caregiver.headship_type'),
        _f('caregiver.name', 'Name', 0,
           _word_cell((0.2754, 0.3094, 0.9673, 0.3242)), 'handwrite'),
        _f('caregiver.surname', 'Surname', 0,
           _word_cell((0.2754, 0.3260, 0.9673, 0.3414)), 'handwrite'),
        _f('caregiver.known_as', 'Known As', 0,
           _word_cell((0.2754, 0.3432, 0.9673, 0.3581)), 'handwrite'),
        _f('caregiver.nationality', 'Nationality', 0, (0.3888, 0.3618, 0.4014, 0.3710), 'checkbox',
           option='South African', group='caregiver.nationality'),
        _f('caregiver.nationality', 'Nationality', 0, (0.4782, 0.3618, 0.4908, 0.3710), 'checkbox',
           option='Other', group='caregiver.nationality'),
        _f('caregiver.nationality', 'Describe', 0,
           _word_cell((0.5200, 0.3599, 0.9673, 0.3747)), 'handwrite', role='nationality_describe'),
        _f('caregiver.date_of_birth', 'Date of Birth', 0,
           _word_cell((0.2754, 0.3771, 0.9673, 0.3919)), 'date'),
        _f('caregiver.sex', 'Sex', 0, (0.3241, 0.3960, 0.3367, 0.4046), 'checkbox',
           option='Male', group='caregiver.sex'),
        _f('caregiver.sex', 'Sex', 0, (0.4513, 0.3960, 0.4639, 0.4046), 'checkbox',
           option='Female', group='caregiver.sex'),
        _f('caregiver.race', 'Race', 0, (0.3401, 0.4132, 0.3527, 0.4218), 'checkbox',
           option='African', group='caregiver.race'),
        _f('caregiver.race', 'Race', 0, (0.4307, 0.4132, 0.4433, 0.4218), 'checkbox',
           option='White', group='caregiver.race'),
        _f('caregiver.race', 'Race', 0, (0.5466, 0.4132, 0.5592, 0.4218), 'checkbox',
           option='Coloured', group='caregiver.race'),
        _f('caregiver.race', 'Race', 0, (0.6398, 0.4132, 0.6524, 0.4218), 'checkbox',
           option='Indian', group='caregiver.race'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.3447, 0.4294, 0.3573, 0.4383), 'checkbox',
           option='Married', group='caregiver.marital_status'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.4618, 0.4294, 0.4744, 0.4383), 'checkbox',
           option='Divorced', group='caregiver.marital_status'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.5756, 0.4294, 0.5882, 0.4383), 'checkbox',
           option='Widowed', group='caregiver.marital_status'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.3342, 0.4418, 0.3468, 0.4507), 'checkbox',
           option='Single', group='caregiver.marital_status'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.4626, 0.4418, 0.4752, 0.4507), 'checkbox',
           option='Cohabiting', group='caregiver.marital_status'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.5785, 0.4418, 0.5911, 0.4507), 'checkbox',
           option='Separated', group='caregiver.marital_status'),
        _f('caregiver.disability', 'Disability', 0, (0.3090, 0.4585, 0.3216, 0.4674), 'checkbox',
           option='false', group='caregiver.disability'),
        _f('caregiver.disability', 'Disability', 0, (0.3858, 0.4585, 0.3984, 0.4674), 'checkbox',
           option='true', group='caregiver.disability'),
        _f('caregiver.disability_description', 'Describe', 0,
           _word_cell((0.5000, 0.4567, 0.9673, 0.4715)), 'handwrite'),
        _f('caregiver.cell_number', 'Cell', 0,
           _word_cell((0.2754, 0.4739, 0.9673, 0.4887)), 'printed'),
        _f('caregiver.home_language', 'Home Language', 0,
           _word_cell((0.2754, 0.4905, 0.9673, 0.5053)), 'handwrite'),
        _f('caregiver.date_joined', 'Date Joined', 0,
           _word_cell((0.2754, 0.5071, 0.9673, 0.5226)), 'date'),
        # Relationship-to-member line: one Word cell, four handwriting slots.
        _f('member.0.relationship_to_head', 'Relationship to Member 1', 0,
           _word_cell((0.4000, 0.5243, 0.6000, 0.5380)), 'handwrite'),
        _f('member.1.relationship_to_head', 'Relationship to Member 2', 0,
           _word_cell((0.7000, 0.5243, 0.9500, 0.5380)), 'handwrite'),
        _f('member.2.relationship_to_head', 'Relationship to Member 3', 0,
           _word_cell((0.4000, 0.5380, 0.6000, 0.5517)), 'handwrite'),
        _f('member.3.relationship_to_head', 'Relationship to Member 4', 0,
           _word_cell((0.7000, 0.5380, 0.9500, 0.5517)), 'handwrite'),
    ]
    c01 += _c01_member(
        0, 0,
        ((0.3959, 0.5753, 0.4085, 0.5839), (0.5743, 0.5753, 0.5869, 0.5839), (0.6709, 0.5753, 0.6835, 0.5839)),
        (0.2754, 0.5897, 0.7200, 0.6057),
        (0.2754, 0.6075, 0.9673, 0.6229),
        (0.2754, 0.6247, 0.9673, 0.6395),
        (0.2754, 0.6413, 0.9673, 0.6568),
        (0.2754, 0.6586, 0.9673, 0.6734),
        (0.2754, 0.6752, 0.9673, 0.6900),
        (0.3241, 0.6948, 0.3367, 0.7036), (0.4513, 0.6948, 0.4639, 0.7036),
        (0.3401, 0.7113, 0.3527, 0.7199), (0.4307, 0.7113, 0.4433, 0.7199),
        (0.5466, 0.7113, 0.5592, 0.7199), (0.6398, 0.7113, 0.6524, 0.7199),
        (0.3090, 0.7281, 0.3216, 0.7370), (0.3858, 0.7281, 0.3984, 0.7370),
        (0.5000, 0.7257, 0.9673, 0.7411),
        (0.2754, 0.7429, 0.9673, 0.7577),
        (0.2754, 0.7595, 0.9673, 0.7868),
    )
    # Page 1: Add member 2 / 3 / 4 tables (same column geometry, stacked).
    c01 += _c01_member(
        1, 1,
        ((0.3959, 0.1122, 0.4085, 0.1209), (0.5743, 0.1122, 0.5869, 0.1209), (0.6709, 0.1122, 0.6835, 0.1209)),
        (0.2754, 0.1265, 0.7200, 0.1431),
        (0.2754, 0.1449, 0.9673, 0.1597),
        (0.2754, 0.1615, 0.9673, 0.1764),
        (0.2754, 0.1781, 0.9673, 0.1936),
        (0.2754, 0.1954, 0.9673, 0.2102),
        (0.2754, 0.2120, 0.9673, 0.2274),
        (0.3241, 0.2315, 0.3367, 0.2403), (0.4513, 0.2315, 0.4639, 0.2403),
        (0.3401, 0.2481, 0.3527, 0.2567), (0.4307, 0.2481, 0.4433, 0.2567),
        (0.5466, 0.2481, 0.5592, 0.2567), (0.6398, 0.2481, 0.6524, 0.2567),
        (0.3090, 0.2654, 0.3216, 0.2743), (0.3858, 0.2654, 0.3984, 0.2743),
        (0.5000, 0.2625, 0.9673, 0.2779),
        (0.2754, 0.2797, 0.9673, 0.2945),
        (0.2754, 0.2963, 0.9673, 0.3118),
    )
    c01 += _c01_member(
        1, 2,
        ((0.3959, 0.3521, 0.4085, 0.3608), (0.5743, 0.3521, 0.5869, 0.3608), (0.6709, 0.3521, 0.6835, 0.3608)),
        (0.2754, 0.3664, 0.7200, 0.3824),
        (0.2754, 0.3848, 0.9673, 0.3996),
        (0.2754, 0.4014, 0.9673, 0.4163),
        (0.2754, 0.4181, 0.9673, 0.4335),
        (0.2754, 0.4353, 0.9673, 0.4501),
        (0.2754, 0.4519, 0.9673, 0.4667),
        (0.3241, 0.4714, 0.3367, 0.4802), (0.4513, 0.4714, 0.4639, 0.4802),
        (0.3401, 0.4880, 0.3527, 0.4966), (0.4307, 0.4880, 0.4433, 0.4966),
        (0.5466, 0.4880, 0.5592, 0.4966), (0.6398, 0.4880, 0.6524, 0.4966),
        (0.3090, 0.5047, 0.3216, 0.5136), (0.3858, 0.5047, 0.3984, 0.5136),
        (0.5000, 0.5024, 0.9673, 0.5178),
        (0.2754, 0.5196, 0.9673, 0.5344),
        (0.2754, 0.5362, 0.9673, 0.5511),
    )
    c01 += _c01_member(
        1, 3,
        ((0.3959, 0.5920, 0.4085, 0.6007), (0.5743, 0.5920, 0.5869, 0.6007), (0.6709, 0.5920, 0.6835, 0.6007)),
        (0.2754, 0.6063, 0.7200, 0.6223),
        (0.2754, 0.6241, 0.9673, 0.6395),
        (0.2754, 0.6413, 0.9673, 0.6562),
        (0.2754, 0.6580, 0.9673, 0.6734),
        (0.2754, 0.6752, 0.9673, 0.6900),
        (0.2754, 0.6918, 0.9673, 0.7067),
        (0.3241, 0.7107, 0.3367, 0.7195), (0.4513, 0.7107, 0.4639, 0.7195),
        (0.3401, 0.7280, 0.3527, 0.7366), (0.4307, 0.7280, 0.4433, 0.7366),
        (0.5466, 0.7280, 0.5592, 0.7366), (0.6398, 0.7280, 0.6524, 0.7366),
        (0.3090, 0.7446, 0.3216, 0.7535), (0.3858, 0.7446, 0.3984, 0.7535),
        (0.5000, 0.7423, 0.9673, 0.7577),
        (0.2754, 0.7595, 0.9673, 0.7743),
        (0.2754, 0.7761, 0.9673, 0.7910),
    )

    intake = [
        _f('household.org_household_number', 'Intake Ref Number', 0, (0.6891, 0.1057, 0.9235, 0.1366), 'printed'),
        _f('caregiver.surname', 'Primary Client Surname', 0, (0.0874, 0.1663, 0.3664, 0.1960), 'handwrite'),
        _f('caregiver.name', 'Primary Client First name', 0, (0.3664, 0.1681, 0.6891, 0.1977), 'handwrite'),
        _f('caregiver.id_number', 'Primary Client ID Number / Date of Birth', 0, (0.6891, 0.1704, 0.9235, 0.1989), 'printed'),
        _f('', 'Caregiver Surname', 0, (0.0874, 0.3593, 0.3655, 0.3884), 'handwrite'),
        _f('', 'Caregiver First name', 0, (0.3655, 0.3610, 0.6882, 0.3901), 'handwrite'),
        _f('', 'Caregiver ID Number / Date of Birth', 0, (0.6882, 0.3628, 0.9235, 0.3913), 'printed'),
        _f('', 'Presenting problem(s) and expectations of the client', 0, (0.0866, 0.4513, 0.9227, 0.8486), 'narrative'),
        _f('', 'Primary Problem Code (see CW 06)', 1, (0.0866, 0.4608, 0.3311, 0.4970), 'printed'),
        _f('', 'Other Problem Codes', 1, (0.3311, 0.4620, 0.9227, 0.5000), 'printed'),
        _f('', 'Risk Level Emergency', 1, (0.3403, 0.4679, 0.3521, 0.4757), 'checkbox', option='Emergency'),
        _f('', 'Risk Level High', 1, (0.5370, 0.4691, 0.5487, 0.4768), 'checkbox', option='High'),
        _f('', 'Risk Level Mild', 1, (0.7345, 0.4697, 0.7454, 0.4780), 'checkbox', option='Mild'),
        _f('', 'Intake Action Emergency Action', 1, (0.3403, 0.5178, 0.3529, 0.5267), 'checkbox'),
        _f('', 'Do you consent to the recommended Intake Action above Yes', 2, (0.3412, 0.0926, 0.3538, 0.1015), 'checkbox', option='Yes'),
        _f('', 'Do you consent to the recommended Intake Action above No', 2, (0.3412, 0.1063, 0.3538, 0.1152), 'checkbox', option='No'),
        _f('', 'Open file', 2, (0.3714, 0.8195, 0.3832, 0.8284), 'checkbox', option='Open file'),
    ]

    cow2 = [
        _f('household.org_household_number', 'Ref No', 0, (0.8237, 0.1099, 0.9622, 0.1395), 'printed'),
        _f('household.town', 'Name of Community', 0, (0.5097, 0.1395, 0.6650, 0.1692), 'printed'),
        _f('__display.personnel', 'Name', 1, (0.0369, 0.1229, 0.3518, 0.1425), 'printed'),
    ]

    c02 = [
        _f('__display.organisation', 'Organisation', 0,
           _inset((0.1574, 0.2090, 0.3290, 0.2261), 0.04, 0.16), 'printed'),
        _f('caregiver.name', 'Name', 0,
           _inset((0.1574, 0.2429, 0.3290, 0.2597), 0.04, 0.16), 'handwrite'),
        _f('caregiver.surname', 'Surname', 0,
           _inset((0.1556, 0.2589, 0.3290, 0.2765), 0.04, 0.16), 'handwrite'),
        _f('household.org_household_number', 'Org Household Number', 0,
           _inset((0.1544, 0.2757, 0.3284, 0.3102), 0.04, 0.12), 'printed'),
        _f('caregiver.nationality', 'Nationality', 0,
           _inset((0.1544, 0.3093, 0.3278, 0.3262), 0.04, 0.16), 'handwrite'),
        _id_cells('caregiver.id_number', 'ID number', 0,
                  *_inset((0.1538, 0.3253, 0.3278, 0.3464), 0.03, 0.12)),
    ]
    # C03 is the child beneficiary sheet. Identity writes to a member slot
    # (allocated at save), never to caregiver.* — that is the head of household
    # on C01 / the adult on C02.
    c03 = [
        _f('__display.cycw_name', 'CYCW/CCG Name', 0,
           _inset((0.1835, 0.1540, 0.4994, 0.1690), 0.03, 0.10), 'handwrite'),
        _f('member.0.id_number', 'Beneficiary ID', 0,
           _inset((0.1829, 0.1700, 0.4994, 0.1850), 0.03, 0.10), 'sa_id'),
        _f('member.0.name', 'Name', 0,
           _inset((0.1823, 0.1860, 0.4988, 0.2015), 0.03, 0.10), 'handwrite'),
        _f('member.0.surname', 'Surname', 0,
           _inset((0.1817, 0.2018, 0.4988, 0.2180), 0.03, 0.10), 'handwrite'),
        _f('household.org_household_number', 'HH number', 0,
           _inset((0.1811, 0.2180, 0.4988, 0.2340), 0.03, 0.10), 'printed'),
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
        'cow2_note': cow2,
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
    geo = form_meta(code).get('geometry')
    return geo in ('pdf', 'word') and bool(form_meta(code).get('blanks'))


@lru_cache(maxsize=64)
def atlas_coverage(code):
    """(measured geometry?, every target this sheet can be read box by box).

    Lets the full-page keyword fallback tell a sheet it can read field by field
    from one it can only scrape, without every caller working it out. A form
    with boxes but no official blank to align to reads nothing from them, so it
    reports no covered targets and the scraper stays in play.
    """
    covered = has_geometry(code)
    if not covered:
        return False, frozenset()
    return True, frozenset(f['target'] for f in fields_for(code) if f.get('target'))
