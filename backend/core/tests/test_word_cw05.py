"""Phase 1–2: Official CW 05 prints as filled Word; blanks from Word pages."""
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.test import TestCase
from docx import Document
from docx.table import _Cell
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.form_atlas import ATLAS_FORMS, fields_for, form_meta
from core.official_blanks import ATLAS_VERSION, blank_info
from core.word_forms import fill_cw05_docx, official_cw05_path

SAMPLE = {
    'household.org_household_number': '472',
    'caregiver.surname': 'Moholoza',
    'caregiver.name': 'Sisi Lettie',
    'caregiver.id_number': '6511010326080',
}


class FillOfficialCw05Tests(TestCase):
    def test_template_file_is_present(self):
        self.assertTrue(official_cw05_path().exists())

    def test_primary_client_identity_fills_the_word_form(self):
        raw = fill_cw05_docx(SAMPLE)
        doc = Document(BytesIO(raw))
        table = doc.tables[0]
        self.assertEqual(_Cell(table.rows[1]._tr.tc_lst[1], table).text.strip(), '472')
        self.assertEqual(_Cell(table.rows[3]._tr.tc_lst[0], table).text.strip(), 'Moholoza')
        self.assertEqual(_Cell(table.rows[3]._tr.tc_lst[1], table).text.strip(), 'Sisi Lettie')
        self.assertEqual(_Cell(table.rows[3]._tr.tc_lst[2], table).text.strip(), '6511010326080')


class PrintCw05WordTests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name='admin')
        self.user = User.objects.create_user('cw05printer', password='x')
        self.user.groups.add(Group.objects.get(name='admin'))
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=self.user).key}')

    def test_print_intake_downloads_a_docx_not_pdf_canvas(self):
        created = self.client.post('/api/households/', {'town': 'Westonaria'}, format='json')
        hid = created.data['id']
        token = Token.objects.get(user=self.user).key
        response = self.client.get(f'/api/print/intake/?household_id={hid}&token={token}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            response['Content-Type'],
        )
        self.assertNotIn(b'official-payload', response.content)


class Cw05WordAtlasTests(TestCase):
    def test_intake_uses_word_geometry_and_four_pages(self):
        self.assertEqual(ATLAS_FORMS['intake']['geometry'], 'word')
        self.assertEqual(form_meta('intake')['pages'], 4)
        info = blank_info('intake', 0)
        self.assertEqual(info.get('source'), 'docx')
        self.assertIn('CW_05_Intake_Form_28082019.docx', info.get('source_docx') or '')
        self.assertIn('cw05', ATLAS_VERSION)
        self.assertEqual(fields_for('intake', 0)[1]['label'], 'Primary Client Surname')
        open_file = next(f for f in fields_for('intake') if f['label'] == 'Open file')
        self.assertEqual(open_file['page'], 3)
