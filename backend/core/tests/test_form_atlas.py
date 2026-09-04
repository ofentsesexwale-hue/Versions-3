import hashlib
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.form_atlas import FIELDS, fields_for, form_meta, has_geometry
from core.official_blanks import BLANKS_DIR, META_PATH, load_meta, sha256_file
from core.sa_id import parse_sa_id


REPO = Path(__file__).resolve().parents[3]


class AtlasGeometryTests(TestCase):
    def test_boxes_are_normalised(self):
        for code, items in FIELDS.items():
            for field in items:
                x0, y0, x1, y1 = field['box']
                self.assertGreaterEqual(x0, 0, field)
                self.assertGreaterEqual(y0, 0, field)
                self.assertLessEqual(x1, 1.001, field)
                self.assertLessEqual(y1, 1.001, field)
                self.assertLess(x0, x1, field)
                self.assertLess(y0, y1, field)
                self.assertIn(field['kind'], {'sa_id', 'handwrite', 'printed', 'checkbox', 'date', 'narrative'})

    def test_c01_uses_word_blanks_and_intake_uses_pdf(self):
        self.assertTrue(has_geometry('c01'))
        self.assertTrue(has_geometry('intake'))
        self.assertEqual(form_meta('c01')['geometry'], 'word')
        self.assertEqual(form_meta('c01')['pages'], 2)
        self.assertEqual(form_meta('intake')['pages'], 3)
        self.assertTrue(any(f['target'] == 'caregiver.id_number' and f['kind'] == 'sa_id' for f in fields_for('c01')))
        self.assertEqual(fields_for('c01', 0)[0]['label'], 'Org Household Nr')
        self.assertEqual(fields_for('intake', 0)[1]['label'], 'Primary Client Surname')

    def test_blank_png_hash_matches_repo_files(self):
        meta = load_meta()
        for key, info in meta['pages'].items():
            path = BLANKS_DIR / info['file']
            self.assertTrue(path.exists(), path)
            self.assertEqual(sha256_file(path), info['sha256'], key)

    def test_blank_png_matches_pdf_render(self):
        import pypdfium2 as pdfium
        from PIL import Image
        meta = load_meta()
        docs = {}
        for key, info in meta['pages'].items():
            if info.get('source') == 'docx' or 'pdf_page' not in info:
                continue
            pdf_rel = info.get('source_pdf') or meta['source_pdf']
            pdf_path = REPO / pdf_rel
            self.assertTrue(pdf_path.exists(), pdf_path)
            if pdf_rel not in docs:
                docs[pdf_rel] = pdfium.PdfDocument(str(pdf_path))
            pdf = docs[pdf_rel]
            img = pdf[info['pdf_page'] - 1].render(scale=meta['scale']).to_pil().convert('RGB')
            if info.get('rotate'):
                img = img.rotate(info['rotate'], expand=True)
            stored = Image.open(BLANKS_DIR / info['file']).convert('RGB')
            self.assertEqual(img.size, stored.size, key)
            self.assertEqual(
                hashlib.sha256(img.tobytes()).hexdigest(),
                hashlib.sha256(stored.tobytes()).hexdigest(),
                f'{key} HTML/scan blank drifted from {pdf_rel}',
            )

    def test_c01_text_boxes_match_word_blank_inputs(self):
        org = next(f for f in fields_for('c01') if f['target'] == 'household.org_household_number')
        self.assertAlmostEqual(org['box'][0], 0.2807, places=3)
        self.assertAlmostEqual(org['box'][1], 0.1097, places=3)
        name = next(f for f in fields_for('c01') if f['target'] == 'caregiver.name')
        self.assertAlmostEqual(name['box'][0], 0.2892, places=3)
        self.assertGreater(name['box'][1], 0.30)
        self.assertTrue(has_geometry('cow2_note'))
        self.assertEqual(form_meta('cow2_note')['pages'], 2)
        ref = next(f for f in fields_for('cow2_note') if f['target'] == 'household.org_household_number')
        self.assertGreater(ref['box'][0], 0.7)

    def test_sa_id_paste_fans_out(self):
        parsed = parse_sa_id('8001015009087')
        self.assertTrue(parsed['luhn_ok'])
        self.assertEqual(parsed['dob'], '1980-01-01')


class OfficialFormApiTests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name='admin')
        self.user = User.objects.create_user(
            'OrphanCoordinator', password='x', is_staff=True, is_superuser=True,
        )
        self.user.groups.add(Group.objects.get(name='admin'))
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=self.user).key}')

    def test_fill_c01_writes_existing_serializers(self):
        created = self.client.post('/api/households/', {'town': 'Umlazi'}, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        hid = created.data['id']
        ok = self.client.put(f'/api/official-forms/c01/values/', {
            'household': hid,
            'values': {
                'household.town': 'Umlazi',
                'household.street': 'Main',
                'caregiver.surname': 'Dlamini',
                'caregiver.name': 'Lindiwe',
                'caregiver.id_number': '8001015009087',
                'caregiver.sex': 'Female',
                'member.0.surname': 'Dlamini',
                'member.0.name': 'Sipho',
            },
        }, format='json')
        self.assertEqual(ok.status_code, 200, ok.data)
        detail = self.client.get(f'/api/households/{hid}/')
        self.assertEqual(detail.data['caregiver']['surname'], 'Dlamini')
        self.assertEqual(detail.data['members'][0]['name'], 'Sipho')
        blank = self.client.get('/api/official-forms/c01/blank/0/')
        self.assertEqual(blank.status_code, 200)
        self.assertEqual(blank['Content-Type'], 'image/png')

    def test_print_c01_downloads_word_and_cow2_uses_official_canvas(self):
        created = self.client.post('/api/households/', {'town': 'Umlazi'}, format='json')
        hid = created.data['id']
        token = Token.objects.get(user=self.user).key
        c01 = self.client.get(f'/api/print/c01/?household_id={hid}&token={token}')
        self.assertEqual(c01.status_code, 200)
        self.assertIn(
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            c01['Content-Type'],
        )
        self.assertNotIn(b'official-payload', c01.content)
        cow = self.client.get(f'/api/print/cow2_note/?household_id={hid}&token={token}')
        self.assertEqual(cow.status_code, 200)
        self.assertIn(b'official-payload', cow.content)
        self.assertIn(b'cow2_note/blank', cow.content)
        self.assertNotIn(b'Sebueng Itumeleng', cow.content)
