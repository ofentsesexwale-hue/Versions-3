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
    """True for keyboard-smash OCR like hgftrujyfdyt."""
    text = ' '.join((value or '').split())
    if not text:
        return False
    letters = _letters(text)
    if len(letters) < 5:
        return False
    if not any(v in letters for v in _VOWELS):
        return True
    if re.search(r'[' + ''.join(_CONSONANTS) + r']{5,}', letters):
        return True
    # Almost every character unique and no repeated syllable — typical Tesseract noise.
    if len(letters) >= 8 and len(set(letters)) / len(letters) >= 0.82:
        return True
    # Mixed case random inside a token (HgFtRu).
    tokens = re.findall(r"[A-Za-z]+", text)
    for token in tokens:
        if len(token) >= 6:
            flips = sum(1 for a, b in zip(token, token[1:]) if a.isupper() != b.isupper())
            if flips >= 3 and not token.isupper() and not token.istitle():
                return True
    return False


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


def sanitize_ocr_value(target, value, kind=None):
    text = ' '.join((value or '').split())
    if not text:
        return ''
    if kind == 'sa_id' or (target or '').endswith('id_number'):
        return text
    if looks_like_gibberish(text):
        return ''
    if target in _NAME_TARGETS or (target or '').endswith('.name') or (target or '').endswith('.surname') or (target or '').endswith('.known_as'):
        cleaned = first_name_words(text)
        return cleaned if plausible_person_name(cleaned) else ''
    if target in _PLACE_TARGETS:
        # One or two words after the label, not the rest of the page.
        clipped = ' '.join(text.split()[:4])
        return clipped if plausible_place(clipped) else ''
    if kind in ('handwrite', 'narrative') and looks_like_gibberish(text):
        return ''
    return text
