"""Phase 6: C03 writes a member, and geographic OCR uses the supplied place list."""
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.form_atlas import fields_for
from core.models import Caregiver, Household, ScanIntakeJob, ScanIntakePage
from core.scan_ocr import _apply_geo_vocab, process_upload
from core.scan_text import sanitize_ocr_value
from core.service_area import (
    DISTRICTS,
    FREE_TEXT_TARGETS,
    GEO_LISTS,
    MUNICIPALITIES,
    PROVINCES,
    TOWNS,
    WARDS,
    match_closed_value,
    match_geo_field,
)

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'handwrite'

# Phase 5 near-misses on the C01 household photograph (and the synthetic
# round-trip ink for the same cells). Canonical names come only from
# service_area.py, which is sourced from that photograph / Phase 5 notes.
PHASE5_GEO_NEAR_MISSES = {
    'household.province': [('gAaIGNg', 'Gauteng')],
    'household.district': [('rando', 'West Rand'), ('RANDWEST', 'West Rand')],
    'household.town': [('Neslonarig', 'Westonaria')],
}


class Upload:
    def __init__(self, path):
        self._raw = Path(path).read_bytes()
        self.name = Path(path).name

    def read(self):
        return self._raw

    def seek(self, *args):
        pass


def _trio(prefix, surname, id_number, dob, name='', confirmed=True):
    fields = [
        {'label': f'{prefix} Surname', 'value': surname,
         'target': f'{prefix}.surname', 'confidence': 0.9, 'confirmed': confirmed},
        {'label': f'{prefix} ID Number', 'value': id_number,
         'target': f'{prefix}.id_number', 'confidence': 0.9, 'confirmed': confirmed},
        {'label': f'{prefix} Date of Birth', 'value': dob,
         'target': f'{prefix}.date_of_birth', 'confidence': 0.9, 'confirmed': confirmed},
    ]
    if name:
        fields.append({
            'label': f'{prefix} Name', 'value': name,
            'target': f'{prefix}.name', 'confidence': 0.8, 'confirmed': False,
        })
    return fields


class C03MemberTargetingTests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name='admin')
        self.user = User.objects.create_user(
            'OrphanCoordinator', password='x', is_staff=True, is_superuser=True,
        )
        self.user.groups.add(Group.objects.get(name='admin'))
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=self.user).key}')

    def test_c03_atlas_targets_a_member_not_the_caregiver(self):
        identity = [
            f['target'] for f in fields_for('c03')
            if f['target'] in (
                'member.0.name', 'member.0.surname', 'member.0.id_number',
                'caregiver.name', 'caregiver.surname', 'caregiver.id_number',
            )
        ]
        self.assertEqual(
            sorted(identity),
            ['member.0.id_number', 'member.0.name', 'member.0.surname'],
        )

    def test_c02_atlas_stays_on_the_caregiver(self):
        identity = {f['target'] for f in fields_for('c02') if f['target'].startswith('caregiver.')}
        self.assertIn('caregiver.name', identity)
        self.assertIn('caregiver.surname', identity)
        self.assertIn('caregiver.id_number', identity)
        self.assertFalse(any(f['target'].startswith('member.') for f in fields_for('c02')))

    def test_c03_only_scan_creates_a_member_not_a_caregiver(self):
        job = ScanIntakeJob.objects.create(created_by=self.user, status='pending')
        ScanIntakePage.objects.create(
            job=job, index=0, form_type='c03', form_confidence=0.9, ocr_confidence=0.8,
            fields=_trio('member.0', 'Khanyi', '1904261049081', '2019-04-26', name='Mpilo'),
        )
        ok = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(ok.status_code, 200, ok.data)
        hh = Household.objects.get(pk=ok.data['household'])
        self.assertFalse(Caregiver.objects.filter(household=hh).exists())
        member = hh.members.get()
        self.assertEqual(member.name, 'Mpilo')
        self.assertEqual(member.surname, 'Khanyi')
        self.assertEqual(member.id_number, '1904261049081')

    def test_legacy_c03_caregiver_targets_are_not_silently_moved_off_an_existing_row(self):
        created = self.client.post('/api/households/', {'town': 'Westonaria'}, format='json')
        hh = Household.objects.get(pk=created.data['id'])
        Caregiver.objects.create(
            household=hh, name='Mpilo', surname='Khanyi',
            id_number='1904261049081', id_number_confirmed=True,
            surname_confirmed=True, date_of_birth_confirmed=True,
        )
        job = ScanIntakeJob.objects.create(
            created_by=self.user, status='pending', household=hh,
        )
        ScanIntakePage.objects.create(
            job=job, index=0, form_type='c03', form_confidence=0.9, ocr_confidence=0.8,
            fields=_trio('caregiver', 'Khanyi', '1904261049081', '2019-04-26', name='Mpilo'),
        )
        ok = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(ok.status_code, 200, ok.data)
        hh.refresh_from_db()
        caregiver = hh.caregiver
        self.assertEqual(caregiver.surname, 'Khanyi')
        self.assertEqual(caregiver.name, 'Mpilo')
        self.assertEqual(caregiver.id_number, '1904261049081')
        self.assertEqual(hh.members.count(), 0)
        reasons = {row['reason'] for row in ok.data.get('needs_review') or []}
        self.assertIn('legacy_c03_on_caregiver', reasons)


class GeoVocabTests(TestCase):
    def test_phase5_near_misses_resolve_to_supplied_canonical_values(self):
        self.assertEqual(PROVINCES, ('Gauteng',))
        self.assertEqual(DISTRICTS, ('West Rand',))
        self.assertEqual(TOWNS, ('Westonaria',))
        self.assertEqual(MUNICIPALITIES, ())
        self.assertEqual(WARDS, ())
        for target, pairs in PHASE5_GEO_NEAR_MISSES.items():
            for raw, canonical in pairs:
                hit, score = match_geo_field(target, raw)
                self.assertEqual(hit, canonical, f'{target} {raw!r} -> {hit!r} ({score})')

    def test_unrecognisable_value_is_left_raw_and_flagged(self):
        item = {
            'target': 'household.town',
            'value': 'xqzplm',
            'confidence': 0.8,
            'low_confidence': False,
        }
        _apply_geo_vocab(item)
        self.assertEqual(item['value'], 'xqzplm')
        self.assertTrue(item['low_confidence'])
        self.assertEqual(item.get('vocab_match'), '')
        self.assertIn('Not close to a known place name', item.get('note') or '')
        self.assertIsNone(match_geo_field('household.town', 'Cape Town')[0])
        self.assertIsNone(match_closed_value('Nkululuthweni', TOWNS)[0])

    def test_free_text_fields_never_use_the_closed_list(self):
        self.assertNotIn('household.street', GEO_LISTS)
        self.assertNotIn('__display.personnel', GEO_LISTS)
        for target in FREE_TEXT_TARGETS:
            self.assertIsNone(match_geo_field(target, 'Neslonarig')[0])
        street = sanitize_ocr_value('household.street', 'Nkululuthweni', 'printed')
        self.assertEqual(street, 'Nkululuthweni')
        item = {
            'target': 'household.street',
            'value': 'Neslonarig',
            'confidence': 0.8,
            'low_confidence': False,
        }
        _apply_geo_vocab(item)
        self.assertEqual(item['value'], 'Neslonarig')
        self.assertNotIn('vocab_match', item)

    def test_municipality_and_ward_have_no_list_so_are_not_forced(self):
        self.assertNotIn('household.municipality', GEO_LISTS)
        self.assertNotIn('household.ward', GEO_LISTS)
        self.assertIsNone(match_geo_field('household.ward', 'ern ee')[0])
        self.assertIsNone(match_geo_field('household.municipality', 'rando')[0])

    def test_six_fixtures_geo_fields_use_only_supplied_lists(self):
        names = (
            'c01_official_page0.jpg',
            'c01_official_page1.jpg',
            'c02_adult.jpg',
            'c03_mpilo.jpg',
            'c03_ticks.jpg',
        )
        for name in names:
            pages, _ = process_upload(Upload(FIXTURES / name))
            for page in pages:
                for field in page.get('fields') or []:
                    target = field.get('target') or ''
                    value = (field.get('value') or '').strip()
                    if target not in GEO_LISTS or not value:
                        continue
                    with self.subTest(fixture=name, target=target, value=value):
                        allowed = {item.lower() for item in GEO_LISTS[target]}
                        if field.get('vocab_match'):
                            self.assertIn(value.lower(), allowed)
                        else:
                            self.assertTrue(field.get('low_confidence'))
                            self.assertNotIn(value.lower(), allowed)
