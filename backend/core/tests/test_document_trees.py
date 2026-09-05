"""Tests for Tree A (case-files) and Tree B (vital-documents) storage."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core import choices
from core.document_trees import (
    document_storage_path,
    expected_parent_kind,
    stamped_filename,
    tree_a_relative_path,
    tree_b_relative_path,
    windows_safe_name,
)
from core.models import Caregiver, Household, HouseholdMember, SupportingDocument
from core.views import _ensure_checklist


TINY_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
    b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)


class DocumentTreeHelpersTests(TestCase):
    def test_windows_safe_name_strips_illegal_characters(self):
        self.assertEqual(windows_safe_name('Motswaledi:ID<>?"'), 'Motswaledi_ID____')
        self.assertEqual(windows_safe_name('CON'), '_CON')
        self.assertEqual(windows_safe_name('  ..  '), 'Unknown')

    def test_checklist_template_has_eight_content_page_sections(self):
        cats = [c for c, _ in choices.CATEGORY_CHOICES]
        self.assertEqual(cats, [
            'intake_form', 'family_care_plan', 'vital_document', 'process_note',
            'school_report', 'referral_form', 'success_story', 'monthly_report',
        ])
        self.assertIn(('vital_document', 'Report card'), choices.CHECKLIST_TEMPLATE)
        self.assertIn(('intake_form', 'CW05'), choices.CHECKLIST_TEMPLATE)

    def test_vital_parent_kind_rules(self):
        self.assertEqual(expected_parent_kind('vital_document', "Parents' ID's"), 'caregiver')
        self.assertEqual(expected_parent_kind('vital_document', 'Death Certificates'), 'caregiver')
        self.assertEqual(expected_parent_kind('vital_document', 'Birth certificates'), 'householdmember')
        self.assertEqual(expected_parent_kind('vital_document', 'Clinic Card'), 'householdmember')
        self.assertEqual(expected_parent_kind('vital_document', 'Report card'), 'householdmember')
        self.assertIsNone(expected_parent_kind('intake_form', 'C01'))


@override_settings(MEDIA_ROOT='/tmp/ovc-doc-trees-test-media')
class DocumentTreeStorageTests(TestCase):
    def setUp(self):
        self.hh = Household.objects.create(
            org_household_number='SI-0042',
            house_number='12',
            street='Main Road',
            town='Umlazi',
        )
        self.cg = Caregiver.objects.create(
            household=self.hh, name='Thandi', surname='Motswaledi',
        )
        self.child = HouseholdMember.objects.create(
            household=self.hh, name='Sipho', surname='Motswaledi',
        )
        _ensure_checklist(self.hh)

    def test_tree_a_path_for_intake_form(self):
        path = tree_a_relative_path(self.hh, 'intake_form', 'C01', 'scan page.pdf')
        self.assertTrue(path.startswith('case-files/SI-0042/01_Intake_Forms/C01/'))
        self.assertRegex(path.split('/')[-1], r'^\d{14}_scan.page\.pdf$|^\d{14}_scan_page\.pdf$')

    def test_stamped_filename_prefixes_timestamp(self):
        name = stamped_filename('IMG_3701.jpg')
        self.assertRegex(name, r'^\d{14}_IMG_3701\.jpg$')
        self.assertEqual(stamped_filename(name), name)

    def test_tree_b_path_for_parents_id_on_caregiver(self):
        path = tree_b_relative_path(self.hh, self.cg, "Parents' ID's", 'id-copy.png')
        self.assertIn('vital-documents/', path)
        self.assertIn('Motswaledi, Thandi (SI-0042)', path)
        self.assertIn('12 Main Road, Umlazi', path)
        self.assertIn('Parent-guardian', path)
        self.assertIn('Parents ID', path)

    def test_tree_b_path_for_birth_cert_on_child(self):
        path = tree_b_relative_path(self.hh, self.child, 'Birth certificates', 'birth.pdf')
        self.assertIn('Child - Sipho Motswaledi', path)
        self.assertIn('Birth certificate', path)

    def test_upload_to_routes_vitals_to_tree_b(self):
        doc = SupportingDocument(
            content_type=ContentType.objects.get_for_model(Caregiver),
            object_id=self.cg.pk,
            category='vital_document',
            sub_item="Parents' ID's",
            parent_kind='caregiver',
        )
        rel = document_storage_path(doc, 'parents-id.png')
        self.assertTrue(rel.startswith('vital-documents/'))
        self.assertIn('Parents ID', rel)

    def test_upload_to_routes_intake_to_tree_a(self):
        doc = SupportingDocument(
            content_type=ContentType.objects.get_for_model(Household),
            object_id=self.hh.pk,
            category='intake_form',
            sub_item='C01',
            parent_kind='household',
        )
        rel = document_storage_path(doc, 'c01.pdf')
        self.assertTrue(rel.startswith('case-files/SI-0042/01_Intake_Forms/C01/'))

    def test_ensure_checklist_adds_report_card_without_wiping(self):
        item = self.hh.checklist_items.filter(sub_item='C01').first()
        item.has_evidence = 'Yes'
        item.save(update_fields=['has_evidence'])
        self.hh.checklist_items.filter(sub_item='Report card').delete()
        _ensure_checklist(self.hh)
        self.assertTrue(self.hh.checklist_items.filter(sub_item='Report card').exists())
        item.refresh_from_db()
        self.assertEqual(item.has_evidence, 'Yes')


@override_settings(MEDIA_ROOT='/tmp/ovc-doc-trees-api-media')
class DocumentUploadApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        Group.objects.get_or_create(name='admin')
        self.user = User.objects.create_user(
            'uploader', password='pass', is_staff=True, is_superuser=True,
        )
        self.user.groups.add(Group.objects.get(name='admin'))
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=self.user).key}')
        self.hh = Household.objects.create(
            org_household_number='SI-0099',
            house_number='7',
            street='Oak Ave',
            town='Durban',
        )
        self.cg = Caregiver.objects.create(household=self.hh, name='Ann', surname='Dlamini')
        self.child = HouseholdMember.objects.create(household=self.hh, name='Leo', surname='Dlamini')
        _ensure_checklist(self.hh)

    def _png(self, name='doc.png'):
        return SimpleUploadedFile(name, TINY_PNG, content_type='image/png')

    def test_choices_expose_checklist_template_and_order(self):
        r = self.client.get('/api/choices/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('checklist_template', r.data)
        self.assertIn('category_order', r.data)
        self.assertEqual(r.data['category_order'][0], 'intake_form')
        self.assertEqual(r.data['category_order'][2], 'vital_document')
        subs = {row['sub_item'] for row in r.data['checklist_template']}
        self.assertIn('Report card', subs)
        self.assertIn('C01', subs)

    def test_vital_upload_stores_under_vital_documents_and_rejects_wrong_parent(self):
        bad = self.client.post('/api/documents/', {
            'file': self._png('birth.png'),
            'parent_type': 'caregiver',
            'parent_id': self.cg.id,
            'category': 'vital_document',
            'sub_item': 'Birth certificates',
            'label': 'Birth',
        }, format='multipart')
        self.assertEqual(bad.status_code, 400, bad.data)

        ok = self.client.post('/api/documents/', {
            'file': self._png('birth.png'),
            'parent_type': 'householdmember',
            'parent_id': self.child.id,
            'category': 'vital_document',
            'sub_item': 'Birth certificates',
            'label': 'Birth',
        }, format='multipart')
        self.assertEqual(ok.status_code, 201, ok.data)
        doc = SupportingDocument.objects.get(pk=ok.data['id'])
        self.assertTrue(doc.file.name.startswith('vital-documents/'))
        self.assertIn('Birth certificate', doc.file.name)
        self.assertRegex(doc.file.name.split('/')[-1], r'^\d{14}_birth\.png$')
        self.assertEqual(ok.data.get('storage_tree'), 'vital')
        doc.file.open('rb')
        self.assertEqual(doc.file.read(), TINY_PNG)
        doc.file.close()
        item = self.hh.checklist_items.get(category='vital_document', sub_item='Birth certificates')
        self.assertEqual(item.has_evidence, 'Yes')

    def test_intake_upload_stores_under_case_files(self):
        r = self.client.post('/api/documents/', {
            'file': self._png('c01.png'),
            'parent_type': 'household',
            'parent_id': self.hh.id,
            'category': 'intake_form',
            'sub_item': 'C01',
            'label': 'C01',
        }, format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        doc = SupportingDocument.objects.get(pk=r.data['id'])
        self.assertTrue(doc.file.name.startswith('case-files/SI-0099/01_Intake_Forms/C01/'))
        self.assertRegex(doc.file.name.split('/')[-1], r'^\d{14}_c01\.png$')
        self.assertEqual(r.data.get('storage_tree'), 'case_file')
        item = self.hh.checklist_items.get(category='intake_form', sub_item='C01')
        self.assertEqual(item.has_evidence, 'Yes')


@override_settings(MEDIA_ROOT='/tmp/ovc-scan-tree-a-media')
class ScanConfirmTreeATests(TestCase):
    def setUp(self):
        User = get_user_model()
        Group.objects.get_or_create(name='admin')
        self.user = User.objects.create_user(
            'OrphanCoordinator', password='x', is_staff=True, is_superuser=True,
        )
        self.user.groups.add(Group.objects.get(name='admin'))
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=self.user).key}')

    def test_confirm_hardlinks_page_into_tree_a_and_keeps_scan_original(self):
        from pathlib import Path

        from django.conf import settings

        from core.models import ScanIntakeJob, ScanIntakePage

        job = ScanIntakeJob.objects.create(created_by=self.user, status='pending')
        page = ScanIntakePage(
            job=job, index=0, form_type='c01', form_confidence=0.9,
            fields=[
                {'label': 'Primary Client Surname', 'value': 'Dlamini', 'target': 'caregiver.surname', 'confidence': 0.9, 'confirmed': True},
                {'label': 'SA ID Number', 'value': '8001015009087', 'target': 'caregiver.id_number', 'confidence': 0.9, 'confirmed': True},
                {'label': 'Date of birth (from ID)', 'value': '1980-01-01', 'target': 'caregiver.date_of_birth', 'confidence': 0.9, 'confirmed': True},
            ],
        )
        page.image.save('page-c01.png', SimpleUploadedFile('page-c01.png', TINY_PNG, content_type='image/png'), save=True)
        original = Path(settings.MEDIA_ROOT) / page.image.name
        self.assertTrue(original.is_file())

        ok = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertTrue(original.is_file(), 'scan_intake original must stay in place')

        doc = SupportingDocument.objects.get(object_id=ok.data['household'])
        self.assertTrue(doc.file.name.startswith('case-files/'))
        self.assertIn('/01_Intake_Forms/C01/', doc.file.name)
        tree_path = Path(settings.MEDIA_ROOT) / doc.file.name
        self.assertTrue(tree_path.is_file())
        self.assertNotEqual(str(original.resolve()), str(tree_path.resolve()))
