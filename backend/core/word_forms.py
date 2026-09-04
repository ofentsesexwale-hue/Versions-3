"""Fill official DSD Word templates. Do not overlay the NPO PDF.

The NPO case-management PDF is a file-order guide only. Print for C01 writes
into ``docs/official/dsd-source/Official_C01_Template.docx``.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from docx import Document

REPO_ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_C01 = REPO_ROOT / 'docs' / 'official' / 'dsd-source' / 'Official_C01_Template.docx'

EMPTY_BOX = '☐'
MARKED_BOX = '☑'


def official_c01_path() -> Path:
    return OFFICIAL_C01


def _clear_cell(cell, text: str = ''):
    """Replace every paragraph in a cell with a single run of ``text``."""
    text = '' if text is None else str(text)
    paragraphs = cell.paragraphs
    if not paragraphs:
        cell.text = text
        return
    first = paragraphs[0]
    for run in list(first.runs):
        run._element.getparent().remove(run._element)
    if first.runs:
        first.runs[0].text = text
    else:
        first.add_run(text)
    for para in paragraphs[1:]:
        para._element.getparent().remove(para._element)


def _set_value_row(row, value: str, value_col: int = 1):
    """Write into the first value cell; mirror across merged duplicates."""
    cells = row.cells
    if value_col >= len(cells):
        return
    _clear_cell(cells[value_col], value)
    # Merged rows often repeat the same cell object; unique cells only.
    seen = {id(cells[value_col]._tc)}
    for cell in cells[value_col + 1:]:
        if id(cell._tc) in seen:
            continue
        # Only overwrite blank lookalikes (merged copies), not a second label.
        if (cell.text or '').strip() in ('', (cells[value_col].text or '').strip()):
            _clear_cell(cell, value)
            seen.add(id(cell._tc))


def _tick_choice(cell_or_text, chosen: str, options: tuple[str, ...] | None = None) -> str:
    """Mark the matching option with ☑ and leave the others ☐."""
    text = cell_or_text.text if hasattr(cell_or_text, 'text') else (cell_or_text or '')
    chosen = (chosen or '').strip()
    if not chosen:
        return text
    working = text.replace(MARKED_BOX, EMPTY_BOX)
    # Longest option first so "Grand Parent Headed" wins over "Parent Headed".
    option_names = sorted(options or (chosen,), key=len, reverse=True)
    match = next((opt for opt in option_names if opt.lower() == chosen.lower()), chosen)
    # Replace only the first "Match  ☐" / "Match ☐" occurrence for that option.
    for gap in ('  ', ' '):
        needle = f'{match}{gap}{EMPTY_BOX}'
        if needle in working:
            return working.replace(needle, f'{match}{gap}{MARKED_BOX}', 1)
    return working


HEADSHIP_OPTIONS = (
    'Grand Parent Headed', 'Parent Headed', 'Youth Headed',
    'Child Headed', 'Relative Headed', 'Other',
)
ID_TYPE_OPTIONS = ('SA ID Number', 'Passport Number', 'Permit')
SEX_OPTIONS = ('Male', 'Female')
RACE_OPTIONS = ('African', 'White', 'Coloured', 'Indian')
NATIONALITY_OPTIONS = ('South African', 'Other')
MARITAL_OPTIONS = ('Married', 'Divorced', 'Widowed', 'Single', 'Cohabiting', 'Separate')
DISABILITY_OPTIONS = ('No', 'Yes')


def _apply_ticks(row, chosen: str, start_col: int = 1, options: tuple[str, ...] | None = None):
    cells = row.cells
    if start_col >= len(cells):
        return
    marked = _tick_choice(cells[start_col], chosen, options=options)
    seen = set()
    for cell in cells[start_col:]:
        if id(cell._tc) in seen:
            continue
        seen.add(id(cell._tc))
        if EMPTY_BOX in (cell.text or '') or MARKED_BOX in (cell.text or ''):
            _clear_cell(cell, marked)


def _member_payload(values: dict, slot: int) -> dict:
    p = f'member.{slot}.'
    return {
        'id_type': values.get(p + 'id_type') or '',
        'id_number': values.get(p + 'id_number') or '',
        'name': values.get(p + 'name') or '',
        'surname': values.get(p + 'surname') or '',
        'known_as': values.get(p + 'known_as') or '',
        'nationality': values.get(p + 'nationality') or '',
        'date_of_birth': values.get(p + 'date_of_birth') or '',
        'sex': values.get(p + 'sex') or '',
        'race': values.get(p + 'race') or '',
        'disability': values.get(p + 'disability') or '',
        'disability_description': values.get(p + 'disability_description') or '',
        'date_joined': values.get(p + 'date_joined') or '',
        'relationship_to_head': values.get(p + 'relationship_to_head') or '',
    }


def _fill_member_table(table, person: dict):
    """Tables 3/4/5: Add member 2/3/4 — label | value."""
    if not any(person.values()):
        return
    _apply_ticks(table.rows[1], person.get('id_type') or 'SA ID Number', options=ID_TYPE_OPTIONS)
    _set_value_row(table.rows[2], person.get('id_number') or '', 1)
    _set_value_row(table.rows[3], person.get('name') or '', 1)
    _set_value_row(table.rows[4], person.get('surname') or '', 1)
    _set_value_row(table.rows[5], person.get('known_as') or '', 1)
    _set_value_row(table.rows[6], person.get('nationality') or '', 1)
    _set_value_row(table.rows[7], person.get('date_of_birth') or '', 1)
    _apply_ticks(table.rows[8], person.get('sex') or '', options=SEX_OPTIONS)
    _apply_ticks(table.rows[9], person.get('race') or '', options=RACE_OPTIONS)
    disability = person.get('disability') or ''
    if disability in ('true', 'True', True, 'yes', 'Yes'):
        label = 'Yes'
    elif disability in ('false', 'False', False, 'no', 'No'):
        label = 'No'
    else:
        label = disability
    marked = _tick_choice(table.rows[10].cells[1], label, options=DISABILITY_OPTIONS)
    if person.get('disability_description'):
        marked = marked.replace('____________________', person['disability_description'])
        marked = marked.replace('___________________', person['disability_description'])
    _clear_cell(table.rows[10].cells[1], marked)
    _set_value_row(table.rows[11], person.get('date_joined') or '', 1)
    _set_value_row(table.rows[12], person.get('relationship_to_head') or '', 1)


def _fill_page1(table, values: dict):
    """Main household + caregiver + member 1 table."""
    _set_value_row(table.rows[1], values.get('household.org_household_number') or '', 1)
    _set_value_row(table.rows[1], values.get('household.province') or '', 3)
    _set_value_row(table.rows[2], values.get('household.house_number') or '', 1)
    _set_value_row(table.rows[2], values.get('household.district') or '', 3)
    _set_value_row(table.rows[3], values.get('household.street') or '', 1)
    _set_value_row(table.rows[3], values.get('household.municipality') or '', 3)
    _set_value_row(table.rows[4], values.get('household.town') or '', 1)
    _set_value_row(table.rows[4], values.get('household.ward') or '', 3)

    personnel = values.get('__display.personnel') or values.get('household.personnel') or ''
    # Personnel row: label in col0, value spans the rest.
    row = table.rows[5]
    if len(row.cells) > 1:
        _clear_cell(row.cells[1], personnel)

    _apply_ticks(table.rows[7], values.get('caregiver.id_type') or 'SA ID Number', options=ID_TYPE_OPTIONS)
    _set_value_row(table.rows[8], values.get('caregiver.id_number') or '', 1)
    _set_value_row(table.rows[9], values.get('caregiver.organisation_beneficiary_number') or '', 1)
    _apply_ticks(table.rows[10], values.get('caregiver.headship') or '', options=HEADSHIP_OPTIONS)
    _set_value_row(table.rows[11], values.get('caregiver.name') or '', 1)
    _set_value_row(table.rows[12], values.get('caregiver.surname') or '', 1)
    _set_value_row(table.rows[13], values.get('caregiver.known_as') or '', 1)
    _apply_ticks(table.rows[14], values.get('caregiver.nationality') or '', options=NATIONALITY_OPTIONS)
    _set_value_row(table.rows[15], values.get('caregiver.date_of_birth') or '', 1)
    _apply_ticks(table.rows[16], values.get('caregiver.sex') or '', options=SEX_OPTIONS)
    _apply_ticks(table.rows[17], values.get('caregiver.race') or '', options=RACE_OPTIONS)
    _apply_ticks(table.rows[18], values.get('caregiver.marital_status') or '', options=MARITAL_OPTIONS)

    disability = values.get('caregiver.disability') or ''
    if disability in ('true', True, 'yes', 'Yes'):
        dlabel = 'Yes'
    elif disability in ('false', False, 'no', 'No'):
        dlabel = 'No'
    else:
        dlabel = disability
    marked = _tick_choice(table.rows[19].cells[1], dlabel, options=DISABILITY_OPTIONS)
    describe = values.get('caregiver.disability_description') or ''
    if describe:
        marked = marked.replace('____________________', describe)
    _clear_cell(table.rows[19].cells[1], marked)

    _set_value_row(table.rows[20], values.get('caregiver.cell_number') or '', 1)
    _set_value_row(table.rows[21], values.get('caregiver.home_language') or '', 1)
    _set_value_row(table.rows[22], values.get('caregiver.date_joined') or '', 1)

    # Relationship to members line.
    rels = []
    for i in range(4):
        rel = values.get(f'member.{i}.relationship_to_head') or ''
        if i == 0 and values.get('caregiver.relationship_to_member_1'):
            rel = values.get('caregiver.relationship_to_member_1') or rel
        rels.append(rel)
    rel_line = (
        f"Member 1 {rels[0] or '_____________'}  "
        f"Member 2 {rels[1] or '______________'}  "
        f"Member 3 {rels[2] or '_________________'}   "
        f"Member 4 {rels[3] or '______________'}"
    )
    _clear_cell(table.rows[23].cells[1], rel_line)

    # Member 1 block (same table).
    m0 = _member_payload(values, 0)
    _apply_ticks(table.rows[25], m0.get('id_type') or ('SA ID Number' if m0.get('id_number') else ''), options=ID_TYPE_OPTIONS)
    _set_value_row(table.rows[26], m0.get('id_number') or '', 1)
    _set_value_row(table.rows[27], m0.get('name') or '', 1)
    _set_value_row(table.rows[28], m0.get('surname') or '', 1)
    _set_value_row(table.rows[29], m0.get('known_as') or '', 1)
    _set_value_row(table.rows[30], m0.get('nationality') or '', 1)
    _set_value_row(table.rows[31], m0.get('date_of_birth') or '', 1)
    _apply_ticks(table.rows[32], m0.get('sex') or '', options=SEX_OPTIONS)
    _apply_ticks(table.rows[33], m0.get('race') or '', options=RACE_OPTIONS)
    disability = m0.get('disability') or ''
    if disability in ('true', True, 'yes', 'Yes'):
        dlabel = 'Yes'
    elif disability in ('false', False, 'no', 'No'):
        dlabel = 'No'
    else:
        dlabel = disability
    marked = _tick_choice(table.rows[34].cells[1], dlabel, options=DISABILITY_OPTIONS)
    if m0.get('disability_description'):
        marked = marked.replace('____________________', m0['disability_description'])
    _clear_cell(table.rows[34].cells[1], marked)
    _set_value_row(table.rows[35], m0.get('date_joined') or '', 1)
    _set_value_row(table.rows[36], m0.get('relationship_to_head') or '', 1)


def fill_c01_docx(values: dict | None = None, template_path: Path | None = None) -> bytes:
    """Return a filled Official C01 .docx (bytes) from atlas-style values."""
    path = Path(template_path or official_c01_path())
    if not path.exists():
        raise FileNotFoundError(f'Official C01 template missing: {path}')
    values = values or {}
    doc = Document(str(path))
    if len(doc.tables) < 6:
        raise ValueError('Official C01 template does not have the expected tables')
    _fill_page1(doc.tables[1], values)
    _fill_member_table(doc.tables[3], _member_payload(values, 1))
    _fill_member_table(doc.tables[4], _member_payload(values, 2))
    _fill_member_table(doc.tables[5], _member_payload(values, 3))
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def values_from_household(household) -> dict:
    """Atlas-style values plus free-text fields the Word sheet needs."""
    from .form_io import values_for_household

    values = values_for_household(household)
    cg = getattr(household, 'caregiver', None)
    if cg:
        mapping = {
            'caregiver.marital_status': 'marital_status',
            'caregiver.cell_number': 'cell_number',
            'caregiver.home_language': 'home_language',
            'caregiver.organisation_beneficiary_number': 'organisation_beneficiary_number',
            'caregiver.nationality': 'nationality',
            'caregiver.headship': 'headship_type',
        }
        for key, attr in mapping.items():
            if values.get(key):
                continue
            raw = getattr(cg, attr, '') if hasattr(cg, attr) else ''
            if raw is True:
                values[key] = 'true'
            elif raw is False:
                values[key] = 'false'
            elif raw is not None and raw != '':
                values[key] = str(raw)
    if household and not values.get('household.municipality'):
        values['household.municipality'] = getattr(household, 'municipality', '') or ''
    return values
