"""Two document trees for the physical NPO case file.

Tree A — Physical case file (reprint order)
  MEDIA_ROOT/case-files/{org_household_number}/
    01_Intake_Forms/{C01|C02|C03|CW05}/…
    02_Family_Care_Plans/…
    03_Vital_Documents/          (index only — bytes live in Tree B)
    04_Process_Notes/…
    05_School_Visit_Reports/…
    06_Referral_Forms/…
    07_Success_Stories/…
    08_Monthly_Reports/…

Tree B — Vital documents cabinet (Home Affairs / clinic originals)
  MEDIA_ROOT/vital-documents/
    {Surname}, {Name} ({org_household_number})/
      {HouseNumber} {Street}, {Town}/
        Parent-guardian/
          Parents ID/…
          Death certificate/…
        Child - {Name} {Surname}/
          Birth certificate/…
          Clinic card/…
          Report card/…

These trees are separate from Scan Intake OCR storage (scan_intake/).
Vital uploads are never OCR'd — SupportingDocument stores original bytes.
Stored basenames are prefixed YYYYMMDDHHMMSS_ so camera duplicates cannot overwrite.
"""
from __future__ import annotations

import os
import re
import shutil
from datetime import datetime
from pathlib import Path, PurePosixPath

from django.conf import settings

from . import choices

# Windows-illegal filename characters + control chars / trailing dots & spaces.
_WIN_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WIN_RESERVED = {
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{i}' for i in range(1, 10)),
    *(f'LPT{i}' for i in range(1, 10)),
}

# Tree A section folders — order matches CATEGORY_CHOICES / Content Page.
PHYSICAL_CASE_SECTIONS: list[tuple[str, str]] = [
    ('intake_form', '01_Intake_Forms'),
    ('family_care_plan', '02_Family_Care_Plans'),
    ('vital_document', '03_Vital_Documents'),
    ('process_note', '04_Process_Notes'),
    ('school_report', '05_School_Visit_Reports'),
    ('referral_form', '06_Referral_Forms'),
    ('success_story', '07_Success_Stories'),
    ('monthly_report', '08_Monthly_Reports'),
]

PHYSICAL_SECTION_BY_CATEGORY = dict(PHYSICAL_CASE_SECTIONS)

# Checklist sub_item → (attach_to, Tree B leaf folder under person).
# attach_to: 'caregiver' | 'member'
VITAL_SUBITEM_SPEC: dict[str, tuple[str, str]] = {
    "Parents' ID's": ('caregiver', 'Parents ID'),
    'Death Certificates': ('caregiver', 'Death certificate'),
    'Birth certificates': ('member', 'Birth certificate'),
    'Clinic Card': ('member', 'Clinic card'),
    'Report card': ('member', 'Report card'),
}

CAREGIVER_VITAL_SUBITEMS = {
    k for k, (who, _) in VITAL_SUBITEM_SPEC.items() if who == 'caregiver'
}
MEMBER_VITAL_SUBITEMS = {
    k for k, (who, _) in VITAL_SUBITEM_SPEC.items() if who == 'member'
}


def windows_safe_name(value: str, *, fallback: str = 'Unknown', max_len: int = 120) -> str:
    """Sanitize a path segment for Windows file systems."""
    text = str(value or '').strip()
    text = _WIN_BAD.sub('_', text)
    text = re.sub(r'\s+', ' ', text).strip(' .')
    if not text:
        text = fallback
    if text.upper() in _WIN_RESERVED:
        text = f'_{text}'
    if len(text) > max_len:
        text = text[:max_len].rstrip(' .')
    return text or fallback


def original_filename(filename: str) -> str:
    """Keep the original basename; only neutralize path separators / illegals."""
    name = (filename or 'upload.bin').replace('\\', '/').split('/')[-1]
    return windows_safe_name(name, fallback='upload.bin', max_len=180)


def stamped_filename(filename: str, when: datetime | None = None) -> str:
    """Prefix basename with YYYYMMDDHHMMSS so IMG_3701.jpg cannot overwrite itself."""
    stamp = (when or datetime.now()).strftime('%Y%m%d%H%M%S')
    base = original_filename(filename)
    if re.match(r'^\d{14}_', base):
        return base
    return f'{stamp}_{base}'


def category_order_keys() -> list[str]:
    """Category keys in Content Page / checklist order."""
    return [key for key, _label in choices.CATEGORY_CHOICES]


def subitems_for_category(category: str) -> list[str]:
    return [sub for cat, sub in choices.CHECKLIST_TEMPLATE if cat == category]


def resolve_household(parent):
    """Return the Household for a caregiver, member, or household instance."""
    from .models import Caregiver, Household, HouseholdMember

    if isinstance(parent, Household):
        return parent
    if isinstance(parent, (Caregiver, HouseholdMember)):
        return parent.household
    return None


def tree_a_relative_path(household, category: str, sub_item: str, filename: str) -> str:
    """Relative path under MEDIA_ROOT for Tree A (physical case file)."""
    org = windows_safe_name(
        getattr(household, 'org_household_number', None) or f'HH-{household.pk}',
        fallback=f'HH-{household.pk}',
    )
    section = PHYSICAL_SECTION_BY_CATEGORY.get(category) or '99_Other'
    sub = windows_safe_name(sub_item or 'General', fallback='General')
    return str(PurePosixPath('case-files', org, section, sub, stamped_filename(filename)))


def _address_folder(household) -> str:
    house = windows_safe_name(getattr(household, 'house_number', '') or '', fallback='')
    street = windows_safe_name(getattr(household, 'street', '') or '', fallback='')
    town = windows_safe_name(getattr(household, 'town', '') or '', fallback='Town')
    left = ' '.join(p for p in (house, street) if p).strip() or 'Address'
    return windows_safe_name(f'{left}, {town}', fallback='Address')


def _caregiver_root_folder(household) -> str:
    caregiver = getattr(household, 'caregiver', None)
    surname = windows_safe_name(getattr(caregiver, 'surname', '') or '', fallback='Surname')
    name = windows_safe_name(getattr(caregiver, 'name', '') or '', fallback='Name')
    org = windows_safe_name(
        getattr(household, 'org_household_number', None) or f'HH-{household.pk}',
        fallback=f'HH-{household.pk}',
    )
    return windows_safe_name(f'{surname}, {name} ({org})', fallback=f'Household ({org})')


def _child_folder(member) -> str:
    name = windows_safe_name(getattr(member, 'name', '') or '', fallback='Name')
    surname = windows_safe_name(getattr(member, 'surname', '') or '', fallback='Surname')
    return windows_safe_name(f'Child - {name} {surname}', fallback='Child')


def tree_b_relative_path(household, parent, sub_item: str, filename: str) -> str:
    """Relative path under MEDIA_ROOT for Tree B (vital-documents cabinet)."""
    from .models import Caregiver, HouseholdMember

    root = _caregiver_root_folder(household)
    address = _address_folder(household)
    spec = VITAL_SUBITEM_SPEC.get(sub_item or '')
    leaf = windows_safe_name(spec[1] if spec else (sub_item or 'Vital'), fallback='Vital')

    if isinstance(parent, Caregiver) or (spec and spec[0] == 'caregiver'):
        person_folder = 'Parent-guardian'
    elif isinstance(parent, HouseholdMember):
        person_folder = _child_folder(parent)
    else:
        if spec and spec[0] == 'member':
            person_folder = 'Child - Unknown'
        else:
            person_folder = 'Parent-guardian'

    return str(PurePosixPath(
        'vital-documents', root, address, person_folder, leaf, stamped_filename(filename),
    ))


def is_vital_category(category: str) -> bool:
    return category == 'vital_document'


def expected_parent_kind(category: str, sub_item: str) -> str | None:
    """Return 'caregiver' / 'householdmember' when the vital sub_item dictates it."""
    if not is_vital_category(category):
        return None
    spec = VITAL_SUBITEM_SPEC.get(sub_item or '')
    if not spec:
        return None
    return 'caregiver' if spec[0] == 'caregiver' else 'householdmember'


def document_storage_path(instance, filename: str) -> str:
    """``upload_to`` callable: Tree B for vitals, Tree A for everything else.

    Scan Intake pages keep using ``scan_page_upload_path`` and must not call this.
    """
    parent = None
    try:
        parent = instance.content_object
    except Exception:
        parent = None

    household = resolve_household(parent) if parent is not None else None
    category = getattr(instance, 'category', '') or ''
    sub_item = getattr(instance, 'sub_item', '') or ''

    if household is not None and is_vital_category(category):
        return tree_b_relative_path(household, parent, sub_item, filename)

    if household is not None:
        return tree_a_relative_path(household, category, sub_item, filename)

    kind = getattr(instance, 'parent_kind', '') or 'record'
    oid = getattr(instance, 'object_id', None) or 0
    return str(PurePosixPath('documents', f'{kind}_{oid}_{stamped_filename(filename)}'))


def hardlink_or_copy_into_tree_a(household, category: str, sub_item: str, source_path, filename: str) -> str:
    """Hardlink (or copy) a scan page into Tree A. Leaves the source file untouched.

    Returns the MEDIA_ROOT-relative path. Does not run OCR.
    """
    rel = tree_a_relative_path(household, category, sub_item, filename)
    dest = Path(settings.MEDIA_ROOT) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = Path(source_path)
    if not src.is_file():
        raise FileNotFoundError(f'Scan page image missing: {src}')
    if dest.resolve() == src.resolve():
        return rel
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        n = 2
        while dest.exists():
            dest = dest.with_name(f'{stem}_{n}{suffix}')
            n += 1
        rel = str(PurePosixPath(*dest.relative_to(settings.MEDIA_ROOT).parts))
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)
    return rel


def mark_checklist_has_evidence(household, category: str, sub_item: str, user=None) -> bool:
    """Set the matching CaseFileChecklistItem.has_evidence to Yes. Returns True if updated."""
    if not household or not category or not sub_item:
        return False
    item = household.checklist_items.filter(category=category, sub_item=sub_item).first()
    if not item:
        return False
    from django.utils import timezone

    item.has_evidence = 'Yes'
    update = ['has_evidence']
    if user is not None:
        item.checked_by = user
        item.checked_at = timezone.now()
        update.extend(['checked_by', 'checked_at'])
    item.save(update_fields=update)
    return True
