"""The words printed on the official sheets, so a label cannot pass as a value.

Full-page OCR reads the form's own printed labels alongside the handwriting,
and nothing downstream could tell the two apart: 'SURNAME', 'FIRST NAME',
'ID NO' and 'Date of Birth' were all accepted verbatim as field values.

The lexicon is derived, never typed out by hand. It comes from the field atlas
(the label and tick-option text measured off each official blank), the print
templates that reproduce those sheets, and the label wording the keyword
extractor searches for. Adding a field to a form therefore adds its label here
too, and nothing has to be kept in step by hand.
"""
import html
import re
from functools import lru_cache
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent / 'templates' / 'print'

# The sheets Scan Intake reads. C01/C02/C03 print through the official-blank
# canvas rather than an HTML template, so their labels come from the atlas.
SCANNED_FORMS = ('c01', 'c02', 'c03', 'intake', 'cow2_note')

# Label wording the keyword extractor looks for in the full-page text. Kept
# here rather than inline in scan_templates so that a label it searches for is
# automatically a label it will refuse to hand back as a value.
EXTRACTION_LABELS = {
    'caregiver.surname': ['Primary Client Surname', 'Caregiver Surname', 'Surname'],
    'caregiver.name': ['Primary Client First name', 'Caregiver First name', 'First name'],
    'household.org_household_number': [
        'Intake Ref Number', 'Org Household Nr', 'Org Household Number', 'Org Household Nr.',
    ],
    'household.house_number': ['House Number'],
    'household.street': ['Street'],
    'household.town': ['Town', 'Town / City'],
    'household.province': ['Province'],
    'household.district': ['District'],
    'household.municipality': ['Municipality'],
    'household.ward': ['Ward'],
    'caregiver.cell_number': ['Cell', 'Cell number', 'Cell Number', 'Contact'],
    'caregiver.known_as': ['Known As'],
    'caregiver.home_language': ['Home Language'],
    'process_note.client_surname': ['Client surname', 'Surname'],
    'process_note.client_first_name': ['Client first name', 'First name'],
    'process_note.file_no': ['File no', 'File number'],
    'process_note.purpose_and_what_transpired': [
        'Purpose and what transpired', 'What transpired',
    ],
    'process_note.outcome_and_follow_up': ['Outcome and follow up', 'Follow up'],
    'process_note.problem_code': ['Problem code', 'Primary Problem Code'],
    'care_plan.overall_goal': ['Overall goal', 'Overall Goal'],
    'care_plan.ssp_name': ['SSP Name', 'SSP name'],
    'member.hiv_status': ['HIV status', 'HIV Status'],
    'member.on_art': ['On ART'],
    'member.last_viral_load': ['Viral load', 'Last viral load'],
    'assessment.overview_situation': ['Overview', 'Situation'],
    'assessment.problem_codes': ['Primary Problem Code', 'Problem Code'],
    'assessment.overall_goal': ['Overall goal'],
    'member.school_name': ['School name', 'School Name'],
    'member.grade': ['Grade'],
}

# Printed wording that appears on the sheets in short form and so never shows
# up as a template label or an atlas label. Each is built from words that are
# already in the lexicon vocabulary, so the word rule below catches them; they
# are listed for the tests to assert against directly.
SHORT_FORM_LABELS = ('ID NO', 'ID NO.', 'FIRST NAME', 'NO', 'REF NO')

_TAG = re.compile(r'<[^>]+>')
_DJANGO = re.compile(r'\{\{.*?\}\}|\{%.*?%\}', re.S)
_LABEL_SPAN = re.compile(r'<span\s+class="lbl">(.*?)</span>', re.S | re.I)
_TABLE_HEAD = re.compile(r'<th[^>]*>(.*?)</th>', re.S | re.I)
_SUB_HEAD = re.compile(r'<h3\s+class="sub">(.*?)</h3>', re.S | re.I)
_FORM_TITLE = re.compile(r'<div\s+class="ftitle">(.*?)</div>', re.S | re.I)


def _plain(fragment):
    text = _DJANGO.sub(' ', fragment or '')
    text = _TAG.sub(' ', text)
    text = html.unescape(text).replace('\xa0', ' ')
    return ' '.join(text.split())


def normalise_label(value):
    """Letters and digits only, lowercased - 'ID No.' and 'ID  no' are one label."""
    return re.sub(r'[^a-z0-9]+', '', (value or '').lower())


def _template_labels(code):
    from .print_views import FORMS

    entry = FORMS.get(code)
    if not entry:
        return []
    path = TEMPLATE_DIR / Path(entry[0]).name
    if not path.exists():
        return []
    raw = path.read_text(encoding='utf-8')
    out = []
    for pattern in (_LABEL_SPAN, _TABLE_HEAD, _SUB_HEAD, _FORM_TITLE):
        for fragment in pattern.findall(raw):
            text = _plain(fragment)
            if text:
                out.append(text)
    return out


def printed_labels(forms=SCANNED_FORMS):
    """Every label printed on the given sheets, as written on the paper."""
    from .form_atlas import FIELDS

    out = []
    for code in forms:
        for spec in FIELDS.get(code) or []:
            if spec.get('label'):
                out.append(spec['label'])
            option = spec.get('option')
            # Tick captions are printed on the sheet too, so 'Passport Number'
            # must not pass as somebody's surname. Checkbox fields are exempt
            # from the lexicon when sanitised, so their own answers survive.
            if option and option not in ('true', 'false'):
                out.append(option)
        out.extend(_template_labels(code))
    for labels in EXTRACTION_LABELS.values():
        out.extend(labels)
    out.extend(SHORT_FORM_LABELS)
    seen, unique = set(), []
    for label in out:
        key = normalise_label(label)
        if key and key not in seen:
            seen.add(key)
            unique.append(label)
    return unique


@lru_cache(maxsize=1)
def option_targets():
    """Fields whose answer is the caption printed beside a tick.

    Sex, race, marital status, nationality, headship and type of ID all answer
    with words that are printed on the sheet, so the label lexicon has to stand
    aside for them or it would throw away every real answer.
    """
    from .form_atlas import FIELDS

    return frozenset(
        spec['target'] for code in FIELDS for spec in FIELDS[code]
        if spec['kind'] == 'checkbox' and spec.get('target')
    )


@lru_cache(maxsize=1)
def _lexicon():
    labels = printed_labels()
    exact = frozenset(normalise_label(label) for label in labels)
    words = set()
    for label in labels:
        for word in re.split(r'[^A-Za-z]+', label):
            if word:
                words.add(word.lower())
    return exact, frozenset(words)


def looks_like_form_label(value, max_words=6):
    """True when the candidate is the form's own printed wording, not an answer.

    Two ways in. A candidate that matches a printed label outright, ignoring
    case, spacing and punctuation. Or a short candidate built entirely out of
    label words, which is how the abbreviations on the paper ('ID NO',
    'FIRST NAME') and the run-together label pairs that full-page OCR produces
    are caught without a hand-written list of every variant.
    """
    text = ' '.join((value or '').split())
    if not text:
        return False
    exact, words = _lexicon()
    if normalise_label(text) in exact:
        return True
    tokens = [w.lower() for w in re.split(r'[^A-Za-z]+', text) if w]
    if not tokens or len(tokens) > max_words:
        return False
    return all(token in words for token in tokens)
