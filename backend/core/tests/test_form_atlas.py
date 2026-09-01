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

    def test_c01_and_intake_share_pdf_blanks(self):
        self.assertTrue(has_geometry('c01'))
        self.assertTrue(has_geometry('intake'))
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
        pdf_path = REPO / 'docs/official/NPO_case_management_file.pdf'
        self.assertTrue(pdf_path.exists())
        meta = load_meta()
        pdf = pdfium.PdfDocument(str(pdf_path))
        for key, info in meta['pages'].items():
            img = pdf[info['pdf_page'] - 1].render(scale=meta['scale']).to_pil().convert('RGB')
            if info.get('rotate'):
                img = img.rotate(info['rotate'], expand=True)
            stored = Image.open(BLANKS_DIR / info['file']).convert('RGB')
            self.assertEqual(img.size, stored.size, key)
            self.assertEqual(
                hashlib.sha256(img.tobytes()).hexdigest(),
                hashlib.sha256(stored.tobytes()).hexdigest(),
                f'{key} HTML/scan blank drifted from the NPO PDF',
            )

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
