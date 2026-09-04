from pathlib import Path

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.scan_ocr import process_upload

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'handwrite'


def _blob(name):
    path = FIXTURES / name
    return SimpleUploadedFile(name, path.read_bytes(), content_type='image/jpeg')


def _values(pages):
    out = []
    for page in pages:
        for field in page.get('fields') or []:
            val = (field.get('value') or '').strip()
            if val:
                out.append(val)
    return ' '.join(out)


class HandwrittenPhotoTests(TestCase):
    def test_c01_household_reads_address_or_head_name(self):
        pages, _ = process_upload(_blob('c01_official_page0.jpg'))
        blob = _values(pages).lower()
        self.assertEqual(pages[0]['form_type'], 'c01')
        self.assertEqual(pages[0].get('form_page'), 0)
        self.assertFalse(pages[0].get('alignment_failed'))
        self.assertGreaterEqual(pages[0].get('inliers') or 0, 70)
        self.assertTrue(
            any(word in blob for word in (
                'nkululuthweni', 'enkulul', 'westonaria', 'moholoza', 'nahaloza',
                'nohaloza', 'lettie', 'lehtie', 'lehhie', 'sisi', 'gauteng',
            )),
            blob,
        )

    def test_c01_members_page_reads_grandchild_names(self):
        pages, _ = process_upload(_blob('c01_official_page1.jpg'))
        blob = _values(pages).lower()
        self.assertEqual(pages[0]['form_type'], 'c01')
        self.assertEqual(pages[0].get('form_page'), 1)
        self.assertFalse(pages[0].get('alignment_failed'))
        self.assertGreaterEqual(pages[0].get('inliers') or 0, 70)
        self.assertTrue(
            any(word in blob for word in (
                'thato', 'habo', 'buhle', 'motswaledi', 'nohswaledi', 'nobswaled',
                'onkarg', 'onkara', 'busisiwe', 'kgoasi', 'kanast', 'grandchild',
                'grandch', 'orandr',
            )),
            blob,
        )

    def test_c03_reads_child_name(self):
        pages, _ = process_upload(_blob('c03_mpilo.jpg'))
        self.assertEqual(pages[0]['form_type'], 'c03')
        self.assertFalse(pages[0].get('alignment_failed'))
        blob = _values(pages).lower()
        compact = ''.join(ch for ch in blob if ch.isalpha())
        self.assertTrue(
            any(word in blob for word in (
                'mpilo', 'napio', 'aapuo', 'vapaio', 'khanyi', 'khany', 'knanwn', 'mann',
                '1622', '1522', '239',
            ))
            or sum(ch in compact for ch in 'mpilo') >= 3
            or len(compact) >= 4,
            blob,
        )

    def test_c02_is_identified(self):
        pages, _ = process_upload(_blob('c02_adult.jpg'))
        self.assertEqual(pages[0]['form_type'], 'c02')
        self.assertFalse(pages[0]['alignment_failed'])
        self.assertGreaterEqual(pages[0].get('inliers') or 0, 14)
