"""Data model for the Offline OVC Case Management System."""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from . import choices


def today():
    """Return the current local date (for DateField defaults)."""
    return timezone.localdate()


def digits_only(value):
    """Strip spaces and dashes so 800101 5009 087 and 8001015009087 match."""
    return ''.join(ch for ch in (value or '') if ch.isdigit())


def document_upload_path(instance, filename):
    """Store files as {model}_{object_id}_{timestamp}_{original_filename}."""
    ts = timezone.now().strftime('%Y%m%d%H%M%S')
    model = 'record'
    try:
        if instance.content_type_id:
            model = instance.content_type.model
    except Exception:
        model = 'record'
    object_id = instance.object_id or 0
    safe_name = filename.replace('/', '_').replace('\\', '_')
    return f"documents/{model}_{object_id}_{ts}_{safe_name}"


class Household(models.Model):
    org_household_number = models.CharField(max_length=100, db_index=True)
    house_number = models.CharField(max_length=100, blank=True)
    street = models.CharField(max_length=255, blank=True)
    town = models.CharField(max_length=255, blank=True)
    province = models.CharField(max_length=255, blank=True)
    district = models.CharField(max_length=255, blank=True)
    municipality = models.CharField(max_length=255, blank=True)
    ward = models.CharField(max_length=255, blank=True)
    date_registered = models.DateField(default=today)
    status = models.CharField(max_length=32, choices=choices.CASE_STATUS_CHOICES, default='open', db_index=True)
    status_changed_at = models.DateField(null=True, blank=True)
    status_reason = models.TextField(blank=True)

    # Caseload scoping for case-workers (SSP).
    assigned_to = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='assigned_households', blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Optimistic-concurrency version (incremented on each edit save).
    version = models.PositiveIntegerField(default=0)

    # Checklist sign-off (supervisor stamp on printed Case File Checklist).
    checklist_signed_name = models.CharField(max_length=255, blank=True)
    checklist_signed_sacssp = models.CharField(max_length=64, blank=True)
    checklist_signed_at = models.DateTimeField(null=True, blank=True)
    checklist_signed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+',
    )

    documents = GenericRelation('SupportingDocument')

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f"Household #{self.pk} ({self.org_household_number})"


class PersonBase(models.Model):
    """Shared person fields for Caregiver and HouseholdMember, incl. confirm-trio."""
    id_type = models.CharField(max_length=32, choices=choices.ID_TYPE_CHOICES, default='SA ID Number')
    id_number = models.CharField(max_length=64, blank=True, db_index=True)
    # Digits-only copy of id_number for Access-style lookup (ignore spaces/dashes).
    id_number_digits = models.CharField(max_length=64, blank=True, db_index=True)
    name = models.CharField(max_length=255, blank=True)
    surname = models.CharField(max_length=255, blank=True, db_index=True)
    known_as = models.CharField(max_length=255, blank=True)
    nationality = models.CharField(max_length=255, default='South African')
    date_of_birth = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=16, choices=choices.SEX_CHOICES, blank=True)
    race = models.CharField(max_length=16, choices=choices.RACE_CHOICES, blank=True)
    disability = models.BooleanField(default=False)
    disability_description = models.TextField(blank=True)
    date_joined = models.DateField(default=today)

    # --- Confirmation trio (surname / id_number / date_of_birth) ---
    surname_confirmed = models.BooleanField(default=False)
    surname_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+',
    )
    surname_confirmed_at = models.DateTimeField(null=True, blank=True)

    id_number_confirmed = models.BooleanField(default=False)
    id_number_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+',
    )
    id_number_confirmed_at = models.DateTimeField(null=True, blank=True)

    date_of_birth_confirmed = models.BooleanField(default=False)
    date_of_birth_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+',
    )
    date_of_birth_confirmed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Fields governed by the confirm-before-save rule.
    CONFIRM_FIELDS = ['surname', 'id_number', 'date_of_birth']

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.id_number_digits = digits_only(self.id_number)
        super().save(*args, **kwargs)


class Caregiver(PersonBase):
    household = models.OneToOneField(Household, on_delete=models.CASCADE, related_name='caregiver')
    marital_status = models.CharField(max_length=32, choices=choices.MARITAL_STATUS_CHOICES, blank=True)
    cell_number = models.CharField(max_length=64, blank=True)
    home_language = models.CharField(max_length=128, blank=True)
    headship_type = models.CharField(max_length=64, choices=choices.HEADSHIP_TYPE_CHOICES, blank=True)

    documents = GenericRelation('SupportingDocument')

    def __str__(self):
        return f"Caregiver: {self.name} {self.surname}".strip()


class HouseholdMember(PersonBase):
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='members')
    relationship_to_head = models.CharField(max_length=255, blank=True)
    school_name = models.CharField(max_length=255, blank=True)
    grade = models.CharField(max_length=32, blank=True)
    enrolled_in_school = models.BooleanField(default=False)
    grant_types = models.JSONField(default=list, blank=True)

    hiv_status = models.CharField(max_length=32, choices=choices.HIV_STATUS_CHOICES, default='unknown', blank=True)
    on_art = models.CharField(max_length=16, choices=choices.ON_ART_CHOICES, blank=True, default='na')
    last_viral_load = models.CharField(max_length=64, blank=True)
    last_viral_load_date = models.DateField(null=True, blank=True)
    hiv_test_date = models.DateField(null=True, blank=True)
    hiv_test_required = models.BooleanField(null=True, blank=True)
    hiv_risk_notes = models.TextField(blank=True)

    documents = GenericRelation('SupportingDocument')

    class Meta:
        ordering = ['id']
        indexes = [
            models.Index(fields=['household', 'surname']),
            models.Index(fields=['household', 'id_number']),
        ]

    def __str__(self):
        return f"Member: {self.name} {self.surname}".strip()


class SupportingDocument(models.Model):
    """Evidence files - never edited, never OCR'd, stored exactly as uploaded."""
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    category = models.CharField(max_length=32, choices=choices.CATEGORY_CHOICES)
    file = models.FileField(upload_to=document_upload_path)
    label = models.CharField(max_length=255, blank=True)
    attached_name = models.CharField(max_length=255, blank=True)
    parent_kind = models.CharField(max_length=32, blank=True, db_index=True)
    date_of_document = models.DateField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='uploaded_documents',
    )

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['-uploaded_at']),
        ]

    def __str__(self):
        return f"{self.get_category_display()}: {self.label}"


class CaseFileChecklistItem(models.Model):
    """Mirrors the physical NPO case-file checklist (per household)."""
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='checklist_items')
    category = models.CharField(max_length=32, choices=choices.CATEGORY_CHOICES)
    sub_item = models.CharField(max_length=255, blank=True)
    has_evidence = models.CharField(max_length=8, choices=choices.HAS_EVIDENCE_CHOICES, blank=True, default='')
    comments = models.TextField(blank=True)
    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='checked_items',
    )
    checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.get_category_display()} / {self.sub_item}"


class AuditLogEntry(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='audit_entries',
    )
    action = models.CharField(max_length=32)
    target_description = models.CharField(max_length=500)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user} {self.action} {self.target_description}"


class ProcessNote(models.Model):
    """Structured CW 11 Case Work Process Note (per engagement with a client)."""
    ENGAGEMENT_CHOICES = [
        ('Office', 'Office'), ('Home', 'Home'), ('School', 'School'),
        ('Court', 'Court'), ('Telephone', 'Telephone'), ('Other', 'Other'),
    ]
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='process_notes')
    client_surname = models.CharField(max_length=255, blank=True)
    client_first_name = models.CharField(max_length=255, blank=True)
    client_id_number = models.CharField(max_length=64, blank=True)
    file_no = models.CharField(max_length=100, blank=True)
    person_engaged_name = models.CharField(max_length=255, blank=True)
    person_engaged_contact = models.CharField(max_length=255, blank=True)
    problem_code = models.CharField(max_length=64, blank=True)
    intervention_code = models.CharField(max_length=64, blank=True)
    type_of_engagement = models.CharField(max_length=16, choices=ENGAGEMENT_CHOICES, blank=True)
    purpose_and_what_transpired = models.TextField(blank=True)
    outcome_and_follow_up = models.TextField(blank=True)
    evaluation_reflection = models.TextField(blank=True)
    date_of_next_follow_up = models.DateField(null=True, blank=True)
    ssp_name = models.CharField(max_length=255, blank=True)
    ssp_sacssp_number = models.CharField(max_length=64, blank=True)
    ssp_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='process_notes',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Process note for Household #{self.household_id} ({self.created_at:%Y-%m-%d})"


class Assessment(models.Model):
    """Structured CW 09 Assessment, Planning and Contracting record."""
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='assessments')
    overview_situation = models.TextField(blank=True)
    strengths = models.TextField(blank=True)
    psychosocial_social = models.TextField(blank=True)
    psychosocial_stress = models.TextField(blank=True)
    education = models.TextField(blank=True)
    safety = models.TextField(blank=True)
    health_nutrition = models.TextField(blank=True)
    economic_legal = models.TextField(blank=True)
    assessment_summary = models.TextField(blank=True)
    problem_codes = models.CharField(max_length=255, blank=True)
    risk_level = models.CharField(max_length=16, choices=choices.RISK_LEVEL_CHOICES, blank=True)
    overall_goal = models.TextField(blank=True)
    client_views = models.TextField(blank=True)
    due_date_evaluation = models.DateField(null=True, blank=True)
    plan_rows = models.JSONField(default=list, blank=True)
    version_number = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='assessments',
    )

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Assessment for Household #{self.household_id}"


class Organisation(models.Model):
    """Singleton org profile used as the letterhead on printed DSD forms."""
    name = models.CharField(max_length=255, default='OVC Organisation')
    logo = models.FileField(upload_to='org/', null=True, blank=True)
    address = models.CharField(max_length=500, blank=True)
    contact = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.name


class SiteConfig(models.Model):
    """Singleton site-wide config (e.g. login page tagline)."""
    login_tagline = models.CharField(max_length=200, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return 'Site configuration'


class ServiceTarget(models.Model):
    """A case worker's monthly service-delivery goal (set by supervisors/admin)."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='service_target'
    )
    monthly_goal = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user}: {self.monthly_goal}/month'


class ServiceDelivery(models.Model):
    """A single service delivered to a household (optionally a named beneficiary)."""
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='services')
    beneficiary_content_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    beneficiary_object_id = models.PositiveIntegerField(null=True, blank=True)
    beneficiary = GenericForeignKey('beneficiary_content_type', 'beneficiary_object_id')
    service_date = models.DateField(default=today, db_index=True)
    service_type = models.CharField(max_length=64, choices=choices.SERVICE_TYPE_CHOICES)
    delivered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='delivered_services',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='created_services',
    )

    class Meta:
        ordering = ['-service_date', '-id']
        indexes = [models.Index(fields=['household', 'service_date'])]

    def __str__(self):
        return f"{self.service_type} for Household #{self.household_id} on {self.service_date}"


class ConsentRecord(models.Model):
    """Dated consent (services, information sharing, photo) with caregiver sign-off and child assent."""
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='consents')
    consent_type = models.CharField(max_length=32, choices=choices.CONSENT_TYPE_CHOICES)
    caregiver_name = models.CharField(max_length=255, blank=True)
    caregiver_signed = models.BooleanField(default=False)
    caregiver_signed_date = models.DateField(null=True, blank=True)
    child_name = models.CharField(max_length=255, blank=True)
    child_assent = models.BooleanField(default=False)
    child_assent_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='consent_records',
    )

    class Meta:
        ordering = ['-caregiver_signed_date', '-id']

    def __str__(self):
        return f"{self.get_consent_type_display()} for Household #{self.household_id}"


class FamilyCarePlan(models.Model):
    """Saved family care plan (needs / actions / progress) for reprinting filled."""
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='care_plans')
    overall_goal = models.TextField(blank=True)
    review_date = models.DateField(null=True, blank=True)
    ssp_name = models.CharField(max_length=255, blank=True)
    caregiver_sign_name = models.CharField(max_length=255, blank=True)
    rows = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='care_plans',
    )

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Family care plan for Household #{self.household_id}"


class ProtectionIncident(models.Model):
    """Form 22 analogue — child protection incident."""
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='protection_incidents')
    member = models.ForeignKey(
        HouseholdMember, null=True, blank=True, on_delete=models.SET_NULL, related_name='protection_incidents'
    )
    incident_date = models.DateField(default=today)
    incident_type = models.CharField(max_length=32, choices=choices.PROTECTION_TYPE_CHOICES, blank=True)
    alleged_perpetrator = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    reported_to = models.CharField(max_length=255, blank=True)
    action_taken = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=choices.INCIDENT_STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='protection_incidents',
    )

    class Meta:
        ordering = ['-incident_date', '-id']

    def __str__(self):
        return f"Protection incident Household #{self.household_id} ({self.incident_date})"


class Cow1Plan(models.Model):
    """COW 1 community work planning record."""
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='cow1_plans')
    plan_date = models.DateField(default=today)
    community_issue = models.TextField(blank=True)
    planned_activities = models.TextField(blank=True)
    stakeholders = models.CharField(max_length=500, blank=True)
    expected_outcome = models.TextField(blank=True)
    ssp_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='cow1_plans',
    )

    class Meta:
        ordering = ['-plan_date', '-id']

    def __str__(self):
        return f"COW1 for Household #{self.household_id}"


class Evaluation(models.Model):
    """CW 12 evaluation of progress against the care plan."""
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='evaluations')
    evaluation_date = models.DateField(default=today)
    period_from = models.DateField(null=True, blank=True)
    period_to = models.DateField(null=True, blank=True)
    progress_against_plan = models.TextField(blank=True)
    remaining_needs = models.TextField(blank=True)
    recommendation = models.CharField(
        max_length=16, choices=choices.EVALUATION_RECOMMENDATION_CHOICES, blank=True
    )
    ssp_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='evaluations',
    )

    class Meta:
        ordering = ['-evaluation_date', '-id']

    def __str__(self):
        return f"CW12 evaluation for Household #{self.household_id}"


class GroupWorkSession(models.Model):
    """GRW group-work session linked to a household file."""
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='group_sessions')
    session_date = models.DateField(default=today)
    group_name = models.CharField(max_length=255, blank=True)
    topic = models.CharField(max_length=255, blank=True)
    attendees_count = models.PositiveIntegerField(default=0)
    attendees_notes = models.TextField(blank=True)
    session_notes = models.TextField(blank=True)
    outcomes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='group_sessions',
    )

    class Meta:
        ordering = ['-session_date', '-id']

    def __str__(self):
        return f"GRW {self.group_name} Household #{self.household_id}"


class PartnerAgency(models.Model):
    """Local directory of clinics, SASSA, schools, SAPS — typed in by this office."""
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=32, choices=choices.PARTNER_KIND_CHOICES, default='other')
    contact_person = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    address = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    is_training = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Referral(models.Model):
    """Tracked external referral (CW 04B as a live record, not only a blank print)."""
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='referrals')
    member = models.ForeignKey(
        HouseholdMember, null=True, blank=True, on_delete=models.SET_NULL, related_name='referrals'
    )
    client_name = models.CharField(max_length=255, blank=True)
    partner = models.ForeignKey(
        PartnerAgency, null=True, blank=True, on_delete=models.SET_NULL, related_name='referrals'
    )
    agency_name = models.CharField(max_length=255, blank=True)
    reason = models.CharField(max_length=32, choices=choices.REFERRAL_REASON_CHOICES, default='other')
    details = models.TextField(blank=True)
    referred_on = models.DateField(default=today)
    follow_up_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=choices.REFERRAL_STATUS_CHOICES, default='sent', db_index=True)
    outcome = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='referrals',
    )

    class Meta:
        ordering = ['-referred_on', '-id']

    def display_agency(self):
        if self.partner_id:
            return self.partner.name
        return self.agency_name or '—'

    def __str__(self):
        return f"Referral {self.display_agency()} Household #{self.household_id}"


class PlannedVisit(models.Model):
    """Diary of planned home/school/office visits — the case-worker work list."""
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='planned_visits')
    visit_date = models.DateField(db_index=True)
    visit_type = models.CharField(max_length=16, choices=choices.VISIT_TYPE_CHOICES, default='home')
    purpose = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=choices.VISIT_STATUS_CHOICES, default='planned', db_index=True)
    notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='planned_visits',
    )
    completed_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='created_visits',
    )

    class Meta:
        ordering = ['visit_date', 'id']

    def __str__(self):
        return f"Visit {self.visit_date} Household #{self.household_id}"
