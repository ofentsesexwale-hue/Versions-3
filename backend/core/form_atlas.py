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
        _id_cells(p + 'id_number', 'ID Number', page, *id_box),
        _f(p + 'name', 'Name', page, name, 'handwrite'),
        _f(p + 'surname', 'Surname', page, surname, 'handwrite'),
        _f(p + 'known_as', 'Known As', page, known, 'handwrite'),
        _f(p + 'nationality', 'Nationality', page, nationality, 'handwrite'),
        _f(p + 'date_of_birth', 'Date of Birth', page, dob, 'date'),
        _f(p + 'sex', 'Sex', page, sex_m, 'checkbox', option='Male', group=p + 'sex'),
        _f(p + 'sex', 'Sex', page, sex_f, 'checkbox', option='Female', group=p + 'sex'),
        _f(p + 'race', 'Race', page, race_a, 'checkbox', option='African', group=p + 'race'),
        _f(p + 'race', 'Race', page, race_w, 'checkbox', option='White', group=p + 'race'),
        _f(p + 'race', 'Race', page, race_c, 'checkbox', option='Coloured', group=p + 'race'),
        _f(p + 'race', 'Race', page, race_i, 'checkbox', option='Indian', group=p + 'race'),
        _f(p + 'disability', 'Disability', page, dis_no, 'checkbox', option='false', group=p + 'disability'),
        _f(p + 'disability', 'Disability', page, dis_yes, 'checkbox', option='true', group=p + 'disability'),
        _f(p + 'disability_description', 'Describe', page, describe, 'handwrite'),
        _f(p + 'date_joined', 'Date Joined', page, joined, 'date'),
        _f(p + 'relationship_to_head', 'Relationship to Head of Household', page, rel, 'handwrite'),
    ]


def _build_fields():
    c01 = [
        _f('household.org_household_number', 'Org Household Nr', 0, (0.2790, 0.0926, 0.4891, 0.1105), 'printed'),
        _f('household.province', 'Province', 0, (0.6277, 0.0914, 0.8336, 0.1081), 'printed'),
        _f('household.house_number', 'House Number', 0, (0.2782, 0.1099, 0.4891, 0.1259), 'printed'),
        _f('household.district', 'District', 0, (0.6277, 0.1087, 0.8336, 0.1235), 'printed'),
        _f('household.street', 'Street', 0, (0.2782, 0.1253, 0.4882, 0.1413), 'printed'),
        _f('household.municipality', 'Municipality', 0, (0.6277, 0.1235, 0.8336, 0.1390), 'printed'),
        _f('household.town', 'Town', 0, (0.2773, 0.1407, 0.4882, 0.1568), 'printed'),
        _f('household.ward', 'Ward', 0, (0.6269, 0.1390, 0.8336, 0.1544), 'printed'),
        _f('__display.personnel', 'Personnel', 0, (0.2765, 0.1544, 0.8336, 0.1728), 'printed'),
        _f('caregiver.id_type', 'Type of ID', 0, (0.3681, 0.1871, 0.3899, 0.2025), 'checkbox', option='SA ID Number', group='caregiver.id_type'),
        _f('caregiver.id_type', 'Type of ID', 0, (0.6034, 0.1859, 0.6261, 0.2013), 'checkbox', option='Passport Number', group='caregiver.id_type'),
        _f('caregiver.id_type', 'Type of ID', 0, (0.7655, 0.1853, 0.7874, 0.2001), 'checkbox', option='Permit', group='caregiver.id_type'),
        _id_cells('caregiver.id_number', 'ID Number', 0, 0.2462, 0.2084, 0.6252, 0.2280),
        _f('caregiver.headship_type', 'Headship', 0, (0.4176, 0.2464, 0.4395, 0.2637), 'checkbox', option='Parent Headed', group='caregiver.headship_type'),
        _f('caregiver.headship_type', 'Headship', 0, (0.7647, 0.2435, 0.7866, 0.2613), 'checkbox', option='Grand Parent Headed', group='caregiver.headship_type'),
        _f('caregiver.headship_type', 'Headship', 0, (0.4168, 0.2643, 0.4395, 0.2821), 'checkbox', option='Youth Headed', group='caregiver.headship_type'),
        _f('caregiver.headship_type', 'Headship', 0, (0.7639, 0.2619, 0.7866, 0.2791), 'checkbox', option='Child Headed', group='caregiver.headship_type'),
        _f('caregiver.headship_type', 'Headship', 0, (0.4168, 0.2821, 0.4387, 0.2999), 'checkbox', option='Relative Headed', group='caregiver.headship_type'),
        _f('caregiver.headship_type', 'Headship', 0, (0.7639, 0.2797, 0.7866, 0.2975), 'checkbox', option='Other', group='caregiver.headship_type'),
        _f('caregiver.name', 'Name', 0, (0.2437, 0.3029, 0.7857, 0.3219), 'handwrite'),
        _f('caregiver.surname', 'Surname', 0, (0.2429, 0.3207, 0.7857, 0.3403), 'handwrite'),
        _f('caregiver.known_as', 'Known As', 0, (0.2429, 0.3385, 0.7849, 0.3599), 'handwrite'),
        _f('caregiver.nationality', 'Nationality', 0, (0.4134, 0.3646, 0.4387, 0.3818), 'checkbox', option='South African', group='caregiver.nationality'),
        _f('caregiver.nationality', 'Nationality', 0, (0.5277, 0.3640, 0.5538, 0.3818), 'checkbox', option='Other', group='caregiver.nationality'),
        _f('caregiver.nationality', 'Describe', 0, (0.6689, 0.3628, 0.8319, 0.3800), 'handwrite', role='nationality_describe'),
        _f('caregiver.date_of_birth', 'Date of Birth', 0, (0.2395, 0.3854, 0.6697, 0.4032), 'date'),
        _f('caregiver.sex', 'Sex', 0, (0.2916, 0.4080, 0.3176, 0.4276), 'checkbox', option='Male', group='caregiver.sex'),
        _f('caregiver.sex', 'Sex', 0, (0.4353, 0.4080, 0.4613, 0.4281), 'checkbox', option='Female', group='caregiver.sex'),
        _f('caregiver.race', 'Race', 0, (0.2908, 0.4317, 0.3168, 0.4501), 'checkbox', option='African', group='caregiver.race'),
        _f('caregiver.race', 'Race', 0, (0.4345, 0.4317, 0.4605, 0.4501), 'checkbox', option='White', group='caregiver.race'),
        _f('caregiver.race', 'Race', 0, (0.5958, 0.4311, 0.6218, 0.4495), 'checkbox', option='Coloured', group='caregiver.race'),
        _f('caregiver.race', 'Race', 0, (0.7588, 0.4305, 0.7857, 0.4489), 'checkbox', option='Indian', group='caregiver.race'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.4345, 0.4572, 0.4605, 0.4762), 'checkbox', option='Married', group='caregiver.marital_status'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.5958, 0.4572, 0.6218, 0.4762), 'checkbox', option='Divorced', group='caregiver.marital_status'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.7588, 0.4561, 0.7849, 0.4757), 'checkbox', option='Widowed', group='caregiver.marital_status'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.4336, 0.4804, 0.4597, 0.5000), 'checkbox', option='Single', group='caregiver.marital_status'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.5950, 0.4804, 0.6210, 0.4994), 'checkbox', option='Cohabiting', group='caregiver.marital_status'),
        _f('caregiver.marital_status', 'Marital Status', 0, (0.7588, 0.4798, 0.7849, 0.4988), 'checkbox', option='Separated', group='caregiver.marital_status'),
        _f('caregiver.disability', 'Disability', 0, (0.2890, 0.5040, 0.3150, 0.5230), 'checkbox', option='false', group='caregiver.disability'),
        _f('caregiver.disability', 'Disability', 0, (0.4340, 0.5040, 0.4590, 0.5230), 'checkbox', option='true', group='caregiver.disability'),
        _f('caregiver.disability_description', 'Describe', 0, (0.5966, 0.5036, 0.8311, 0.5208), 'handwrite'),
        _f('caregiver.cell_number', 'Cell', 0, (0.2664, 0.5267, 0.7832, 0.5457), 'printed'),
        _f('caregiver.home_language', 'Home Language', 0, (0.2655, 0.5445, 0.7832, 0.5635), 'handwrite'),
        _f('caregiver.date_joined', 'Date Joined', 0, (0.2647, 0.5624, 0.7832, 0.5808), 'date'),
        _f('member.0.relationship_to_head', 'Relationship to Member 1', 0, (0.3798, 0.5849, 0.5739, 0.6057), 'handwrite'),
        _f('member.1.relationship_to_head', 'Relationship to Member 2', 0, (0.7126, 0.5855, 0.8311, 0.6033), 'handwrite'),
        _f('member.2.relationship_to_head', 'Relationship to Member 3', 0, (0.3790, 0.6087, 0.5739, 0.6271), 'handwrite'),
        _f('member.3.relationship_to_head', 'Relationship to Member 4', 0, (0.7126, 0.6093, 0.8311, 0.6247), 'handwrite'),
    ]
    c01 += _c01_member(
        0, 0,
        ((0.3563, 0.6496, 0.3790, 0.6675), (0.5958, 0.6485, 0.6185, 0.6657), (0.7597, 0.6479, 0.7832, 0.6651)),
        (0.2319, 0.6728, 0.5479, 0.6912),
        (0.2311, 0.6894, 0.7824, 0.7078),
        (0.2311, 0.7067, 0.7824, 0.7245),
        (0.2303, 0.7227, 0.7824, 0.7405),
        (0.2303, 0.7387, 0.7824, 0.7565),
        (0.2294, 0.7542, 0.7815, 0.7726),
        (0.2807, 0.7767, 0.3067, 0.7957), (0.5681, 0.7755, 0.5950, 0.7945),
        (0.2798, 0.7987, 0.3059, 0.8171), (0.4025, 0.7981, 0.4286, 0.8171),
        (0.5681, 0.7975, 0.5941, 0.8159), (0.7563, 0.7957, 0.7832, 0.8147),
        (0.2790, 0.8207, 0.3059, 0.8403), (0.4017, 0.8207, 0.4286, 0.8403),
        (0.5454, 0.8195, 0.8286, 0.8385),
        (0.2277, 0.8426, 0.8277, 0.8628),
        (0.4269, 0.8605, 0.8277, 0.8800),
    )
    c01 += _c01_member(
        1, 1,
        ((0.3891, 0.0683, 0.4109, 0.0867), (0.6235, 0.0695, 0.6454, 0.0873), (0.7824, 0.0713, 0.8042, 0.0891)),
        (0.2672, 0.0938, 0.6454, 0.1122),
        (0.2664, 0.1116, 0.8050, 0.1289),
        (0.2664, 0.1277, 0.8050, 0.1437),
        (0.2664, 0.1431, 0.8050, 0.1591),
        (0.2655, 0.1586, 0.8059, 0.1746),
        (0.2655, 0.1740, 0.8059, 0.1894),
        (0.3160, 0.1942, 0.3412, 0.2114), (0.5983, 0.1942, 0.6244, 0.2120),
        (0.3151, 0.2150, 0.3412, 0.2334), (0.4361, 0.2156, 0.4613, 0.2340),
        (0.5975, 0.2156, 0.6235, 0.2340), (0.7824, 0.2150, 0.8076, 0.2334),
        (0.3151, 0.2399, 0.3403, 0.2583), (0.4353, 0.2405, 0.4613, 0.2595),
        (0.5765, 0.2411, 0.8513, 0.2577),
        (0.2639, 0.2654, 0.8513, 0.2815),
        (0.2639, 0.2809, 0.8513, 0.2987),
    )
    c01 += _c01_member(
        1, 2,
        ((0.3857, 0.3147, 0.4084, 0.3302), (0.6210, 0.3153, 0.6437, 0.3302), (0.7824, 0.3141, 0.8050, 0.3296)),
        (0.2630, 0.3361, 0.6429, 0.3545),
        (0.2630, 0.3539, 0.8042, 0.3700),
        (0.2630, 0.3694, 0.8042, 0.3854),
        (0.2630, 0.3848, 0.8042, 0.4014),
        (0.2622, 0.4008, 0.8042, 0.4169),
        (0.2622, 0.4163, 0.8042, 0.4323),
        (0.3134, 0.4388, 0.3387, 0.4561), (0.5950, 0.4382, 0.6202, 0.4561),
        (0.3126, 0.4614, 0.3387, 0.4798), (0.4336, 0.4614, 0.4597, 0.4792),
        (0.5950, 0.4608, 0.6202, 0.4792), (0.7790, 0.4602, 0.8059, 0.4786),
        (0.3126, 0.4887, 0.3378, 0.5071), (0.4328, 0.4881, 0.4588, 0.5065),
        (0.5731, 0.4881, 0.8513, 0.5053),
        (0.2605, 0.5089, 0.8513, 0.5261),
        (0.2597, 0.5243, 0.8513, 0.5416),
    )
    c01 += _c01_member(
        1, 3,
        ((0.3832, 0.5570, 0.4059, 0.5724), (0.6193, 0.5564, 0.6420, 0.5713), (0.7815, 0.5558, 0.8042, 0.5707)),
        (0.2588, 0.5819, 0.6420, 0.6004),
        (0.2580, 0.5980, 0.8042, 0.6164),
        (0.2580, 0.6134, 0.8042, 0.6324),
        (0.2580, 0.6295, 0.8042, 0.6485),
        (0.2571, 0.6455, 0.8042, 0.6645),
        (0.2571, 0.6615, 0.8042, 0.6805),
        (0.3084, 0.6882, 0.3345, 0.7061), (0.5950, 0.6859, 0.6210, 0.7043),
        (0.3076, 0.7108, 0.3345, 0.7298), (0.4303, 0.7096, 0.4563, 0.7286),
        (0.5941, 0.7090, 0.6210, 0.7274), (0.7798, 0.7067, 0.8059, 0.7257),
        (0.3076, 0.7381, 0.3336, 0.7577), (0.4294, 0.7369, 0.4563, 0.7565),
        (0.5731, 0.7346, 0.8504, 0.7542),
        (0.2555, 0.7595, 0.8504, 0.7803),
        (0.2555, 0.7749, 0.8504, 0.7975),
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
        _f('', 'Risk Level Emergency', 1, (0.6496, 0.5606, 0.6756, 0.5707), 'checkbox', option='Emergency'),
        _f('', 'Risk Level High', 1, (0.7723, 0.5612, 0.7958, 0.5695), 'checkbox', option='High'),
        _f('', 'Risk Level Mild', 1, (0.8899, 0.5618, 0.9109, 0.5719), 'checkbox', option='Mild'),
        _f('', 'Intake Action Emergency Action', 1, (0.3580, 0.6556, 0.3782, 0.6645), 'checkbox'),
        _f('', 'Do you consent to the recommended Intake Action above Yes', 2, (0.3580, 0.0938, 0.3790, 0.1021), 'checkbox', option='Yes'),
        _f('', 'Do you consent to the recommended Intake Action above No', 2, (0.2160, 0.0962, 0.2378, 0.1045), 'checkbox', option='No'),
        _f('', 'Open file', 2, (0.3882, 0.8207, 0.4218, 0.8302), 'checkbox', option='Open file'),
    ]

    cow2 = [
        _f('household.org_household_number', 'Ref No', 0, (0.8237, 0.1099, 0.9622, 0.1395), 'printed'),
        _f('household.town', 'Name of Community', 0, (0.5097, 0.1395, 0.6650, 0.1692), 'printed'),
        _f('__display.personnel', 'Name', 1, (0.0369, 0.1229, 0.3518, 0.1425), 'printed'),
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
    return form_meta(code).get('geometry') == 'pdf' and bool(form_meta(code).get('blanks'))
