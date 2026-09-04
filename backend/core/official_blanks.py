"""Canonical blank pages for fill, print, and Scan Intake.

C01–C03, CW 05, Family Care Plan, and HIV-pack sheet blanks are rendered from
their Official Word templates. Other forms still use the NPO case-management
PDF pages. Never invent a second HTML layout.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

BLANKS_DIR = Path(__file__).resolve().parent / 'official_blanks'
META_PATH = BLANKS_DIR / 'blanks.json'
ATLAS_VERSION = 'word-c01-c02-c03-cw05-fcp-hiv-v2.4'


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
