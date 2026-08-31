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

# CW 06 Problem Codes (value = code, label includes code).
PROBLEM_CODES = [
    ('1.1', '1.1 Loss of income'), ('1.2', '1.2 Unemployment'),
    ('1.3', '1.3 Access to social grants'), ('1.4', '1.4 Food or nutritional problems'),
    ('1.5', '1.5 Clothing or other basic necessities'),
    ('1.6', '1.6 Housing issues, including water and sanitation'),
    ('2.1', '2.1 Mismanagement of funds'), ('2.2', '2.2 Mismanagement of social grants'),
    ('2.3', '2.3 Burial assistance'), ('2.4', '2.4 Health services or health related problems'),
    ('2.5', '2.5 Human displacement (Refugee, Migration)'), ('2.6', '2.6 Xenophobic related incident'),
    ('3.1', '3.1 Marital problems including divorce'),
    ('3.2', '3.2 Parenting challenges and child-parent relationship issues'),
    ('3.3', '3.3 Sexual orientation related issues'),
    ('3.4', '3.4 Legal issues incl. Estate / trust problems and guardianship'),
    ('3.5', '3.5 Child non maintenance'), ('3.6', '3.6 Marital non maintenance'),
    ('3.7', '3.7 Care and contact / custody'), ('3.8', '3.8 Documentation (birth registration, marriage)'),
    ('3.9', '3.9 Bereavement'), ('3.10', '3.10 Application for adoption'), ('3.11', '3.11 Other family challenges'),
    ('4.1', '4.1 Violent crimes'), ('4.2', '4.2 Property crimes'), ('4.3', '4.3 Other crimes'),
    ('4.4', '4.4 Child in conflict with the law'), ('4.5', '4.5 Adult in conflict with the law'),
    ('4.6', '4.6 Child used by adult to commit crimes (Cubac)'), ('4.7', '4.7 Gangsterism'),
    ('5.1', '5.1 Physical abuse'), ('5.2', '5.2 Sexual abuse'),
    ('5.3', '5.3 Emotional / verbal / psychological abuse'), ('5.4', '5.4 Economic abuse and denial of resources'),
    ('5.5', '5.5 Intimidation / harassment / stalking'), ('5.6', '5.6 Human Trafficking'),
    ('5.7', '5.7 Abduction and forced marriages'), ('5.8', '5.8 Domestic Violence'),
    ('5.9', '5.9 Gender Based Violence'),
    ('6.1', '6.1 Child abandonment'), ('6.2', '6.2 Child neglect'), ('6.3', '6.3 Child exploitation'),
    ('6.4', '6.4 Child physical abuse'), ('6.5', '6.5 Child psychological / mental abuse'),
    ('6.6', '6.6 Child sexual abuse'), ('6.7', '6.7 Child endangerment'), ('6.8', '6.8 Orphaned child'),
    ('6.9', '6.9 Child headed household'), ('6.10', '6.10 Bullying'), ('6.11', '6.11 Child behaviour problems'),
    ('6.12', '6.12 Child living / working on the streets / begging'), ('6.13', '6.13 Child labour'),
    ('6.14', '6.14 Unaccompanied minors'), ('6.15', '6.15 Migrant children'),
    ('6.16', '6.16 Child / teenage pregnancy'), ('6.17', '6.17 Child abduction and trafficking'),
    ('6.18', '6.18 Access to education or education related problems'), ('6.19', '6.19 Corporal punishment'),
    ('6.20', '6.20 Harmful socio-cultural / religious practices'),
    ('7.1', '7.1 Visual impairment, incl. blindness'), ('7.2', '7.2 Hearing impairment'),
    ('7.3', '7.3 Speech impairment'), ('7.4', '7.4 Physical disability'), ('7.5', '7.5 Mental disability'),
    ('7.6', '7.6 Multiple disabilities'), ('7.7', '7.7 Challenges in self-care'),
    ('7.8', '7.8 Sexual abuse of disabled person'), ('7.9', '7.9 Physical abuse of disabled person'),
    ('7.10', '7.10 Psychological abuse of disabled person'), ('7.11', '7.11 Disabled person abuse - financial/neglect'),
    ('8.1', '8.1 Care for persons with disability, elderly etc.'), ('8.2', '8.2 Sexual abuse of Elderly person'),
    ('8.3', '8.3 Physical abuse of Elderly person'), ('8.4', '8.4 Psychological abuse of elderly person'),
    ('8.5', '8.5 Elderly abuse - financial/neglect/abandonment'),
    ('9.1', '9.1 HIV and AIDS affected or infected'), ('9.2', '9.2 Stigmatisation/discrimination (HIV & AIDS)'),
    ('9.3', '9.3 Lack of access to HIV and AIDS services'),
    ('10.1', '10.1 Poly / Multi dependency'), ('10.2', '10.2 Alcohol'), ('10.3', '10.3 Cannabis / Dagga'),
    ('10.4', '10.4 Mandrax'), ('10.5', '10.5 Crack / Cocaine'), ('10.6', '10.6 Heroin'),
    ('10.7', '10.7 Nyaope / Whoonga'), ('10.8', '10.8 Inhalant / solvent'), ('10.9', '10.9 Methamphetamine / Tik'),
    ('10.10', '10.10 Over-the-counter and prescription medication'), ('10.11', '10.11 Other dependency (gambling etc.)'),
    ('11.1', '11.1 Childhood development delays or learning disabilities'), ('11.2', '11.2 Childhood mental disorders'),
    ('11.3', '11.3 Adult emotional or behavioural problems'), ('11.4', '11.4 Adult mental disorders'),
    ('11.5', '11.5 Suicide attempt / suicidal thoughts / self-harm'),
    ('12.1', '12.1 Exposure to natural disaster'), ('12.2', '12.2 Other, specify'),
]

# CW 10 Intervention Codes (main + programme-specific).
INTERVENTION_CODES = [
    ('1', '1 Assessment'), ('2', '2 Individual Counselling and therapy'), ('3', '3 Interview'),
    ('4', '4 Trauma debriefing'), ('5', '5 Mediation'), ('6', '6 Counselling'),
    ('7', '7 Psychosocial support'), ('8', '8 Emergency material support'),
    ('9', '9 Prevention and early intervention services'), ('10', '10 Reintegration and aftercare services'),
    ('11', '11 Reunification services'), ('12', '12 School Bursary / Uniform'), ('13', '13 Paupers Burial'),
    ('14', '14 Accompaniment and transportation of clients'), ('15', '15 Statutory casework'),
    ('16', '16 Court appearance'), ('17', '17 Support to Home based care'),
    ('18', '18 Referral for social assistance / grants'), ('19', '19 Referral to job placement / income generation'),
    ('20', '20 Referral to education'), ('21', '21 Referral for Health services'),
    ('22', '22 Referral to accommodation'), ('23', '23 Referral to police, legal and judicial services'),
    ('24', '24 Referral for documentation (birth cert, ID)'), ('25', '25 Referral to other basic needs'),
    ('26', '26 Educational group'), ('27', '27 Support group'), ('28', '28 Counselling group'),
    ('29', '29 Parenting programmes'), ('30', '30 Capacity building, life skills, empowerment'),
    ('31', '31 Community awareness and information provision'), ('32', '32 Social & behavioural change programme'),
    ('33', '33 Community dialogues and mobilisation'), ('34', '34 Advocacy'),
    ('35', '35 Sport and recreational programme'), ('36', '36 Celebrations and events'),
    ('37', '37 Disaster relief programme'), ('38', '38 Poverty Alleviation Programme'),
    ('39', '39 Non-residential centres'), ('40', '40 Residential care / treatment centres'),
    ('41', '41 NPO related interventions'), ('60', '60 Home visits'), ('61', '61 Information gathering'),
    ('62', '62 Report writing'), ('64', '64 Developmental Quality Assurance'), ('68', '68 Stakeholder engagement'),
    ('69', '69 Other'),
    ('55A', '55A Parental guidance'), ('55C', '55C Bereavement / Support services'),
    ('55D', '55D Family preservation'), ('55E', '55E Family reunification'),
    ('56A', '56A Removal and placement in temporary safe care'), ('56D', '56D Placement in Foster Care'),
    ('54', '54 Programme for OVC and child headed households'),
    ('53A', '53A Support services (HIV/AIDS infected/affected)'), ('58A', '58A Victim Empowerment services'),
    ('59A', '59A Substance abuse prevention programme'),
]

RISK_LEVEL_CHOICES = [
    ('Emergency', 'Emergency (24-48 hours)'),
    ('High', 'High (1 week)'),
    ('Mild', 'Mild (2-3 weeks)'),
]

CASE_STATUS_CHOICES = [
    ('open', 'Open'),
    ('graduated', 'Graduated'),
    ('transferred', 'Transferred'),
    ('lost_to_follow_up', 'Lost to follow-up'),
    ('closed', 'Closed'),
]

HIV_STATUS_CHOICES = [
    ('unknown', 'Unknown'),
    ('negative', 'Negative'),
    ('positive', 'Positive'),
    ('not_disclosed', 'Not disclosed'),
]

ON_ART_CHOICES = [
    ('na', 'Not applicable'),
    ('yes', 'On ART'),
    ('no', 'Not on ART'),
    ('unknown', 'Unknown'),
]

GRANT_TYPE_CHOICES = [
    ('CSG', 'Child Support Grant (CSG)'),
    ('FCG', 'Foster Child Grant (FCG)'),
    ('CDG', 'Care Dependency Grant (CDG)'),
    ('OAG', "Older Person's Grant"),
    ('DG', 'Disability Grant'),
    ('other', 'Other'),
]

CONSENT_TYPE_CHOICES = [
    ('services', 'Consent to services'),
    ('information_sharing', 'Information sharing'),
    ('photo', 'Photo / media consent'),
]

PROTECTION_TYPE_CHOICES = [
    ('physical_abuse', 'Physical abuse'),
    ('sexual_abuse', 'Sexual abuse'),
    ('neglect', 'Neglect'),
    ('emotional_abuse', 'Emotional / psychological abuse'),
    ('exploitation', 'Exploitation'),
    ('abandonment', 'Abandonment'),
    ('gbv', 'Gender-based violence'),
    ('other', 'Other'),
]

INCIDENT_STATUS_CHOICES = [
    ('open', 'Open'),
    ('referred', 'Referred'),
    ('closed', 'Closed'),
]

EVALUATION_RECOMMENDATION_CHOICES = [
    ('continue', 'Continue services'),
    ('close', 'Close / graduate'),
    ('refer', 'Refer'),
    ('transfer', 'Transfer'),
]

# Service delivery types (fixed list agreed with the NPO).
SERVICE_TYPE_CHOICES = [
    ('Individual Counselling', 'Individual Counselling'),
    ('Family Counselling', 'Family Counselling'),
    ('Home Visit', 'Home Visit'),
    ('School Visit', 'School Visit'),
    ('Support Group', 'Support Group'),
    ('Referral', 'Referral'),
    ('Material Support', 'Material Support'),
    ('Grant Assistance', 'Grant Assistance'),
    ('ID Documentation Assistance', 'ID Documentation Assistance'),
    ('HIV Testing Referral', 'HIV Testing Referral'),
    ('Health Check', 'Health Check'),
    ('Educational Support', 'Educational Support'),
    ('Psychosocial Support', 'Psychosocial Support'),
    ('Other', 'Other'),
]
