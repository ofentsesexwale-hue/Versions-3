"""Choice definitions shared across the data model."""

ID_TYPE_CHOICES = [
    ('SA ID Number', 'SA ID Number'),
    ('Passport Number', 'Passport Number'),
    ('Permit', 'Permit'),
]

SEX_CHOICES = [
    ('Male', 'Male'),
    ('Female', 'Female'),
]

RACE_CHOICES = [
    ('African', 'African'),
    ('White', 'White'),
    ('Coloured', 'Coloured'),
    ('Indian', 'Indian'),
    ('Other', 'Other'),
]

MARITAL_STATUS_CHOICES = [
    ('Married', 'Married'),
    ('Divorced', 'Divorced'),
    ('Widowed', 'Widowed'),
    ('Single', 'Single'),
    ('Cohabiting', 'Cohabiting'),
    ('Separated', 'Separated'),
]

HEADSHIP_TYPE_CHOICES = [
    ('Parent Headed', 'Parent Headed'),
    ('Grand Parent Headed', 'Grand Parent Headed'),
    ('Youth Headed', 'Youth Headed'),
    ('Child Headed', 'Child Headed'),
    ('Relative Headed', 'Relative Headed'),
    ('Other', 'Other'),
]

# Document / checklist categories (shared).
CATEGORY_CHOICES = [
    ('intake_form', 'Intake Forms'),
    ('family_care_plan', 'Family Care Plans'),
    ('vital_document', 'Vital Documents'),
    ('process_note', 'Process Notes'),
    ('school_report', 'School Visit Reports'),
    ('referral_form', 'Referral Forms'),
    ('success_story', 'Success Stories'),
    ('monthly_report', 'Monthly Reports'),
]

HAS_EVIDENCE_CHOICES = [
    ('Yes', 'Yes'),
    ('No', 'No'),
    ('', 'Unknown'),
]

AUDIT_ACTIONS = [
    ('viewed', 'viewed'),
    ('created', 'created'),
    ('edited', 'edited'),
    ('deleted', 'deleted'),
    ('downloaded', 'downloaded'),
    ('printed', 'printed'),
    ('confirmed', 'confirmed'),
    ('suggested', 'suggested'),
]

# Standard checklist template mirroring the physical NPO case file checklist.
# (category_key, sub_item) pairs.
CHECKLIST_TEMPLATE = [
    ('intake_form', 'C01'),
    ('intake_form', 'C02'),
    ('intake_form', 'C03'),
    ('intake_form', 'CW05'),
    ('family_care_plan', 'Family Care Plan'),
    ('family_care_plan', 'Contract between family and organisation'),
    ('family_care_plan', 'Consent form'),
    ('family_care_plan', 'Risk Assessment Form'),
    ('family_care_plan', 'Girl/Boy Index form'),
    ('vital_document', 'Birth certificates'),
    ('vital_document', 'Clinic Card'),
    ("vital_document", "Parents' ID's"),
    ('vital_document', 'Death Certificates'),
    ('process_note', 'House visit forms'),
    ('process_note', 'SAW Process note - CW 11'),
    ('process_note', 'Termination report / Exit forms - CW 13'),
    ('school_report', 'Educational Plan'),
    ('school_report', 'Teachers Feedback report'),
    ('referral_form', 'Referral form'),
    ('success_story', 'Success story'),
    ('monthly_report', 'Monthly Household Services Report - C06'),
]
