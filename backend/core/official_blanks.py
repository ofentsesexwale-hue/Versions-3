"""Canonical blank pages for fill, print, and Scan Intake.

Official Word (and converted .doc→.docx) blanks live under ``official_blanks/``.
The NPO case-management PDF is a file-order guide only — never invent a second
HTML layout for statutory sheets.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

BLANKS_DIR = Path(__file__).resolve().parent / 'official_blanks'
META_PATH = BLANKS_DIR / 'blanks.json'
ATLAS_VERSION = 'word-c01-c02-c03-cw05-fcp-hiv-remaining-cow2-v2.6'


def load_meta():
    return json.loads(META_PATH.read_text())


def blank_path(code, page_index):
    meta = load_meta()
    info = meta['pages'].get(f'{code}:{page_index}')
    if not info:
        return None
    return BLANKS_DIR / info['file']


def blank_info(code, page_index):
    return load_meta()['pages'].get(f'{code}:{page_index}')


def page_count(code):
    meta = load_meta()
    n = 0
    while f'{code}:{n}' in meta['pages']:
        n += 1
    return n


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
