"""Read/write atlas targets through existing household serializers."""
from datetime import datetime

from .form_atlas import fields_for
from .models import Caregiver, HouseholdMember
from .sa_id import parse_sa_id
from .serializers import CaregiverSerializer, HouseholdMemberSerializer, HouseholdSerializer

# Identity fields a person must sign off before the file can be trusted.
TRIO_FIELDS = ('surname', 'id_number', 'date_of_birth')


def needs_staff_confirmation(target):
    """True for the surname / ID / date of birth of anyone on the file.

    Matched on the shape of the target rather than a fixed list, so every
    member slot the atlas emits is gated exactly like the caregiver.
    """
    parts = (target or '').split('.')
    if len(parts) == 2 and parts[0] == 'caregiver':
        return parts[1] in TRIO_FIELDS
    if len(parts) == 3 and parts[0] == 'member' and parts[1].isdigit():
        return parts[2] in TRIO_FIELDS
    return False


def _get_nested(household, target):
    if not target or not household:
        return ''
    parts = target.split('.')
    if parts[0] == 'household':
        val = getattr(household, parts[1], '')
    elif parts[0] == 'caregiver':
        cg = getattr(household, 'caregiver', None)
        val = getattr(cg, parts[1], '') if cg else ''
    elif parts[0] == 'member' and len(parts) >= 3 and parts[1].isdigit():
        members = list(household.members.order_by('id'))
        idx = int(parts[1])
        person = members[idx] if idx < len(members) else None
        val = getattr(person, parts[2], '') if person else ''
    else:
        return ''
    if val is True:
        return 'true'
    if val is False:
        return 'false'
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    return '' if val is None else str(val)


def values_for_household(household):
    values = {}
    seen = set()
    for field in fields_for('c01') + fields_for('intake') + fields_for('c02') + fields_for('c03') + fields_for('family_care_plan') + fields_for('cow2_note'):
        target = field.get('target')
        if not target or target in seen:
            continue
        seen.add(target)
        values[target] = _get_nested(household, target)
    if household:
        names = [u.get_full_name() or u.username for u in household.assigned_to.all()]
        values['__display.personnel'] = ', '.join(names)
    return values


def _parse_date(value):
    raw = (value or '').strip()
    if not raw:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw


def _boolish(value):
    if value in (True, False):
        return value
    text = str(value or '').strip().lower()
    if text in ('true', 'yes', '1'):
        return True
    if text in ('false', 'no', '0'):
        return False
    return value


def buckets_from_values(values):
    buckets = {}
    for target, value in (values or {}).items():
        if not target or target.startswith('__') or value in (None, ''):
            continue
        buckets[target] = value
    return buckets


def _mark_confirmed(person_data, prefix, confirmed, derived):
    """Set the *_confirmed flags this person's values have actually earned.

    A value only counts as confirmed when a staff member signed off that
    target, or when it was worked out from an ID number they signed off
    (a date of birth read straight off the ID digits). An unchecked reading
    of the paper never confirms itself.
    """
    id_signed = f'{prefix}.id_number' in confirmed
    for trio in TRIO_FIELDS:
        if not person_data.get(trio):
            continue
        if f'{prefix}.{trio}' in confirmed or (trio in derived and id_signed):
            person_data[f'{trio}_confirmed'] = True


def apply_buckets(request, household, buckets, create=False, confirmed_targets=None):
    """Write atlas buckets via existing serializers. Returns household.

    `confirmed_targets` is the set of targets a staff member explicitly signed
    off. Only those set the model's *_confirmed flags — an extracted value on
    its own is never treated as verified. Because ConfirmMixin refuses to save
    an unconfirmed surname, ID or date of birth, callers must gate those
    targets before they get here (Scan Intake does this in `confirm`).
    """
    confirmed = set(confirmed_targets or ())
    ctx = {'request': request}
    hh_data = {}
    for key, value in buckets.items():
        if key.startswith('household.') and key != 'household.org_household_number':
            field = key.split('.', 1)[1]
            if field.endswith('date') or field == 'date_registered':
                value = _parse_date(value) or value
            hh_data[field] = value
    scanned_number = buckets.get('household.org_household_number') or ''

    if household:
        if hh_data:
            ser = HouseholdSerializer(household, data=hh_data, partial=True, context=ctx)
            ser.is_valid(raise_exception=True)
            household = ser.save()
    else:
        create_data = dict(hh_data)
        from .permissions import is_training_user
        if scanned_number:
            prefix_ok = (
                scanned_number.upper().startswith('TEST')
                if is_training_user(request.user)
                else not scanned_number.upper().startswith('TEST')
            )
            if prefix_ok:
                create_data['org_household_number'] = scanned_number
        ser = HouseholdSerializer(data=create_data, context=ctx)
        ser.is_valid(raise_exception=True)
        household = ser.save()
        from .permissions import is_field_worker
        from .views import _ensure_checklist
        if is_field_worker(request.user):
            household.assigned_to.add(request.user)
        _ensure_checklist(household)

    cg_data = {}
    for key, value in buckets.items():
        if not key.startswith('caregiver.'):
            continue
        field = key.split('.', 1)[1]
        if field in ('date_of_birth', 'date_joined'):
            value = _parse_date(value) or value
        if field == 'disability':
            value = _boolish(value)
        cg_data[field] = value
    derived = set()
    if cg_data.get('id_number'):
        parsed = parse_sa_id(cg_data['id_number'])
        if parsed.get('dob') and not cg_data.get('date_of_birth'):
            cg_data['date_of_birth'] = parsed['dob']
            derived.add('date_of_birth')
        if parsed.get('sex') and not cg_data.get('sex'):
            cg_data['sex'] = parsed['sex']
    _mark_confirmed(cg_data, 'caregiver', confirmed, derived)
    if cg_data:
        existing = Caregiver.objects.filter(household=household).first()
        if existing:
            ser = CaregiverSerializer(existing, data=cg_data, partial=True, context=ctx)
        else:
            cg_data['household'] = household.id
            ser = CaregiverSerializer(data=cg_data, context=ctx)
        ser.is_valid(raise_exception=True)
        ser.save()

    by_slot = {}
    for key, value in buckets.items():
        parts = key.split('.')
        if parts[0] != 'member' or len(parts) < 3 or not parts[1].isdigit():
            continue
        slot = int(parts[1])
        field = parts[2]
        if field in ('date_of_birth', 'date_joined'):
            value = _parse_date(value) or value
        if field == 'disability':
            value = _boolish(value)
        by_slot.setdefault(slot, {})[field] = value

    members = list(HouseholdMember.objects.filter(household=household).order_by('id'))
    for slot, mem_data in sorted(by_slot.items()):
        if not any(str(v).strip() for v in mem_data.values() if v not in (None, False)):
            continue
        derived = set()
        if mem_data.get('id_number'):
            parsed = parse_sa_id(mem_data['id_number'])
            if parsed.get('dob') and not mem_data.get('date_of_birth'):
                mem_data['date_of_birth'] = parsed['dob']
                derived.add('date_of_birth')
            if parsed.get('sex') and not mem_data.get('sex'):
                mem_data['sex'] = parsed['sex']
        _mark_confirmed(mem_data, f'member.{slot}', confirmed, derived)
        if slot < len(members):
            ser = HouseholdMemberSerializer(members[slot], data=mem_data, partial=True, context=ctx)
        else:
            mem_data['household'] = household.id
            ser = HouseholdMemberSerializer(data=mem_data, context=ctx)
        ser.is_valid(raise_exception=True)
        saved = ser.save()
        if slot >= len(members):
            members.append(saved)
    return household
