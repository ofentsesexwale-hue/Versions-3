"""DRF serializers for the OVC case management API."""
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework import serializers

from . import choices
from .models import (
    AuditLogEntry,
    Assessment,
    Caregiver,
    CaseFileChecklistItem,
    ConsentRecord,
    Cow1Plan,
    Evaluation,
    FamilyCarePlan,
    GroupWorkSession,
    Household,
    HouseholdMember,
    Organisation,
    PartnerAgency,
    PlannedVisit,
    ProcessNote,
    ProtectionIncident,
    Referral,
    ServiceDelivery,
    SiteConfig,
    SupportingDocument,
)
from .permissions import is_system_builder, is_training_user, user_role


class EmptyBlankDatesMixin:
    """Treat empty date strings as null so household forms can omit optional dates."""

    def to_internal_value(self, data):
        if hasattr(data, 'copy'):
            data = data.copy()
        else:
            data = dict(data)
        for name, field in self.fields.items():
            if isinstance(field, serializers.DateField) and data.get(name) == '':
                data[name] = None
        return super().to_internal_value(data)


PARENT_MODEL_MAP = {
    'household': Household,
    'caregiver': Caregiver,
    'householdmember': HouseholdMember,
}


def checklist_progress(household):
    """Return case-file completeness based on checklist items marked 'Yes'."""
    items = list(household.checklist_items.all())
    total = len(items)
    if not total:
        return {'yes': 0, 'total': 0, 'percent': 0}
    yes = sum(1 for i in items if i.has_evidence == 'Yes')
    return {'yes': yes, 'total': total, 'percent': round(yes * 100 / total)}



class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    job_title = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    is_training = serializers.SerializerMethodField()
    is_system_builder = serializers.SerializerMethodField()
    linked_household = serializers.SerializerMethodField()
    permission_summary = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'full_name', 'email',
            'role', 'job_title', 'is_active', 'last_login', 'date_joined',
            'is_training', 'is_system_builder', 'linked_household',
            'permission_summary',
        ]

    def get_role(self, obj):
        return user_role(obj)

    def get_job_title(self, obj):
        return user_role(obj)

    def get_full_name(self, obj):
        return (obj.get_full_name() or obj.username).strip()

    def get_is_training(self, obj):
        return is_training_user(obj)

    def get_is_system_builder(self, obj):
        return is_system_builder(obj)

    def get_linked_household(self, obj):
        try:
            cg = obj.household_caregiver
        except Caregiver.DoesNotExist:
            return None
        if not cg:
            return None
        return {
            'id': cg.household_id,
            'org_household_number': cg.household.org_household_number,
            'caregiver_id': cg.id,
        }

    def get_permission_summary(self, obj):
        from .permissions import ROLE_PERMISSION_TEXT
        return ROLE_PERMISSION_TEXT.get(user_role(obj) or '', '')


class ConfirmMixin(serializers.ModelSerializer):
    """Implements the confirm-before-save rule + stamping for the confirm-trio."""

    CONFIRM_FIELDS = ['surname', 'id_number', 'date_of_birth']

    def _has_value(self, field, data, instance):
        if field in data:
            value = data.get(field)
        elif instance is not None:
            value = getattr(instance, field)
        else:
            value = None
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != ''
        return True

    def _confirmed_value(self, field, data, instance):
        key = f'{field}_confirmed'
        if key in data:
            return bool(data.get(key))
        if instance is not None:
            return bool(getattr(instance, key))
        return False

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        errors = {}
        for field in self.CONFIRM_FIELDS:
            if self._has_value(field, attrs, instance) and not self._confirmed_value(field, attrs, instance):
                errors[field] = (
                    f'This field must be confirmed before saving. '
                    f'Use the Confirm control next to "{field}".'
                )
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def _stamp(self, validated_data, instance=None):
        """Stamp confirmed_by/at when a field transitions to confirmed."""
        user = self.context['request'].user
        now = timezone.now()
        for field in self.CONFIRM_FIELDS:
            key = f'{field}_confirmed'
            if key not in validated_data:
                continue
            new_val = bool(validated_data[key])
            old_val = bool(getattr(instance, key)) if instance is not None else False
            if new_val and not old_val:
                validated_data[f'{field}_confirmed_by'] = user
                validated_data[f'{field}_confirmed_at'] = now
            elif not new_val:
                validated_data[f'{field}_confirmed_by'] = None
                validated_data[f'{field}_confirmed_at'] = None
        return validated_data

    def create(self, validated_data):
        validated_data = self._stamp(validated_data, instance=None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self._stamp(validated_data, instance=instance)
        return super().update(instance, validated_data)


CONFIRM_READ_FIELDS = [
    'surname_confirmed', 'surname_confirmed_by', 'surname_confirmed_at',
    'id_number_confirmed', 'id_number_confirmed_by', 'id_number_confirmed_at',
    'date_of_birth_confirmed', 'date_of_birth_confirmed_by', 'date_of_birth_confirmed_at',
]


class CaregiverSerializer(ConfirmMixin):
    surname_confirmed_by = serializers.StringRelatedField(read_only=True)
    id_number_confirmed_by = serializers.StringRelatedField(read_only=True)
    date_of_birth_confirmed_by = serializers.StringRelatedField(read_only=True)
    has_login = serializers.SerializerMethodField()
    login_username = serializers.SerializerMethodField()

    class Meta:
        model = Caregiver
        fields = [
            'id', 'household', 'id_type', 'id_number', 'name', 'surname', 'known_as',
            'nationality', 'date_of_birth', 'sex', 'race', 'marital_status',
            'disability', 'disability_description', 'cell_number', 'home_language',
            'headship_type', 'date_joined', 'has_login', 'login_username',
        ] + CONFIRM_READ_FIELDS
        read_only_fields = [
            'surname_confirmed_at', 'id_number_confirmed_at', 'date_of_birth_confirmed_at',
            'has_login', 'login_username',
        ]

    def get_has_login(self, obj):
        return bool(obj.user_id)

    def get_login_username(self, obj):
        return obj.user.username if obj.user_id else ''


class HouseholdMemberSerializer(EmptyBlankDatesMixin, ConfirmMixin):
    surname_confirmed_by = serializers.StringRelatedField(read_only=True)
    id_number_confirmed_by = serializers.StringRelatedField(read_only=True)
    date_of_birth_confirmed_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = HouseholdMember
        fields = [
            'id', 'household', 'id_type', 'id_number', 'name', 'surname', 'known_as',
            'nationality', 'date_of_birth', 'sex', 'race', 'disability',
            'disability_description', 'relationship_to_head', 'date_joined',
            'school_name', 'grade', 'enrolled_in_school', 'grant_types',
            'hiv_status', 'on_art', 'last_viral_load', 'last_viral_load_date',
            'hiv_test_date', 'hiv_test_required', 'hiv_risk_notes',
        ] + CONFIRM_READ_FIELDS
        read_only_fields = [
            'surname_confirmed_at', 'id_number_confirmed_at', 'date_of_birth_confirmed_at',
        ]


class SupportingDocumentSerializer(serializers.ModelSerializer):
    parent_type = serializers.ChoiceField(choices=list(PARENT_MODEL_MAP.keys()), write_only=True)
    parent_id = serializers.IntegerField(write_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    uploaded_by = serializers.StringRelatedField(read_only=True)
    file_name = serializers.SerializerMethodField()
    view_url = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    is_pdf = serializers.SerializerMethodField()
    is_image = serializers.SerializerMethodField()

    class Meta:
        model = SupportingDocument
        fields = [
            'id', 'parent_type', 'parent_id', 'category', 'category_display', 'file',
            'file_name', 'view_url', 'download_url', 'is_pdf', 'is_image', 'label',
            'attached_name', 'parent_kind',
            'date_of_document', 'uploaded_at', 'uploaded_by',
        ]
        extra_kwargs = {'file': {'write_only': True}}

    def get_file_name(self, obj):
        return obj.file.name.split('/')[-1] if obj.file else ''

    def get_view_url(self, obj):
        return f'/api/documents/{obj.pk}/view/'

    def get_download_url(self, obj):
        return f'/api/documents/{obj.pk}/download/'

    def get_is_pdf(self, obj):
        name = (obj.file.name if obj.file else '') or ''
        return name.lower().endswith('.pdf')

    def get_is_image(self, obj):
        name = (obj.file.name if obj.file else '') or ''
        return name.lower().endswith(('.png', '.jpg', '.jpeg'))

    def validate_file(self, value):
        if value.size > settings.MAX_UPLOAD_SIZE:
            raise serializers.ValidationError(
                f'File too large. Maximum size is {settings.MAX_UPLOAD_SIZE // (1024 * 1024)} MB.'
            )
        name = (getattr(value, 'name', '') or '').lower()
        allowed_ext = getattr(settings, 'ALLOWED_UPLOAD_EXTENSIONS', ('.pdf', '.png', '.jpg', '.jpeg'))
        if not name.endswith(allowed_ext):
            raise serializers.ValidationError(
                'Upload a PDF or PNG. JPEG scans of IDs and clinic cards are also accepted.'
            )
        header = value.read(8) or b''
        value.seek(0)
        is_pdf = header.startswith(b'%PDF')
        is_png = header.startswith(b'\x89PNG')
        is_jpeg = header.startswith(b'\xff\xd8\xff')
        if not (is_pdf or is_png or is_jpeg):
            raise serializers.ValidationError(
                'That file is not a valid PDF or PNG (or JPEG scan).'
            )
        if name.endswith('.pdf') and not is_pdf:
            raise serializers.ValidationError('The file extension does not match a PDF.')
        if name.endswith('.png') and not is_png:
            raise serializers.ValidationError('The file extension does not match a PNG.')
        return value

    def create(self, validated_data):
        parent_type = validated_data.pop('parent_type')
        parent_id = validated_data.pop('parent_id')
        model = PARENT_MODEL_MAP[parent_type]
        parent = model.objects.filter(pk=parent_id).first()
        if not parent:
            raise serializers.ValidationError({'parent_id': 'Target record not found.'})
        request = self.context.get('request')
        if request:
            from .views import scoped_household_qs
            if model is Household:
                hid = parent.pk
            else:
                hid = parent.household_id
            if not scoped_household_qs(request.user).filter(pk=hid).exists():
                raise serializers.ValidationError({'parent_id': 'You cannot attach a file to this record.'})
        validated_data['content_type'] = ContentType.objects.get_for_model(model)
        validated_data['object_id'] = parent_id
        validated_data['parent_kind'] = parent_type
        if model is Household:
            validated_data['attached_name'] = f'Household {parent.org_household_number}'
        else:
            validated_data['attached_name'] = f'{parent.name} {parent.surname}'.strip() or parent_type
        validated_data['uploaded_by'] = request.user if request else None
        return super().create(validated_data)


class ChecklistItemSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    checked_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = CaseFileChecklistItem
        fields = [
            'id', 'household', 'category', 'category_display', 'sub_item',
            'has_evidence', 'comments', 'checked_by', 'checked_at',
        ]
        read_only_fields = ['household', 'checked_by', 'checked_at']


class CaregiverBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Caregiver
        fields = ['id', 'name', 'surname', 'id_number', 'cell_number', 'headship_type']


class HouseholdListSerializer(serializers.ModelSerializer):
    caregiver_name = serializers.SerializerMethodField()
    member_count = serializers.IntegerField(source='members.count', read_only=True)
    has_unconfirmed = serializers.SerializerMethodField()
    checklist_progress = serializers.SerializerMethodField()
    assigned_to_ids = serializers.SerializerMethodField()
    assigned_to_names = serializers.SerializerMethodField()

    class Meta:
        model = Household
        fields = [
            'id', 'org_household_number', 'town', 'district', 'province',
            'date_registered', 'caregiver_name', 'member_count', 'has_unconfirmed',
            'checklist_progress', 'assigned_to_ids', 'assigned_to_names',
            'checklist_signed_name', 'checklist_signed_sacssp', 'checklist_signed_at',
            'status', 'status_changed_at', 'status_reason',
        ]

    def get_caregiver_name(self, obj):
        cg = getattr(obj, 'caregiver', None)
        return f'{cg.name} {cg.surname}'.strip() if cg else ''

    def get_assigned_to_ids(self, obj):
        return [u.id for u in obj.assigned_to.all()]

    def get_assigned_to_names(self, obj):
        return [u.get_full_name() or u.username for u in obj.assigned_to.all()]

    def get_checklist_progress(self, obj):
        return checklist_progress(obj)

    def get_has_unconfirmed(self, obj):
        cg = getattr(obj, 'caregiver', None)
        people = ([cg] if cg else []) + list(obj.members.all())
        for p in people:
            for f in ['surname', 'id_number', 'date_of_birth']:
                val = getattr(p, f)
                has_val = (val.strip() != '') if isinstance(val, str) else (val is not None)
                if has_val and not getattr(p, f'{f}_confirmed'):
                    return True
        return False


class HouseholdSerializer(serializers.ModelSerializer):
    assigned_to = serializers.PrimaryKeyRelatedField(
        many=True, queryset=User.objects.all(), required=False
    )
    assigned_to_names = serializers.SerializerMethodField()
    checklist_progress = serializers.SerializerMethodField()
    version = serializers.IntegerField(read_only=True)

    class Meta:
        model = Household
        fields = [
            'id', 'org_household_number', 'house_number', 'street', 'town',
            'province', 'district', 'municipality', 'ward', 'date_registered',
            'assigned_to', 'assigned_to_names', 'checklist_progress', 'created_at',
            'checklist_signed_name', 'checklist_signed_sacssp', 'checklist_signed_at',
            'status', 'status_changed_at', 'status_reason', 'version',
        ]
        extra_kwargs = {
            'org_household_number': {'required': False, 'allow_blank': True},
        }

    def validate_org_household_number(self, value):
        value = (value or '').strip()
        if not value:
            return ''
        prefix = getattr(settings, 'TRAINING_HOUSEHOLD_PREFIX', 'TEST')
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        is_training = is_training_user(user)
        starts_test = value.upper().startswith(prefix.upper())
        if is_training and not starts_test:
            return f'{prefix}-{value}' if value else ''
        if user and user.is_authenticated and not is_training and starts_test:
            raise serializers.ValidationError(
                'TEST- household numbers belong to the training files. Use a real organisation number here.'
            )
        return value

    def create(self, validated_data):
        number = (validated_data.get('org_household_number') or '').strip()
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not number:
            validated_data['org_household_number'] = Household.next_file_number(
                training=is_training_user(user)
            )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        new_status = validated_data.get('status', instance.status)
        if new_status != instance.status:
            validated_data['status_changed_at'] = timezone.localdate()
        return super().update(instance, validated_data)

    def get_assigned_to_names(self, obj):
        return [u.get_full_name() or u.username for u in obj.assigned_to.all()]

    def get_checklist_progress(self, obj):
        return checklist_progress(obj)


class HouseholdDetailSerializer(HouseholdSerializer):
    caregiver = CaregiverSerializer(read_only=True)
    members = HouseholdMemberSerializer(many=True, read_only=True)

    class Meta(HouseholdSerializer.Meta):
        fields = HouseholdSerializer.Meta.fields + ['caregiver', 'members']


class AuditLogSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = AuditLogEntry
        fields = ['id', 'user', 'action', 'target_description', 'timestamp']

    def get_user(self, obj):
        if not obj.user:
            return 'system'
        return obj.user.get_full_name() or obj.user.username


class ProcessNoteSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    type_of_engagement_display = serializers.CharField(source='get_type_of_engagement_display', read_only=True)

    class Meta:
        model = ProcessNote
        fields = [
            'id', 'household', 'client_surname', 'client_first_name', 'client_id_number',
            'file_no', 'person_engaged_name', 'person_engaged_contact', 'problem_code',
            'intervention_code', 'type_of_engagement', 'type_of_engagement_display',
            'purpose_and_what_transpired', 'outcome_and_follow_up', 'evaluation_reflection',
            'date_of_next_follow_up', 'ssp_name', 'ssp_sacssp_number', 'ssp_date',
            'created_at', 'created_by',
        ]
        read_only_fields = ['created_at', 'created_by']


class AssessmentSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Assessment
        fields = [
            'id', 'household', 'overview_situation', 'strengths', 'psychosocial_social',
            'psychosocial_stress', 'education', 'safety', 'health_nutrition', 'economic_legal',
            'assessment_summary', 'problem_codes', 'risk_level', 'overall_goal', 'client_views',
            'due_date_evaluation', 'plan_rows', 'version_number', 'created_at', 'updated_at', 'created_by',
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'version_number']


class OrganisationSerializer(serializers.ModelSerializer):
    logo = serializers.SerializerMethodField()

    class Meta:
        model = Organisation
        fields = ['id', 'name', 'logo', 'address', 'contact', 'updated_at']
        read_only_fields = ['updated_at']

    def get_logo(self, obj):
        # Return a relative URL so the frontend can prepend REACT_APP_BACKEND_URL
        # correctly. build_absolute_uri uses the internal cluster hostname (Host
        # header from ingress -> pod) which is not reachable from a browser.
        if not obj.logo:
            return None
        try:
            return obj.logo.url
        except Exception:
            return None

    def to_internal_value(self, data):
        # SerializerMethodField makes 'logo' read-only; accept uploads via the
        # model field directly by delegating write handling to the parent when
        # a file is provided in multipart data.
        result = super().to_internal_value(data)
        if hasattr(data, 'getlist'):
            files = data.getlist('logo') if 'logo' in data else []
            if files and hasattr(files[0], 'read'):
                result['logo'] = files[0]
        return result


class SiteConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteConfig
        fields = ['id', 'login_tagline', 'updated_at']
        read_only_fields = ['updated_at']


class ServiceDeliverySerializer(serializers.ModelSerializer):
    delivered_by = serializers.StringRelatedField(read_only=True)
    created_by = serializers.StringRelatedField(read_only=True)
    beneficiary_type = serializers.ChoiceField(
        choices=['caregiver', 'householdmember'], write_only=True, required=False, allow_null=True
    )
    beneficiary_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    beneficiary_name = serializers.SerializerMethodField()

    class Meta:
        model = ServiceDelivery
        fields = [
            'id', 'household', 'service_date', 'service_type', 'notes',
            'delivered_by', 'created_at', 'created_by',
            'beneficiary_type', 'beneficiary_id', 'beneficiary_name',
        ]
        read_only_fields = ['created_at', 'delivered_by', 'created_by']

    def get_beneficiary_name(self, obj):
        b = obj.beneficiary
        if not b:
            return ''
        return f'{b.name} {b.surname}'.strip()

    def validate_service_date(self, value):
        if value and value > timezone.localdate():
            raise serializers.ValidationError('Service date cannot be in the future.')
        return value

    def create(self, validated_data):
        btype = validated_data.pop('beneficiary_type', None)
        bid = validated_data.pop('beneficiary_id', None)
        if btype and bid:
            model = {'caregiver': Caregiver, 'householdmember': HouseholdMember}[btype]
            obj = model.objects.filter(pk=bid, household=validated_data['household']).first()
            if not obj:
                raise serializers.ValidationError({'beneficiary_id': 'Beneficiary not found in this household.'})
            validated_data['beneficiary_content_type'] = ContentType.objects.get_for_model(model)
            validated_data['beneficiary_object_id'] = bid
        return super().create(validated_data)


class ConsentRecordSerializer(EmptyBlankDatesMixin, serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    consent_type_display = serializers.CharField(source='get_consent_type_display', read_only=True)

    class Meta:
        model = ConsentRecord
        fields = [
            'id', 'household', 'consent_type', 'consent_type_display',
            'caregiver_name', 'caregiver_signed', 'caregiver_signed_date',
            'child_name', 'child_assent', 'child_assent_date', 'notes',
            'created_at', 'created_by',
        ]
        read_only_fields = ['created_at', 'created_by']


class FamilyCarePlanSerializer(EmptyBlankDatesMixin, serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = FamilyCarePlan
        fields = [
            'id', 'household', 'overall_goal', 'review_date', 'ssp_name',
            'caregiver_sign_name', 'rows', 'created_at', 'updated_at', 'created_by',
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class ProtectionIncidentSerializer(EmptyBlankDatesMixin, serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    incident_type_display = serializers.CharField(source='get_incident_type_display', read_only=True)
    member_name = serializers.SerializerMethodField()

    class Meta:
        model = ProtectionIncident
        fields = [
            'id', 'household', 'member', 'member_name', 'incident_date', 'incident_type',
            'incident_type_display', 'alleged_perpetrator', 'location', 'description',
            'reported_to', 'action_taken', 'status', 'created_at', 'created_by',
        ]
        read_only_fields = ['created_at', 'created_by']

    def get_member_name(self, obj):
        if not obj.member:
            return ''
        return f'{obj.member.name} {obj.member.surname}'.strip()


class Cow1PlanSerializer(EmptyBlankDatesMixin, serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Cow1Plan
        fields = [
            'id', 'household', 'plan_date', 'community_issue', 'planned_activities',
            'stakeholders', 'expected_outcome', 'ssp_name', 'created_at', 'created_by',
        ]
        read_only_fields = ['created_at', 'created_by']


class EvaluationSerializer(EmptyBlankDatesMixin, serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    recommendation_display = serializers.CharField(source='get_recommendation_display', read_only=True)

    class Meta:
        model = Evaluation
        fields = [
            'id', 'household', 'evaluation_date', 'period_from', 'period_to',
            'progress_against_plan', 'remaining_needs', 'recommendation',
            'recommendation_display', 'ssp_name', 'created_at', 'created_by',
        ]
        read_only_fields = ['created_at', 'created_by']


class GroupWorkSessionSerializer(EmptyBlankDatesMixin, serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = GroupWorkSession
        fields = [
            'id', 'household', 'session_date', 'group_name', 'topic',
            'attendees_count', 'attendees_notes', 'session_notes', 'outcomes',
            'created_at', 'created_by',
        ]
        read_only_fields = ['created_at', 'created_by']


class PartnerAgencySerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)

    class Meta:
        model = PartnerAgency
        fields = [
            'id', 'name', 'kind', 'kind_display', 'contact_person', 'phone',
            'address', 'notes', 'is_training', 'created_at',
        ]
        read_only_fields = ['created_at', 'is_training']


class ReferralSerializer(EmptyBlankDatesMixin, serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    partner_name = serializers.SerializerMethodField()
    member_name = serializers.SerializerMethodField()
    household_number = serializers.CharField(source='household.org_household_number', read_only=True)
    caregiver_name = serializers.SerializerMethodField()

    class Meta:
        model = Referral
        fields = [
            'id', 'household', 'household_number', 'caregiver_name', 'member', 'member_name',
            'client_name', 'partner', 'partner_name', 'agency_name', 'reason', 'reason_display',
            'details', 'referred_on', 'follow_up_date', 'status', 'status_display', 'outcome',
            'created_at', 'created_by',
        ]
        read_only_fields = ['created_at', 'created_by']

    def get_partner_name(self, obj):
        return obj.display_agency()

    def get_member_name(self, obj):
        if not obj.member:
            return obj.client_name
        return f'{obj.member.name} {obj.member.surname}'.strip() or obj.client_name

    def get_caregiver_name(self, obj):
        cg = getattr(obj.household, 'caregiver', None)
        return f'{cg.name} {cg.surname}'.strip() if cg else ''


class PlannedVisitSerializer(EmptyBlankDatesMixin, serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    visit_type_display = serializers.CharField(source='get_visit_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    household_number = serializers.CharField(source='household.org_household_number', read_only=True)
    caregiver_name = serializers.SerializerMethodField()

    class Meta:
        model = PlannedVisit
        fields = [
            'id', 'household', 'household_number', 'caregiver_name', 'visit_date',
            'visit_type', 'visit_type_display', 'purpose', 'status', 'status_display',
            'notes', 'assigned_to', 'assigned_to_name', 'completed_at', 'created_at', 'created_by',
        ]
        read_only_fields = ['created_at', 'created_by']

    def get_assigned_to_name(self, obj):
        if not obj.assigned_to:
            return ''
        return obj.assigned_to.get_full_name() or obj.assigned_to.username

    def get_caregiver_name(self, obj):
        cg = getattr(obj.household, 'caregiver', None)
        return f'{cg.name} {cg.surname}'.strip() if cg else ''
