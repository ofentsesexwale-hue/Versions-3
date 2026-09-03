"""Closed vocabularies for Scan Intake geographic fields.

Only place names attested in material supplied with this office file are
listed. Nothing here is filled in from a generic map of South Africa.

What was actually supplied
--------------------------
* The beneficiary-file table of contents (`docs/official/beneficiary-file-contents.png`
  and `BENEFICIARY_FILE_CONTENTS.md`) is a Yes/No evidence checklist. It has
  no provinces, districts, municipalities, towns, or wards.
* The DSD / CCG Word pack (`docs/official/dsd-source/`) includes C01
  (`CCG_Form_C01.docx`) with Province / District / Municipality / Town / Ward
  cells. Those cells are empty on the blank — there is still no list of values
  for this NPO's service area. The NPO PDF is a file-order guide only.
* `seed_data.py` training towns (Umlazi, Soweto, …) are dummy classroom
  data, not this organisation's area — they are not used.
* The only geographic strings in the supplied Scan Intake material are the
  handwritten cells on `c01_household.jpg`, as recorded in Phase 5:
  province GAUTENG, town Westonaria, district West Rand (the synthetic
  round-trip writes RANDWEST into that cell). Street Nkululuthweni is
  free text and is not a closed list.

Fields with no supplied list (municipality, ward) are out of scope: OCR
stays raw and is not forced into a guess.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import re

# Attested on c01_household.jpg / Phase 5 ground truth of that photograph.
PROVINCES = ('Gauteng',)
DISTRICTS = ('West Rand',)
TOWNS = ('Westonaria',)

# No canonical municipality or ward list was supplied.
MUNICIPALITIES = ()
WARDS = ()

GEO_LISTS = {
    'household.province': PROVINCES,
    'household.district': DISTRICTS,
    'household.town': TOWNS,
}

# Explicitly not matched, even though they sit on the same C01 address row.
FREE_TEXT_TARGETS = {
    'household.street',
    'household.house_number',
    '__display.personnel',
}

MIN_SCORE = 0.60
MIN_MARGIN = 0.08


def is_geo_target(target):
    return (target or '') in GEO_LISTS


def _alnum(text):
    return re.sub(r'[^a-z0-9]+', '', (text or '').lower())


def _consonants(text):
    return re.sub(r'[aeiou]', '', _alnum(text))


def _word_sorted(text):
    words = re.findall(r'[a-z0-9]+', (text or '').lower())
    return ''.join(sorted(words)) if words else _alnum(text)


def _score(raw, canonical):
    a, b = _alnum(raw), _alnum(canonical)
    if not a or not b:
        return 0.0
    scores = [SequenceMatcher(None, a, b).ratio()]
    wa, wb = _word_sorted(raw), _word_sorted(canonical)
    scores.append(SequenceMatcher(None, wa, wb).ratio())
    # OCR often mangles vowels (gAaIGNg / GAUTENG). Only use the consonant
    # skeleton when the two strings are about the same length, so a short
    # smash cannot win against a long place name.
    if min(len(a), len(b)) / max(len(a), len(b)) >= 0.7:
        ca, cb = _consonants(raw), _consonants(canonical)
        if ca and cb:
            scores.append(SequenceMatcher(None, ca, cb).ratio())
    return max(scores)


def match_closed_value(raw, canonicals, min_score=MIN_SCORE):
    """Return (canonical, score) or (None, best_score).

    Below the threshold, or when two names are equally close, the raw OCR
    string is left alone — a bad fuzzy match is worse than an ugly reading.
    """
    text = ' '.join((raw or '').split())
    if not text or not canonicals:
        return None, 0.0
    ranked = sorted(
        ((name, _score(text, name)) for name in canonicals),
        key=lambda item: item[1],
        reverse=True,
    )
    best_name, best = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    if best < min_score:
        return None, best
    if second and best - second < MIN_MARGIN:
        return None, best
    return best_name, round(best, 3)


def match_geo_field(target, raw):
    """Match a geographic OCR string against the supplied list for that field."""
    names = GEO_LISTS.get(target or '') or ()
    if not names:
        return None, 0.0
    return match_closed_value(raw, names)
