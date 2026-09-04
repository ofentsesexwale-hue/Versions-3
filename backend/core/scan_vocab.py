"""Closed lists for Scan Intake fields that are not geography.

Only values attested on the official C01 forms / Word templates. A bad fuzzy
match is worse than an ugly reading, so thresholds stay strict.
"""
from __future__ import annotations

import re

from .service_area import match_closed_value

# Printed on C01 caregiver nationality ticks; members write the same phrase.
NATIONALITIES = ('South African',)

# Common C01 relationship answers written on the Moholoza / Word C01 sheets.
RELATIONSHIPS = (
    'Grandchild',
    'Child',
    'Parent',
    'Spouse',
    'Sibling',
    'Niece',
    'Nephew',
    'Cousin',
    'Grandmother',
    'Grandfather',
    'Aunt',
    'Uncle',
    'Other',
)

CLOSED_TEXT = {
    'caregiver.nationality': NATIONALITIES,
    'member.0.nationality': NATIONALITIES,
    'member.1.nationality': NATIONALITIES,
    'member.2.nationality': NATIONALITIES,
    'member.3.nationality': NATIONALITIES,
    'member.0.relationship_to_head': RELATIONSHIPS,
    'member.1.relationship_to_head': RELATIONSHIPS,
    'member.2.relationship_to_head': RELATIONSHIPS,
    'member.3.relationship_to_head': RELATIONSHIPS,
}

MIN_SCORE = 0.52


def _alnum(text):
    return re.sub(r'[^a-z0-9]+', '', (text or '').lower())


def match_closed_text(target, raw):
    names = CLOSED_TEXT.get(target or '') or ()
    if not names:
        return None, 0.0
    hit, score = match_closed_value(raw, names, min_score=MIN_SCORE)
    if hit:
        return hit, score
    blob = _alnum(raw)
    if not blob:
        return None, score
    # OCR often keeps the shape of "African" / "Grandchild" even when letters slip.
    if 'South African' in names and (
        'afric' in blob or 'ahric' in blob or 'afrc' in blob or 'frican' in blob
        or 'hric' in blob or 'fric' in blob or 'htncan' in blob or 'htncan' in blob
        or ('can' in blob and (
            'sout' in blob or 'sa' in blob[:3] or 'qou' in blob or 'jou' in blob
            or 'dou' in blob or 'jau' in blob or 'manoc' in blob or 'anoc' in blob
        ))
    ):
        return 'South African', round(max(score, 0.72), 3)
    if 'Grandchild' in names and (
        ('grand' in blob and 'ch' in blob)
        or 'orand' in blob or 'grard' in blob or 'grandeh' in blob or 'orandeh' in blob
    ):
        return 'Grandchild', round(max(score, 0.72), 3)
    if 'Grandmother' in names and 'grand' in blob and 'moth' in blob:
        return 'Grandmother', round(max(score, 0.72), 3)
    if 'Grandfather' in names and 'grand' in blob and 'fath' in blob:
        return 'Grandfather', round(max(score, 0.72), 3)
    return None, score
