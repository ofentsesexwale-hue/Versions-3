from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import Caregiver, Household, ScanIntakeJob, ScanIntakePage
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
        # CW 05 has a measured atlas, so the per-field crops answer for it and
        # scraping the flattened page text is off. The labels still work on a
        # sheet with no atlas.
        fields = {f['target']: f for f in extract_fields('unknown', INTAKE_TEXT, 0.8)}
        self.assertEqual(fields['caregiver.surname']['label'], 'Primary Client Surname')
        self.assertIn('Dlamini', fields['caregiver.surname']['value'])
        self.assertEqual(fields['caregiver.id_number']['value'], '8001015009087')
        self.assertEqual(fields['caregiver.date_of_birth']['value'], '1980-01-01')
        scraped = [f for f in extract_fields('intake', INTAKE_TEXT, 0.8) if f['target']]
        self.assertEqual(scraped, [])

    def test_gibberish_name_is_not_saved_as_hallie(self):
        from core.scan_text import looks_like_gibberish, sanitize_ocr_value
        self.assertTrue(looks_like_gibberish('hgftrujyfdyt'))
        self.assertEqual(sanitize_ocr_value('caregiver.name', 'hgftrujyfdyt', 'handwrite'), '')
        self.assertEqual(sanitize_ocr_value('caregiver.name', 'Hallie', 'handwrite'), 'Hallie')
        self.assertFalse(looks_like_gibberish('Motswaledi'))
        self.assertEqual(sanitize_ocr_value('member.1.surname', 'Motswaledi', 'handwrite'), 'Motswaledi')
        text = 'Surname hgftrujyfdyt\nFirst name Hallie'
        fields = {f['target']: f for f in extract_fields('unknown', text, 0.8)}
        self.assertNotIn('caregiver.surname', fields)
        self.assertEqual(fields.get('caregiver.name', {}).get('value'), 'Hallie')

    def test_rapidocr_reads_printed_name_better_than_smash(self):
        from core.scan_engines import rapidocr_available, read_line
        self.assertTrue(rapidocr_available(), 'RapidOCR must be installed in this Python')
        from PIL import ImageDraw, ImageFont
        im = Image.new('RGB', (420, 90), 'white')
        draw = ImageDraw.Draw(im)
        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 40)
        except OSError:
            font = ImageFont.load_default()
        draw.text((12, 22), 'Hallie', fill='black', font=font)
        text, conf = read_line(im)
        self.assertIn('Hallie', text)
        self.assertGreater(conf, 0.8)

    def test_engine_status_reports_rapidocr(self):
        r = self.client.get('/api/scan-intake/engine/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.get('rapidocr'), r.data)

    def test_engine_status_reports_trocr_and_lightonocr_flags(self):
        r = self.client.get('/api/scan-intake/engine/')
        self.assertEqual(r.status_code, 200)
        # Loaded / ready / error keys must be present for the status panel.
        for key in (
            'trocr', 'trocr_ready', 'trocr_error',
            'lightonocr', 'lightonocr_ready', 'lightonocr_error',
        ):
            self.assertIn(key, r.data, r.data)
        self.assertIn('TrOCR', r.data.get('message') or '')
        self.assertIn('LightOnOCR', r.data.get('message') or '')
        self.assertNotIn('qwen', r.data)
        self.assertNotIn('Qwen', r.data.get('message') or '')

    def test_handwrite_path_uses_trocr_not_rapidocr(self):
        from unittest.mock import patch
        from PIL import Image
        from core.scan_ocr import _ocr_handwrite_variants

        crop = Image.new('RGB', (200, 40), 'white')
        with patch('core.scan_handwrite_engines.read_handwriting', return_value=('Hallie', 0.88, 'trocr')) as hw, \
             patch('core.scan_engines.read_line') as rapid:
            text, conf = _ocr_handwrite_variants(crop)
        self.assertEqual(text, 'Hallie')
        self.assertGreaterEqual(conf, 0.72)
        self.assertTrue(hw.called)
        rapid.assert_not_called()

    def test_handwrite_falls_back_to_lightonocr_when_trocr_weak(self):
        from core.scan_handwrite_engines import read_handwriting, TROCR_LOW_CONF
        from unittest.mock import patch
        from PIL import Image

        crop = Image.new('RGB', (120, 40), 'white')
        with patch('core.scan_handwrite_engines.read_trocr', return_value=('', 0.0)), \
             patch('core.scan_handwrite_engines.read_lightonocr', return_value=('Motswaledi', 0.7)):
            text, conf, name = read_handwriting(crop)
        self.assertEqual(text, 'Motswaledi')
        self.assertEqual(name, 'lightonocr')
        self.assertGreater(conf, TROCR_LOW_CONF)

    def test_preprocess_handwriting_crop_is_mild_not_binarized(self):
        from unittest.mock import patch
        from PIL import Image
        from core import scan_handwrite_engines as hw

        crop = Image.new('RGB', (80, 24), 'white')
        with patch.object(hw, 'fix_polarity') as polarity, \
             patch.object(hw, 'deskew_image') as deskew, \
             patch.object(hw, 'reduce_noise') as noise, \
             patch.object(hw, 'enhance_clahe') as clahe, \
             patch.object(hw, 'adaptive_binarize') as binarize:
            out = hw.preprocess_handwriting_crop(crop)
        # First-pass prep must not run hard akincal/OCR steps.
        polarity.assert_not_called()
        deskew.assert_not_called()
        noise.assert_not_called()
        clahe.assert_not_called()
        binarize.assert_not_called()
        self.assertEqual(out.mode, 'RGB')
        # Short rows are padded / upscaled, not left as a thin strip.
        self.assertGreaterEqual(out.size[1], 48)

    def test_hard_handwriting_variant_rejects_sludge(self):
        from PIL import Image, ImageDraw
        from core.scan_handwrite_engines import (
            hard_variant_is_usable,
            preprocess_handwriting_crop,
        )

        crop = Image.new('RGB', (200, 40), (245, 245, 245))
        draw = ImageDraw.Draw(crop)
        draw.text((20, 10), 'Motswaledi', fill=(30, 30, 30))
        mild = preprocess_handwriting_crop(crop)
        sludge = Image.new('RGB', mild.size, (0, 0, 0))
        blank = Image.new('RGB', mild.size, (255, 255, 255))
        self.assertFalse(hard_variant_is_usable(mild, sludge))
        self.assertFalse(hard_variant_is_usable(mild, blank))

    def test_handwrite_tries_mild_before_hard_variants(self):
        from unittest.mock import patch
        from PIL import Image
        from core.scan_handwrite_engines import read_handwriting

        crop = Image.new('RGB', (120, 40), 'white')
        mild = Image.new('RGB', (360, 120), 'white')
        hard = Image.new('RGB', (360, 120), 'black')
        trocr_images = []

        def _trocr(image, cancel=None, session_id=None, *, preprocessed=False):
            trocr_images.append(image)
            # Strong hit on the first (mild) pass — hard variants must not run.
            return ('Motswaledi', 0.9)

        with patch('core.scan_handwrite_engines.preprocess_handwriting_crop', return_value=mild) as prep, \
             patch('core.scan_handwrite_engines.handwriting_fallback_variants', return_value=[hard]) as variants, \
             patch('core.scan_handwrite_engines.read_trocr', side_effect=_trocr), \
             patch('core.scan_handwrite_engines.read_lightonocr') as lighton:
            text, conf, name = read_handwriting(crop)
        self.assertEqual(text, 'Motswaledi')
        self.assertEqual(name, 'trocr')
        prep.assert_called()
        variants.assert_not_called()
        lighton.assert_not_called()
        self.assertEqual(trocr_images[0], mild)

    def test_handwrite_session_cancel_stops_progress(self):
        from core.scan_handwrite_engines import (
            begin_handwrite_session,
            cancel_handwrite_session,
            end_handwrite_session,
            handwrite_session_progress,
            read_handwriting,
        )
        from unittest.mock import patch
        from PIL import Image

        sid = begin_handwrite_session('test-cancel')
        try:
            crop = Image.new('RGB', (40, 20), 'white')
            cancel_handwrite_session(sid)
            with patch('core.scan_handwrite_engines.preprocess_handwriting_crop', side_effect=lambda im: im), \
                 patch('core.scan_handwrite_engines.read_trocr') as trocr, \
                 patch('core.scan_handwrite_engines.read_lightonocr') as lighton:
                text, conf, name = read_handwriting(crop, session_id=sid, field_key='caregiver.name')
            self.assertEqual(name, 'cancelled')
            self.assertEqual(text, '')
            trocr.assert_not_called()
            lighton.assert_not_called()
            progress = handwrite_session_progress(sid)
            self.assertTrue(progress['cancelled'])
            self.assertEqual(progress['fields'].get('caregiver.name'), 'cancelled')
        finally:
            end_handwrite_session(sid)

    def test_intake_without_c01_still_classifies(self):
        form, conf = classify_text(INTAKE_TEXT)
        self.assertEqual(form, 'intake')
        self.assertNotEqual(form, 'c01')

    def test_extract_c01_address_from_ocr_text(self):
        text = """
        C01: Household Details
        HEAD OF HOUSEHOLD
        1. Org Household Nr. SI-0007
        2. House Number 12
        3. Street Main Road
        4. Town Umlazi
        Province KwaZulu-Natal
        Surname Cele
        """
        form, conf = classify_text(text)
        self.assertEqual(form, 'c01')
        # C01 is read box by box off the aligned photo, so the page-text
        # scraper is not allowed to guess over those same fields.
        self.assertEqual([f for f in extract_fields('c01', text, 0.8) if f['target']], [])
        fields = {f['target']: f for f in extract_fields('unknown', text, 0.8)}
        self.assertEqual(fields['household.town']['value'], 'Umlazi')
        self.assertEqual(fields['household.house_number']['value'], '12')
        self.assertIn('Cele', fields['caregiver.surname']['value'])

    def test_upload_photo_reads_printed_text(self):
        from core.scan_ocr import ocr_available
        if not ocr_available():
            self.skipTest('Tesseract is not on this PC')
        from PIL import ImageDraw, ImageFont
        im = Image.new('RGB', (1400, 500), 'white')
        draw = ImageDraw.Draw(im)
        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 36)
        except OSError:
            font = ImageFont.load_default()
        draw.text(
            (40, 40),
            'CW 05: INTAKE FORM\nPrimary Client Surname Dlamini\nPrimary Client First name Lindiwe\nTown Umlazi',
            fill='black',
            font=font,
            spacing=16,
        )
        buf = BytesIO()
        im.save(buf, format='PNG')
        upload = SimpleUploadedFile('file-page.png', buf.getvalue(), content_type='image/png')
        r = self.client.post('/api/scan-intake/', {'files': upload}, format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        text = ' '.join(p.get('ocr_text') or '' for p in r.data['pages']).upper()
        self.assertTrue(text.strip(), r.data['pages'])
        blob = text + ' ' + ' '.join(
            (f.get('value') or '') for p in r.data['pages'] for f in (p.get('fields') or [])
        )
        self.assertTrue(
            'DLAMINI' in blob.upper() or 'UML' in blob.upper() or 'CW' in text,
            blob[:500],
        )

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


TRIO_FIELDS = ('surname', 'id_number', 'date_of_birth')


def _trio(prefix, surname, id_number, dob, confirmed=True):
    return [
        {'label': f'{prefix} Surname', 'value': surname,
         'target': f'{prefix}.surname', 'confidence': 0.9, 'confirmed': confirmed},
        {'label': f'{prefix} ID Number', 'value': id_number,
         'target': f'{prefix}.id_number', 'confidence': 0.9, 'confirmed': confirmed},
        {'label': f'{prefix} Date of Birth', 'value': dob,
         'target': f'{prefix}.date_of_birth', 'confidence': 0.9, 'confirmed': confirmed},
    ]


class ScanConfirmationGateTests(TestCase):
    """A scanned surname / ID / date of birth is only trusted once a person says so."""

    def setUp(self):
        Group.objects.get_or_create(name='admin')
        self.user = User.objects.create_user(
            'OrphanCoordinator', password='x', is_staff=True, is_superuser=True,
        )
        self.user.groups.add(Group.objects.get(name='admin'))
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=self.user).key}')

    def _job(self, pages):
        job = ScanIntakeJob.objects.create(created_by=self.user, status='pending')
        for index, (form_type, fields) in enumerate(pages):
            ScanIntakePage.objects.create(
                job=job, index=index, form_type=form_type, form_confidence=0.9,
                ocr_confidence=0.8, fields=fields,
            )
        return job

    def test_every_member_slot_is_gated_like_the_caregiver(self):
        from core.form_io import needs_staff_confirmation
        for slot in range(4):
            for field in TRIO_FIELDS:
                self.assertTrue(
                    needs_staff_confirmation(f'member.{slot}.{field}'),
                    f'member.{slot}.{field} must need a staff confirm',
                )
            self.assertFalse(needs_staff_confirmation(f'member.{slot}.name'))
        for field in TRIO_FIELDS:
            self.assertTrue(needs_staff_confirmation(f'caregiver.{field}'))
        # The old literal never appears in the atlas and must not be relied on.
        self.assertFalse(needs_staff_confirmation('member.surname'))

    def test_unconfirmed_member_slot_blocks_save_for_all_four_slots(self):
        for slot in range(4):
            with self.subTest(slot=slot):
                job = self._job([(
                    'c01',
                    _trio(f'member.{slot}', 'Motswaledi', '8001015009087',
                          '1980-01-01', confirmed=False),
                )])
                blocked = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
                self.assertEqual(blocked.status_code, 400, blocked.data)
                self.assertEqual(len(blocked.data['unconfirmed']), 3, blocked.data)
                self.assertEqual(Household.objects.count(), 0)

    def test_confirmed_member_slot_saves_from_any_of_the_four_slots(self):
        # One ID per slot: each pass writes a new household, and reusing one
        # number would (rightly) trip the duplicate-ID warning.
        ids = ['8001015009087', '8502025100089', '9003035200083', '9504045300086']
        for slot in range(4):
            with self.subTest(slot=slot):
                job = self._job([(
                    'c01',
                    _trio(f'member.{slot}', 'Motswaledi', ids[slot], '1980-01-01'),
                )])
                ok = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
                self.assertEqual(ok.status_code, 200, ok.data)
                member = Household.objects.get(pk=ok.data['household']).members.get()
                self.assertEqual(member.surname, 'Motswaledi')
                self.assertTrue(member.surname_confirmed)
                self.assertTrue(member.id_number_confirmed)
                self.assertTrue(member.date_of_birth_confirmed)

    def test_date_of_birth_read_off_the_paper_needs_its_own_confirm(self):
        """Confirming the surname and ID does not confirm a scanned date of birth."""
        job = self._job([(
            'intake',
            [
                {'label': 'Primary Client Surname', 'value': 'Dlamini',
                 'target': 'caregiver.surname', 'confidence': 0.9, 'confirmed': True},
                {'label': 'SA ID Number', 'value': '8001015009087',
                 'target': 'caregiver.id_number', 'confidence': 0.9, 'confirmed': True},
                {'label': 'Date of Birth', 'value': '1979-02-02',
                 'target': 'caregiver.date_of_birth', 'confidence': 0.9, 'confirmed': False},
            ],
        )])
        blocked = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(blocked.status_code, 400, blocked.data)
        self.assertEqual(blocked.data['unconfirmed'], ['Date of Birth'])
        self.assertEqual(Household.objects.count(), 0)

    def test_date_of_birth_worked_out_from_a_confirmed_id_is_accepted(self):
        """Arithmetic on an ID a person signed off is not an unchecked reading."""
        job = self._job([(
            'intake',
            [
                {'label': 'Primary Client Surname', 'value': 'Dlamini',
                 'target': 'caregiver.surname', 'confidence': 0.9, 'confirmed': True},
                {'label': 'SA ID Number', 'value': '8001015009087',
                 'target': 'caregiver.id_number', 'confidence': 0.9, 'confirmed': True},
            ],
        )])
        ok = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(ok.status_code, 200, ok.data)
        caregiver = Household.objects.get(pk=ok.data['household']).caregiver
        self.assertEqual(caregiver.date_of_birth.isoformat(), '1980-01-01')
        self.assertTrue(caregiver.id_number_confirmed)

    def test_unchecked_ocr_values_cannot_be_written_at_all(self):
        """apply_buckets must not self-confirm, so the serializer refuses the write."""
        from core.form_io import apply_buckets
        from rest_framework.exceptions import ValidationError
        from rest_framework.test import APIRequestFactory
        request = APIRequestFactory().post('/api/scan-intake/')
        request.user = self.user
        for prefix in ('caregiver', 'member.0'):
            with self.subTest(prefix=prefix):
                with self.assertRaises(ValidationError) as caught:
                    apply_buckets(request, None, {
                        f'{prefix}.surname': 'Dlamini',
                        f'{prefix}.date_of_birth': '1980-01-01',
                    })
                self.assertIn('surname', caught.exception.detail)
                self.assertIn('date_of_birth', caught.exception.detail)
        self.assertFalse(Caregiver.objects.exists())


class ScanCrossPageOverwriteTests(TestCase):
    """One person's sheet must never overwrite another person through a shared target."""

    def setUp(self):
        Group.objects.get_or_create(name='admin')
        self.user = User.objects.create_user(
            'OrphanCoordinator', password='x', is_staff=True, is_superuser=True,
        )
        self.user.groups.add(Group.objects.get(name='admin'))
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=self.user).key}')
        created = self.client.post('/api/households/', {'town': 'Westonaria'}, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        self.household = Household.objects.get(pk=created.data['id'])

    def _job(self, pages, household=None):
        job = ScanIntakeJob.objects.create(
            created_by=self.user, status='pending', household=household,
        )
        for index, (form_type, fields) in enumerate(pages):
            ScanIntakePage.objects.create(
                job=job, index=index, form_type=form_type, form_confidence=0.9,
                ocr_confidence=0.8, fields=fields,
            )
        return job

    def test_c03_child_page_cannot_overwrite_the_c02_adult(self):
        job = self._job(
            [
                ('c02', _trio('caregiver', 'Dlamini', '8001015009087', '1980-01-01') + [
                    {'label': 'Name', 'value': 'Thabo', 'target': 'caregiver.name',
                     'confidence': 0.8, 'confirmed': False},
                ]),
                ('c03', _trio('caregiver', 'Khanyi', '1904261049081', '2019-04-26') + [
                    {'label': 'Name', 'value': 'Mpilo', 'target': 'caregiver.name',
                     'confidence': 0.8, 'confirmed': False},
                ]),
            ],
            household=self.household,
        )
        ok = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(ok.status_code, 200, ok.data)
        caregiver = Household.objects.get(pk=ok.data['household']).caregiver
        self.assertEqual(caregiver.surname, 'Dlamini')
        self.assertEqual(caregiver.name, 'Thabo')
        self.assertEqual(caregiver.id_number, '8001015009087')
        member = Household.objects.get(pk=ok.data['household']).members.get()
        self.assertEqual(member.surname, 'Khanyi')
        self.assertEqual(member.name, 'Mpilo')
        self.assertEqual(member.id_number, '1904261049081')
        self.assertNotIn('held_back', ok.data)
        # Legacy C03 caregiver.* names were rewritten onto the member.
        self.assertTrue(ok.data.get('needs_review'))

    def test_page_order_does_not_decide_the_winner(self):
        """The same two sheets uploaded the other way round give the same adult."""
        job = self._job(
            [
                ('c03', _trio('caregiver', 'Khanyi', '1904261049081', '2019-04-26')),
                ('c02', _trio('caregiver', 'Dlamini', '8001015009087', '1980-01-01')),
            ],
            household=self.household,
        )
        ok = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(ok.status_code, 200, ok.data)
        caregiver = Household.objects.get(pk=ok.data['household']).caregiver
        self.assertEqual(caregiver.surname, 'Dlamini')

    def test_two_c01_pages_for_one_household_still_merge(self):
        job = self._job(
            [
                ('c01', _trio('caregiver', 'Dlamini', '8001015009087', '1980-01-01') + [
                    {'label': 'Town', 'value': 'Westonaria', 'target': 'household.town',
                     'confidence': 0.8, 'confirmed': False},
                ]),
                ('c01', _trio('member.1', 'Motswaledi', '0403155009086', '2004-03-15')),
            ],
            household=self.household,
        )
        ok = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertNotIn('held_back', ok.data)
        hh = Household.objects.get(pk=ok.data['household'])
        self.assertEqual(hh.caregiver.surname, 'Dlamini')
        self.assertEqual(hh.members.get().surname, 'Motswaledi')

    def test_two_readings_of_the_same_person_are_surfaced_not_guessed(self):
        job = self._job(
            [
                ('c01', _trio('caregiver', 'Dlamini', '8001015009087', '1980-01-01')),
                ('intake', _trio('caregiver', 'Zulu', '8001015009087', '1980-01-01')),
            ],
            household=self.household,
        )
        blocked = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(blocked.status_code, 400, blocked.data)
        conflict = blocked.data['conflicts'][0]
        self.assertEqual(conflict['target'], 'caregiver.surname')
        self.assertEqual(
            {row['value'] for row in conflict['values']}, {'Dlamini', 'Zulu'},
        )
        self.assertIsNone(Caregiver.objects.filter(household=self.household).first())
