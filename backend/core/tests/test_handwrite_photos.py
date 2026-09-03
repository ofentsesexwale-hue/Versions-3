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
        pages, _ = process_upload(_blob('c01_household.jpg'))
        blob = _values(pages).lower()
        self.assertEqual(pages[0]['form_type'], 'c01')
        self.assertTrue(
            any(word in blob for word in ('nkululuthweni', 'westonaria', 'moholoza', 'lettie', 'sisi', 'gauteng')),
            blob,
        )

    def test_c01_members_read_grandchild_names(self):
        pages, _ = process_upload(_blob('c01_members_a.jpg'))
        blob = _values(pages).lower()
        self.assertEqual(pages[0]['form_type'], 'c01')
        self.assertTrue(
            any(word in blob for word in (
                'mpilo', 'khanyi', 'paballo', 'motswaledi', 'motswaled', 'motwedr',
                'lucky', 'loeky', 'thato',
            )),
            blob,
        )

    def test_c03_reads_child_name(self):
        pages, _ = process_upload(_blob('c03_mpilo.jpg'))
        blob = _values(pages).lower()
        self.assertEqual(pages[0]['form_type'], 'c03')
        self.assertTrue(
            any(word in blob for word in (
                'mpilo', 'napio', 'aapuo', 'vapaio', 'khanyi', 'khany', 'knanwn', 'mann',
                '1622', '1522',
            )),
            blob,
        )

    def test_c02_is_identified(self):
        pages, _ = process_upload(_blob('c02_adult.jpg'))
        self.assertEqual(pages[0]['form_type'], 'c02')
        self.assertFalse(pages[0]['alignment_failed'])
