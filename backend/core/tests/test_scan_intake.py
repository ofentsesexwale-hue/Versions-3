from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import Household, ScanIntakeJob, ScanIntakePage
from core.scan_templates import classify_text, extract_fields


INTAKE_TEXT = """
CW 05: INTAKE FORM
CONFIDENTIAL
Primary Client Surname Dlamini
Primary Client First name Lindiwe
Intake Ref Number SI-0042
Primary Client ID Number / Date of Birth 8001015009087
Town Umlazi
"""


class ScanIntakeTests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name='admin')
        self.user = User.objects.create_user(
            'OrphanCoordinator', password='x', is_staff=True, is_superuser=True,
        )
        self.user.groups.add(Group.objects.get(name='admin'))
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=self.user).key}')

    def test_classify_and_extract_intake_labels(self):
        form, conf = classify_text(INTAKE_TEXT)
        self.assertEqual(form, 'intake')
        self.assertGreater(conf, 0.4)
        fields = {f['target']: f for f in extract_fields('intake', INTAKE_TEXT, 0.8)}
        self.assertEqual(fields['caregiver.surname']['label'], 'Primary Client Surname')
        self.assertIn('Dlamini', fields['caregiver.surname']['value'])
        self.assertEqual(fields['caregiver.id_number']['value'], '8001015009087')
        self.assertEqual(fields['caregiver.date_of_birth']['value'], '1980-01-01')

    def test_confirm_writes_through_household_path(self):
        job = ScanIntakeJob.objects.create(created_by=self.user, status='pending')
        ScanIntakePage.objects.create(
            job=job, index=0, form_type='intake', form_confidence=0.9,
            ocr_text=INTAKE_TEXT, ocr_confidence=0.8,
            fields=[
                {'label': 'Primary Client Surname', 'value': 'Dlamini', 'target': 'caregiver.surname', 'confidence': 0.9, 'confirmed': True},
                {'label': 'Primary Client First name', 'value': 'Lindiwe', 'target': 'caregiver.name', 'confidence': 0.8, 'confirmed': False},
                {'label': 'SA ID Number', 'value': '8001015009087', 'target': 'caregiver.id_number', 'confidence': 0.9, 'confirmed': True},
                {'label': 'Date of birth (from ID)', 'value': '1980-01-01', 'target': 'caregiver.date_of_birth', 'confidence': 0.9, 'confirmed': True},
                {'label': 'Town', 'value': 'Umlazi', 'target': 'household.town', 'confidence': 0.7, 'confirmed': False},
            ],
        )
        ok = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(ok.status_code, 200, ok.data)
        hh = Household.objects.get(pk=ok.data['household'])
        self.assertTrue(hh.org_household_number.startswith('SI-'))
        self.assertEqual(hh.town, 'Umlazi')
        self.assertEqual(hh.caregiver.surname, 'Dlamini')
        self.assertEqual(hh.caregiver.name, 'Lindiwe')
        self.assertTrue(hh.caregiver.surname_confirmed)
        self.assertTrue(hh.checklist_items.filter(sub_item='CW05', has_evidence='Yes').exists())

    def test_unconfirmed_trio_blocks_save(self):
        job = ScanIntakeJob.objects.create(created_by=self.user, status='pending')
        ScanIntakePage.objects.create(
            job=job, index=0, form_type='intake',
            fields=[
                {'label': 'Primary Client Surname', 'value': 'Dlamini', 'target': 'caregiver.surname', 'confidence': 0.9, 'confirmed': False},
            ],
        )
        blocked = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(blocked.status_code, 400)
        self.assertEqual(Household.objects.count(), 0)

    def test_training_scan_cannot_create_live_file(self):
        demo = User.objects.create_user('demo.admin', password='x', is_staff=True, is_superuser=True)
        demo.groups.add(Group.objects.get(name='admin'))
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=demo).key}')
        job = ScanIntakeJob.objects.create(created_by=demo, status='pending')
        ScanIntakePage.objects.create(
            job=job, index=0, form_type='intake',
            fields=[
                {'label': 'Primary Client Surname', 'value': 'Zulu', 'target': 'caregiver.surname', 'confidence': 0.9, 'confirmed': True},
                {'label': 'SA ID Number', 'value': '8001015009087', 'target': 'caregiver.id_number', 'confidence': 0.9, 'confirmed': True},
                {'label': 'Date of birth (from ID)', 'value': '1980-01-01', 'target': 'caregiver.date_of_birth', 'confidence': 0.9, 'confirmed': True},
            ],
        )
        r = client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        hh = Household.objects.get(pk=r.data['household'])
        self.assertTrue(hh.org_household_number.upper().startswith('TEST'))

    def test_upload_image_creates_pending_job(self):
        buf = BytesIO()
        Image.new('RGB', (40, 40), 'white').save(buf, format='PNG')
        upload = SimpleUploadedFile('page.png', buf.getvalue(), content_type='image/png')
        before = Household.objects.count()
        r = self.client.post('/api/scan-intake/', {'file': upload}, format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['status'], 'pending')
        self.assertGreaterEqual(len(r.data['pages']), 1)
        self.assertEqual(Household.objects.count(), before)
