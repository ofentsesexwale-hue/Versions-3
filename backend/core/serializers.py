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
    Household,
    HouseholdMember,
    Organisation,
    ProcessNote,
    SupportingDocument,
)
from .permissions import user_role

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
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name', 'email', 'role']

    def get_role(self, obj):
        return user_role(obj)

    def get_full_name(self, obj):
        return (obj.get_full_name() or obj.username).strip()


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

    class Meta:
        model = Caregiver
        fields = [
            'id', 'household', 'id_type', 'id_number', 'name', 'surname', 'known_as',
            'nationality', 'date_of_birth', 'sex', 'race', 'marital_status',
            'disability', 'disability_description', 'cell_number', 'home_language',
            'headship_type', 'date_joined',
        ] + CONFIRM_READ_FIELDS
        read_only_fields = [
            'surname_confirmed_at', 'id_number_confirmed_at', 'date_of_birth_confirmed_at',
        ]


class HouseholdMemberSerializer(ConfirmMixin):
    surname_confirmed_by = serializers.StringRelatedField(read_only=True)
    id_number_confirmed_by = serializers.StringRelatedField(read_only=True)
    date_of_birth_confirmed_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = HouseholdMember
        fields = [
            'id', 'household', 'id_type', 'id_number', 'name', 'surname', 'known_as',
            'nationality', 'date_of_birth', 'sex', 'race', 'disability',
            'disability_description', 'relationship_to_head', 'date_joined',
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

    class Meta:
        model = SupportingDocument
        fields = [
            'id', 'parent_type', 'parent_id', 'category', 'category_display', 'file',
            'file_name', 'view_url', 'download_url', 'is_pdf', 'label',
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
        return bool(obj.file) and obj.file.name.lower().endswith('.pdf')

    def validate_file(self, value):
        if value.size > settings.MAX_UPLOAD_SIZE:
            raise serializers.ValidationError(
                f'File too large. Maximum size is {settings.MAX_UPLOAD_SIZE // (1024 * 1024)} MB.'
            )
        return value

    def create(self, validated_data):
        parent_type = validated_data.pop('parent_type')
        parent_id = validated_data.pop('parent_id')
        model = PARENT_MODEL_MAP[parent_type]
        if not model.objects.filter(pk=parent_id).exists():
            raise serializers.ValidationError({'parent_id': 'Target record not found.'})
        validated_data['content_type'] = ContentType.objects.get_for_model(model)
        validated_data['object_id'] = parent_id
        validated_data['uploaded_by'] = self.context['request'].user
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

    class Meta:
        model = Household
        fields = [
            'id', 'org_household_number', 'house_number', 'street', 'town',
            'province', 'district', 'municipality', 'ward', 'date_registered',
            'assigned_to', 'assigned_to_names', 'checklist_progress', 'created_at',
            'checklist_signed_name', 'checklist_signed_sacssp', 'checklist_signed_at',
        ]

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
            'due_date_evaluation', 'plan_rows', 'created_at', 'updated_at', 'created_by',
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


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
