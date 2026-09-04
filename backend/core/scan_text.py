"""Reject Tesseract smash-text so names like Hallie are not replaced with junk."""
import re

_VOWELS = set('aeiou')
_CONSONANTS = set('bcdfghjklmnpqrstvwxyz')
_NAME_TARGETS = {
    'caregiver.name', 'caregiver.surname', 'caregiver.known_as',
    'member.0.name', 'member.0.surname', 'member.0.known_as',
    'member.1.name', 'member.1.surname', 'member.1.known_as',
    'member.2.name', 'member.2.surname', 'member.2.known_as',
    'member.3.name', 'member.3.surname', 'member.3.known_as',
    'process_note.client_surname', 'process_note.client_first_name',
}
_PLACE_TARGETS = {
    'household.town', 'household.street', 'household.province',
    'household.district', 'household.municipality', 'caregiver.home_language',
}


def _letters(text):
    return ''.join(ch for ch in (text or '') if ch.isalpha()).lower()


def looks_like_gibberish(value):
    """True for keyboard-smash OCR like hgftrujyfdyt, or the form's own labels.

    Full-page OCR cannot tell a printed label from the handwriting beside it,
    so 'SURNAME' and 'ID NO' arrive looking exactly like answers. The charset
    rules cannot catch those - they are real words - so the printed wording is
    checked as well. Both tests apply; neither replaces the other.
    """
    from .form_labels import looks_like_form_label
    text = ' '.join((value or '').split())
    if not text:
        return False
    return looks_like_form_label(text) or _looks_like_smash(text)


def _looks_like_smash(value):
    """The charset and shape rules on their own, with no label lexicon."""
    text = ' '.join((value or '').split())
    if not text:
        return False
    # Printed table chrome that lands in handwriting boxes ("Member 4.", "IVember 4.", "Add-Member-1").
    if re.search(r'(?:member|[mv]?ember)', text, re.I) and re.search(r'\d', text):
        return True
    if re.search(r'\badd[\s\-]*m?ember\b', text, re.I):
        return True
    # Cropped "Describe:" label from the nationality / disability row.
    if re.fullmatch(r'd?escribe:?', text, re.I):
        return True
    letters = _letters(text)
    # Sparse ruling-noise OCR: "te re ee", "fe eee" (several tiny tokens).
    tokens = [t for t in re.split(r'[^A-Za-z]+', text) if t]
    if len(tokens) >= 2 and all(len(t) <= 2 for t in tokens) and len(letters) <= 8:
        return True
    if letters and set(letters) <= set('eosatrn') and len(letters) >= 4 and len(set(letters)) <= 3:
        return True
    # "fe eee" / "eae" style ruling noise: mostly e with tiny helpers.
    if len(letters) >= 4 and letters.count('e') / len(letters) >= 0.6:
        return True
    if len(letters) >= 3 and len(set(letters)) == 1:
        return True
    # Long runs of the same few letters (EYIMIIIMMI) are table-rule noise.
    if len(letters) >= 8 and len(set(letters)) <= 4:
        if max(letters.count(ch) for ch in set(letters)) >= 4:
            return True
    if len(letters) < 5:
        return False
    if not any(v in letters for v in _VOWELS):
        return True
    if re.search(r'[' + ''.join(_CONSONANTS) + r']{6,}', letters):
        return True
    # Keyboard smash is long with almost no repeated letters *and* no real vowels clusters.
    if len(letters) >= 12 and len(set(letters)) / len(letters) >= 0.92:
        if not re.search(r'[aeiou]{1}[a-z]{1,3}[aeiou]', letters):
            return True
    return False


def title_case_name(value):
    """Light title-case for person names after OCR (Thato, not thato)."""
    parts = []
    for raw in (value or '').split():
        if not raw:
            continue
        if raw.isupper() and len(raw) > 1:
            parts.append(raw.capitalize())
        elif raw.islower():
            parts.append(raw.capitalize())
        else:
            parts.append(raw[0].upper() + raw[1:] if raw else raw)
    return ' '.join(parts)


def split_glued_name_caps(value):
    """Insert spaces where RapidOCR glued GivenNameSurname without a gap.

    'SisiLebtie' → 'Sisi Lebtie', 'otshelaMicsegc' → 'otshela Micsegc'.
    """
    text = ' '.join((value or '').split())
    if not text:
        return ''
    return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text).strip()


def plausible_person_name(value):
    text = ' '.join((value or '').split())
    if len(text) < 2 or len(text) > 48:
        return False
    if looks_like_gibberish(text):
        return False
    letters = _letters(text)
    if len(letters) < 2:
        return False
    compact = re.sub(r'[\s\'\-]', '', text)
    if not compact or len(letters) / len(compact) < 0.8:
        return False
    if not any(v in letters for v in _VOWELS):
        return False
    if re.search(r'\d{3,}', text):
        return False
    return True


def first_name_words(value, limit=3):
    """Keep the first plausible name tokens; drop trailing OCR junk."""
    words = []
    for raw in (value or '').replace(',', ' ').split():
        token = re.sub(r'[^A-Za-z\'\-]', '', raw)
        if not token:
            if words:
                break
            continue
        if not plausible_person_name(token) and not (token.isalpha() and 2 <= len(token) <= 14 and any(v in token.lower() for v in _VOWELS)):
            break
        if looks_like_gibberish(token):
            break
        words.append(token)
        if len(words) >= limit:
            break
    return ' '.join(words)


def plausible_place(value):
    text = ' '.join((value or '').split())
    if len(text) < 2 or len(text) > 60:
        return False
    if looks_like_gibberish(text):
        return False
    letters = _letters(text)
    return len(letters) >= 2 and any(v in letters for v in _VOWELS)


_DATE_SPLIT = re.compile(r'[^0-9]+')
# Separators are normalised to '-' first, so only these three orders are tried.
# Year-first is unambiguous; the rest read day-first, as written in South Africa.
_DATE_FORMATS = ('%Y-%m-%d', '%d-%m-%Y', '%d-%m-%y')
MAX_AGE_YEARS = 120


def _plausible_date(parsed, today):
    if parsed is None or parsed > today:
        return False
    return today.year - parsed.year <= MAX_AGE_YEARS


def normalise_date_value(value):
    """An ISO date, or nothing. A half-read date is not a date.

    Handwritten date boxes come back as '99b1 Ol11/', 'be-no-bloe' and
    'Z1107o2 12'. None of those are dates, and offering them to staff only
    buys a pointless confirm click on junk, so a candidate has to parse as a
    real calendar date within living memory or it counts as unread. Same rule
    as an SA ID after Phase 3: the whole thing or nothing.
    """
    from datetime import date, datetime

    text = ' '.join((value or '').split())
    if not text:
        return ''
    parts = [p for p in _DATE_SPLIT.split(text) if p]
    today = date.today()
    if len(parts) == 1 and len(parts[0]) == 8:
        # A date grid can read back as one run of digits.
        try:
            parsed = datetime.strptime(parts[0], '%Y%m%d').date()
        except ValueError:
            return ''
        return parsed.isoformat() if _plausible_date(parsed, today) else ''
    if len(parts) != 3:
        return ''
    joined = '-'.join(parts)
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(joined, fmt).date()
        except ValueError:
            continue
        if fmt == '%d-%m-%y' and parsed > today:
            # strptime reads '55' as 2055; a birth date means 1955.
            try:
                parsed = parsed.replace(year=parsed.year - 100)
            except ValueError:
                continue
        if _plausible_date(parsed, today):
            return parsed.isoformat()
    return ''


def sanitize_ocr_value(target, value, kind=None):
    text = ' '.join((value or '').split())
    if not text:
        return ''
    if kind == 'checkbox':
        # The tick is the evidence here, not the text beside it.
        return text
    if kind == 'date' or (target or '').endswith(('date_of_birth', 'date_joined',
                                                  'date_registered')):
        return normalise_date_value(text)
    from .form_labels import option_targets
    if (target or '') in option_targets():
        # 'Female' and 'African' are captions printed on the sheet as well as
        # real answers, including when worked out from an ID number, so only
        # the charset rules apply to a choice field.
        return '' if _looks_like_smash(text) else text
    # Closed-list answers (nationality, relationship) are also printed on the
    # form as captions. Once OCR / vocab has produced the canonical string,
    # keep it — looks_like_gibberish would otherwise blank 'South African'.
    from .scan_vocab import CLOSED_TEXT, match_closed_text
    if target in CLOSED_TEXT:
        hit, _score = match_closed_text(target, text)
        if hit:
            return hit
        if text in CLOSED_TEXT[target]:
            return text
    if kind == 'sa_id' or (target or '').endswith('id_number'):
        # Spaces and dashes are normal on a form; a short read is not a short
        # ID. Returning the partial digits is what put '74' and '4' into ID
        # fields, so anything that is not 13 digits is simply unreadable.
        from .sa_id import id_digits, repair_sa_id_digits
        digits = id_digits(text)
        if not digits:
            return ''
        return repair_sa_id_digits(digits)
    if looks_like_gibberish(text):
        return ''
    if target in _NAME_TARGETS or (target or '').endswith('.name') or (target or '').endswith('.surname') or (target or '').endswith('.known_as'):
        cleaned = first_name_words(split_glued_name_caps(text))
        if not plausible_person_name(cleaned):
            return ''
        return title_case_name(cleaned)
    if target in _PLACE_TARGETS:
        # One or two words after the label, not the rest of the page.
        clipped = ' '.join(text.split()[:4])
        return clipped if plausible_place(clipped) else ''
    if kind in ('handwrite', 'narrative') and looks_like_gibberish(text):
        return ''
    return text
