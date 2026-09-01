"""Read/write atlas targets through existing household serializers."""
from datetime import datetime

from .form_atlas import fields_for
from .models import Caregiver, HouseholdMember
from .sa_id import parse_sa_id
from .serializers import CaregiverSerializer, HouseholdMemberSerializer, HouseholdSerializer


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
    for field in fields_for('c01') + fields_for('intake') + fields_for('c02') + fields_for('c03') + fields_for('family_care_plan'):
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


def apply_buckets(request, household, buckets, create=False):
    """Write atlas buckets via existing serializers. Returns household."""
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
    if cg_data.get('id_number'):
        parsed = parse_sa_id(cg_data['id_number'])
        if parsed.get('dob') and not cg_data.get('date_of_birth'):
            cg_data['date_of_birth'] = parsed['dob']
        if parsed.get('sex') and not cg_data.get('sex'):
            cg_data['sex'] = parsed['sex']
    for trio in ('surname', 'id_number', 'date_of_birth'):
        if cg_data.get(trio):
            cg_data[f'{trio}_confirmed'] = True
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
        if mem_data.get('id_number'):
            parsed = parse_sa_id(mem_data['id_number'])
            if parsed.get('dob') and not mem_data.get('date_of_birth'):
                mem_data['date_of_birth'] = parsed['dob']
            if parsed.get('sex') and not mem_data.get('sex'):
                mem_data['sex'] = parsed['sex']
        for trio in ('surname', 'id_number', 'date_of_birth'):
            if mem_data.get(trio):
                mem_data[f'{trio}_confirmed'] = True
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
