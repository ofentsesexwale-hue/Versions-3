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

    # Caseload scoping for case-workers (SSP).
    assigned_to = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='assigned_households', blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

    documents = GenericRelation('SupportingDocument')

    class Meta:
        ordering = ['id']

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
    date_of_document = models.DateField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='uploaded_documents',
    )

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [models.Index(fields=['content_type', 'object_id'])]

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
