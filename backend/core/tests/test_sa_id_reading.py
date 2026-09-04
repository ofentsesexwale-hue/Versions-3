"""SA ID handling: only a real 13-digit ID may reach an ID field, only a valid
one may work out a date of birth or a sex, and an ID already on another file
must be raised before the scan is written.
"""
from datetime import date
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import Caregiver, Household, HouseholdMember, ScanIntakeJob, ScanIntakePage
from core.sa_id import id_digits, parse_sa_id
from core.scan_ocr import best_sa_id_reading, _adopt_valid_page_id, _reconcile_id_derived
from core.scan_text import sanitize_ocr_value

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'handwrite'

VALID = '8001015009087'      # 1980-01-01, sequence 5009 -> Male, citizen
VALID_FEMALE = '9504045300086'  # 1995-04-04, sequence 5300 -> Male
BAD_CHECKSUM = '8001015009088'
BAD_DATE = '8013015009083'   # month 13


def _with_checksum(first12):
    from core.sa_id import luhn_ok
    for digit in '0123456789':
        if luhn_ok(first12 + digit):
            return first12 + digit
    raise AssertionError('no check digit fits')


class SaIdRuleTests(TestCase):
    """Each rule from the back of the ID book, checked on its own."""

    def test_a_real_id_gives_a_date_of_birth_a_sex_and_a_citizenship(self):
        parsed = parse_sa_id(VALID)
        self.assertTrue(parsed['valid'])
        self.assertTrue(parsed['luhn_ok'])
        self.assertTrue(parsed['date_ok'])
        self.assertEqual(parsed['dob'], '1980-01-01')
        self.assertEqual(parsed['sex'], 'Male')
        self.assertEqual(parsed['citizenship'], 'South African citizen')
        self.assertEqual(parsed['problems'], [])

    def test_spaces_and_dashes_are_not_part_of_the_number(self):
        for written in ('800101 5009 087', '800101-5009-087', ' 800101 5009087 '):
            with self.subTest(written=written):
                parsed = parse_sa_id(written)
                self.assertEqual(parsed['digits'], VALID)
                self.assertTrue(parsed['valid'])
                self.assertEqual(id_digits(written), VALID)

    def test_a_failed_checksum_derives_nothing(self):
        parsed = parse_sa_id(BAD_CHECKSUM)
        self.assertTrue(parsed['is_sa_length'])
        self.assertFalse(parsed['luhn_ok'])
        self.assertFalse(parsed['valid'])
        self.assertIsNone(parsed['dob'])
        self.assertEqual(parsed['sex'], '')
        self.assertIn('last digit does not check out', ' '.join(parsed['problems']))

    def test_a_date_that_is_not_on_the_calendar_derives_nothing(self):
        parsed = parse_sa_id(BAD_DATE)
        self.assertTrue(parsed['is_sa_length'])
        self.assertFalse(parsed['date_ok'])
        self.assertFalse(parsed['valid'])
        self.assertIsNone(parsed['dob'])
        self.assertEqual(parsed['sex'], '')
        self.assertIn('not a real date of birth', ' '.join(parsed['problems']))

    def test_twelve_and_fourteen_digits_are_not_ids_at_all(self):
        for wrong in (VALID[:12], VALID + '4', '74', '4', '019042', '2122712740'):
            with self.subTest(wrong=wrong):
                parsed = parse_sa_id(wrong)
                self.assertFalse(parsed['is_sa_length'])
                self.assertFalse(parsed['valid'])
                self.assertIsNone(parsed['dob'])
                self.assertEqual(parsed['sex'], '')
                self.assertEqual(id_digits(wrong), '')
                self.assertIn('South African ID has 13 digits', parsed['message'])

    def test_the_sequence_digits_decide_the_sex(self):
        female = _with_checksum('850202' + '0001' + '0' + '8')
        male = _with_checksum('850202' + '9999' + '0' + '8')
        self.assertEqual(parse_sa_id(female)['sex'], 'Female')
        self.assertEqual(parse_sa_id(male)['sex'], 'Male')
        # 4999 / 5000 is the boundary.
        self.assertEqual(parse_sa_id(_with_checksum('850202499908'))['sex'], 'Female')
        self.assertEqual(parse_sa_id(_with_checksum('850202500008'))['sex'], 'Male')

    def test_digit_eleven_says_citizen_resident_or_refugee(self):
        wanted = {
            '0': 'South African citizen',
            '1': 'Permanent resident',
            '2': 'Refugee',
        }
        for digit, label in wanted.items():
            number = _with_checksum('8502025100' + digit + '8')
            with self.subTest(digit=digit):
                parsed = parse_sa_id(number)
                self.assertTrue(parsed['valid'], parsed['problems'])
                self.assertEqual(parsed['citizenship'], label)
        for digit in '3456789':
            number = _with_checksum('8502025100' + digit + '8')
            with self.subTest(digit=digit):
                parsed = parse_sa_id(number)
                self.assertFalse(parsed['valid'])
                self.assertIn('not 0 (citizen)', ' '.join(parsed['problems']))

    def test_the_century_is_chosen_so_nobody_is_born_tomorrow(self):
        """A '99' born-year is 1999, not 2099."""
        parsed = parse_sa_id(_with_checksum('9901015009' + '0' + '8'))
        self.assertTrue(parsed['valid'], parsed['problems'])
        self.assertEqual(parsed['dob'], '1999-01-01')
        self.assertLessEqual(date.fromisoformat(parsed['dob']), date.today())

    def test_a_baby_born_this_century_reads_as_this_century(self):
        parsed = parse_sa_id(_with_checksum('1001015009' + '0' + '8'))
        self.assertTrue(parsed['valid'], parsed['problems'])
        self.assertEqual(parsed['dob'], '2010-01-01')


class SanitiserTests(TestCase):
    """Nothing that is not 13 digits may be handed to an ID field."""

    def test_a_part_read_is_dropped_rather_than_written(self):
        for partial in ('74', '4', '144', '019042', '2122712740', VALID[:12]):
            with self.subTest(partial=partial):
                self.assertEqual(sanitize_ocr_value('caregiver.id_number', partial, 'sa_id'), '')
                self.assertEqual(sanitize_ocr_value('member.2.id_number', partial, 'sa_id'), '')

    def test_a_full_number_survives_with_its_spacing_stripped(self):
        self.assertEqual(
            sanitize_ocr_value('caregiver.id_number', '800101 5009 087', 'sa_id'), VALID,
        )

    def test_thirteen_digits_that_fail_the_rules_still_reach_staff(self):
        """Marked invalid, not silently blanked - staff need to see the misread."""
        self.assertEqual(
            sanitize_ocr_value('caregiver.id_number', BAD_CHECKSUM, 'sa_id'), BAD_CHECKSUM,
        )
        self.assertEqual(sanitize_ocr_value('caregiver.id_number', BAD_DATE, 'sa_id'), BAD_DATE)

    def test_letters_in_an_id_box_are_not_an_id(self):
        self.assertEqual(sanitize_ocr_value('caregiver.id_number', 'ID NO', 'sa_id'), '')


class EngineDisagreementTests(TestCase):
    """Both engines read the cell grid; the checksum settles the argument."""

    def test_the_reading_that_passes_the_checksum_wins_over_a_confident_one(self):
        # Tesseract is sure of a number that fails the checksum; RapidOCR is
        # unsure of one that passes. The valid one must win.
        value, conf = best_sa_id_reading([(BAD_CHECKSUM, 0.98), (VALID, 0.31)])
        self.assertEqual(value, VALID)
        self.assertGreater(conf, 0.72)

    def test_thirteen_digits_beat_a_part_read_however_confident(self):
        value, _conf = best_sa_id_reading([('74', 0.99), (BAD_CHECKSUM, 0.20)])
        self.assertEqual(value, BAD_CHECKSUM)

    def test_confidence_only_decides_between_equals(self):
        other = _with_checksum('850202510008')
        value, _conf = best_sa_id_reading([(VALID, 0.40), (other, 0.90)])
        self.assertEqual(value, other)

    def test_neither_engine_reaching_thirteen_digits_reads_as_nothing(self):
        for readings in ([('74', 0.9), ('4', 0.8)], [('', 0.0), ('', 0.0)], [('019042', 0.7), ('', 0.0)]):
            with self.subTest(readings=readings):
                value, conf = best_sa_id_reading(readings)
                self.assertEqual(value, '')
                self.assertLess(conf, 0.3)

    def test_two_halves_are_only_joined_when_the_checksum_agrees(self):
        halves = best_sa_id_reading([(VALID[:7], 0.5), (VALID[7:], 0.5)])
        self.assertEqual(halves[0], VALID)
        # '144' + '1206431708' is 13 digits by accident, not a reading.
        stitched = best_sa_id_reading([('144', 0.5), ('1206431708', 0.5)])
        self.assertEqual(stitched[0], '')

    def test_a_valid_reading_is_reported_more_confidently_than_a_doubtful_one(self):
        _v, good = best_sa_id_reading([(VALID, 0.5)])
        _v, poor = best_sa_id_reading([(BAD_CHECKSUM, 0.5)])
        self.assertGreater(good, poor)


class AdoptPageIdTests(TestCase):
    """A garbled 13-cell read yields to the valid number found on the same page."""

    def _fields(self, box_id, page_id, target='member.2.id_number'):
        return [
            {
                'label': 'ID number read on this page - not placed',
                'value': page_id,
                'target': '',
                'kind': 'sa_id',
                'confidence': 0.55,
                'low_confidence': True,
                'confirmed': False,
                'unassigned': True,
            },
            {
                'label': 'ID Number',
                'value': box_id,
                'target': target,
                'kind': 'sa_id',
                'page': 1,
                'bbox': [0.2, 0.3, 0.6, 0.35],
                'confidence': 0.5,
                'low_confidence': True,
                'confirmed': False,
                'invalid_id': True,
                'note': 'Not a valid SA ID: not a real date of birth',
            },
        ]

    def test_a_near_miss_box_takes_the_valid_page_number(self):
        out = {f.get('target'): f for f in _adopt_valid_page_id(
            self._fields('2121228026107', '2212280261081'),
        )}
        self.assertEqual(out['member.2.id_number']['value'], '2212280261081')
        self.assertFalse(out['member.2.id_number'].get('invalid_id'))
        self.assertEqual(out['']['value'], '2212280261081')
        self.assertTrue(out['']['unassigned'])
        self.assertEqual(out['member.2.date_of_birth']['value'], '2022-12-28')
        self.assertEqual(out['member.2.sex']['value'], 'Female')

    def test_an_empty_box_is_not_filled_from_the_page(self):
        fields = self._fields('', '2212280261081')
        fields[1].pop('invalid_id', None)
        fields[1]['value'] = ''
        out = {f.get('target'): f for f in _adopt_valid_page_id(fields)}
        self.assertEqual(out['member.2.id_number']['value'], '')
        self.assertNotIn('member.2.date_of_birth', out)

    def test_a_dissimilar_valid_page_id_is_not_copied(self):
        out = {f.get('target'): f for f in _adopt_valid_page_id(
            self._fields('2121228026107', VALID),
        )}
        self.assertEqual(out['member.2.id_number']['value'], '2121228026107')
        self.assertTrue(out['member.2.id_number'].get('invalid_id'))


class DerivedValueConflictTests(TestCase):
    """A written date of birth and one worked out from the ID must not overwrite
    each other in silence."""

    def _fields(self, written_dob, id_dob='1980-01-01'):
        written = {
            'label': 'Date of Birth', 'value': written_dob,
            'target': 'caregiver.date_of_birth', 'kind': 'date',
            'page': 0, 'bbox': [0, 0, 1, 1], 'confidence': 0.7,
            'low_confidence': False, 'confirmed': False,
        }
        derived = {
            'label': 'Date of Birth', 'value': id_dob,
            'target': 'caregiver.date_of_birth', 'kind': 'date',
            'page': 0, 'bbox': [0, 0, 1, 1], 'confidence': 0.85,
            'low_confidence': False, 'confirmed': False, '_from_id': True,
        }
        return [written, derived]

    def test_a_disagreement_comes_back_blank_and_names_both_readings(self):
        out = _reconcile_id_derived(self._fields('1979-02-02'))
        self.assertEqual(len(out), 1)
        field = out[0]
        self.assertEqual(field['value'], '')
        self.assertTrue(field['low_confidence'])
        self.assertEqual(
            field['conflict'], {'from_form': '1979-02-02', 'from_id_number': '1980-01-01'},
        )
        self.assertIn('1979-02-02', field['note'])
        self.assertIn('1980-01-01', field['note'])

    def test_an_empty_box_is_filled_from_the_id(self):
        out = _reconcile_id_derived(self._fields(''))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['value'], '1980-01-01')
        self.assertNotIn('conflict', out[0])
        self.assertNotIn('_from_id', out[0])

    def test_agreement_is_not_a_conflict(self):
        out = _reconcile_id_derived(self._fields('1980-01-01'))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['value'], '1980-01-01')
        self.assertNotIn('conflict', out[0])

    def test_a_ticked_sex_that_disagrees_with_the_id_is_flagged(self):
        ticked = {
            'label': 'Sex', 'value': 'Female', 'target': 'caregiver.sex',
            'kind': 'checkbox', 'page': 0, 'bbox': [0, 0, 1, 1],
            'confidence': 0.8, 'low_confidence': False, 'confirmed': False,
            'options': ['Male', 'Female'],
        }
        derived = {
            'label': 'Sex', 'value': 'Male', 'target': 'caregiver.sex',
            'kind': 'printed', 'page': 0, 'bbox': [0, 0, 1, 1],
            'confidence': 0.8, 'low_confidence': False, 'confirmed': False,
            '_from_id': True,
        }
        out = _reconcile_id_derived([ticked, derived])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['value'], '')
        self.assertTrue(out[0]['low_confidence'])
        self.assertEqual(out[0]['conflict'], {'from_form': 'Female', 'from_id_number': 'Male'})

    def test_fields_with_no_id_reading_pass_straight_through(self):
        plain = {'label': 'Surname', 'value': 'Dlamini', 'target': 'caregiver.surname'}
        out = _reconcile_id_derived([plain])
        self.assertEqual(out, [plain])

    def test_an_invalid_id_derives_nothing_to_conflict_with(self):
        """No derived field is produced at all, so the written date stands."""
        self.assertIsNone(parse_sa_id(BAD_CHECKSUM)['dob'])
        self.assertEqual(parse_sa_id(BAD_CHECKSUM)['sex'], '')


class ScanIdWriteTests(TestCase):
    """The save path, end to end, over the API."""

    def setUp(self):
        Group.objects.get_or_create(name='admin')
        self.user = User.objects.create_user(
            'OrphanCoordinator', password='x', is_staff=True, is_superuser=True,
        )
        self.user.groups.add(Group.objects.get(name='admin'))
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=self.user).key}'
        )

    def _job(self, fields, form_type='c01', household=None):
        job = ScanIntakeJob.objects.create(
            created_by=self.user, status='pending', household=household,
        )
        ScanIntakePage.objects.create(
            job=job, index=0, form_type=form_type, form_confidence=0.9,
            ocr_confidence=0.8, fields=fields,
        )
        return job

    def _trio(self, prefix, surname, id_number, dob):
        return [
            {'label': f'{prefix} Surname', 'value': surname,
             'target': f'{prefix}.surname', 'confidence': 0.9, 'confirmed': True},
            {'label': f'{prefix} ID Number', 'value': id_number,
             'target': f'{prefix}.id_number', 'confidence': 0.9, 'confirmed': True},
            {'label': f'{prefix} Date of Birth', 'value': dob,
             'target': f'{prefix}.date_of_birth', 'confidence': 0.9, 'confirmed': True},
        ]

    def test_a_part_read_id_never_reaches_the_field_even_when_confirmed(self):
        for partial in ('74', '4', '019042', VALID[:12], VALID + '9'):
            with self.subTest(partial=partial):
                job = self._job(self._trio('caregiver', 'Dlamini', partial, '1980-01-01'))
                r = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
                self.assertEqual(r.status_code, 200, r.data)
                caregiver = Household.objects.get(pk=r.data['household']).caregiver
                self.assertEqual(caregiver.id_number, '')
                self.assertEqual(caregiver.surname, 'Dlamini')

    def test_a_full_id_is_written_and_its_spacing_stripped(self):
        job = self._job(self._trio('caregiver', 'Dlamini', '800101 5009 087', '1980-01-01'))
        r = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        caregiver = Household.objects.get(pk=r.data['household']).caregiver
        self.assertEqual(caregiver.id_number_digits, VALID)
        self.assertTrue(caregiver.id_number_confirmed)

    def test_a_passport_number_is_not_held_to_thirteen_digits(self):
        fields = self._trio('caregiver', 'Ncube', 'AN412339', '1980-01-01')
        fields.append({
            'label': 'Type of ID', 'value': 'Passport Number',
            'target': 'caregiver.id_type', 'confidence': 0.8, 'confirmed': True,
        })
        job = self._job(fields)
        r = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        caregiver = Household.objects.get(pk=r.data['household']).caregiver
        self.assertEqual(caregiver.id_number, 'AN412339')


class FixtureIdReadingTests(TestCase):
    """The photos that produced '74' and '4' in Phase 0, read again.

    An ID field may hold 13 digits or nothing. Anything in between is the bug
    this phase closes, so it is checked on the real photographs rather than
    only on synthetic input.
    """

    FIXTURE_NAMES = (
        'c01_official_page0.jpg', 'c01_official_page1.jpg',
        'c03_mpilo.jpg', 'c03_ticks.jpg',
    )

    class Upload:
        def __init__(self, path):
            self._raw = Path(path).read_bytes()
            self.name = Path(path).name

        def read(self):
            return self._raw

        def seek(self, *args):
            pass

    def test_no_photograph_yields_a_part_read_id(self):
        from core.scan_ocr import process_upload

        seen = 0
        for name in self.FIXTURE_NAMES:
            path = FIXTURES / name
            if not path.exists():
                continue
            pages, _tess = process_upload(self.Upload(path))
            for page in pages:
                for field in page.get('fields') or []:
                    target = field.get('target') or ''
                    if not target.endswith('id_number'):
                        continue
                    seen += 1
                    value = (field.get('value') or '').strip()
                    with self.subTest(fixture=name, target=target):
                        if not value:
                            continue
                        self.assertEqual(
                            len(value), 13,
                            f'{name} {target} came back as {value!r}, which is neither a '
                            'full ID nor blank',
                        )
                        self.assertTrue(value.isdigit())
                        parsed = parse_sa_id(value)
                        if not parsed['valid']:
                            # Kept for staff to correct, but labelled and inert.
                            self.assertTrue(field.get('invalid_id'))
                            self.assertTrue(field.get('low_confidence'))
                            self.assertIn('Not a valid SA ID', field.get('note') or '')
        self.assertGreater(seen, 0, 'no ID fields were read from the fixtures')

    def test_a_date_of_birth_is_never_taken_from_an_invalid_id(self):
        from core.scan_ocr import process_upload

        for name in ('c01_official_page0.jpg', 'c01_official_page1.jpg'):
            path = FIXTURES / name
            if not path.exists():
                continue
            pages, _tess = process_upload(self.Upload(path))
            for page in pages:
                fields = {f.get('target'): f for f in page.get('fields') or []}
                for target, field in fields.items():
                    if not (target or '').endswith('id_number'):
                        continue
                    if parse_sa_id(field.get('value') or '')['valid']:
                        continue
                    prefix = target.rsplit('.', 1)[0]
                    dob = (fields.get(f'{prefix}.date_of_birth') or {}).get('value') or ''
                    with self.subTest(fixture=name, target=target):
                        self.assertNotEqual(
                            dob, parse_sa_id(field.get('value') or '').get('dob'),
                        )


class DuplicateIdOnScanTests(TestCase):
    """Scanning an ID that is already on another file warns first, like typing it does."""

    def setUp(self):
        Group.objects.get_or_create(name='admin')
        self.user = User.objects.create_user(
            'OrphanCoordinator', password='x', is_staff=True, is_superuser=True,
        )
        self.user.groups.add(Group.objects.get(name='admin'))
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=self.user).key}'
        )
        self.other = Household.objects.create(org_household_number='KHAYA-104')
        Caregiver.objects.create(
            household=self.other, name='Thandi', surname='Mokoena', id_number=VALID,
            surname_confirmed=True, id_number_confirmed=True,
        )

    def _job(self, id_number, household=None):
        job = ScanIntakeJob.objects.create(
            created_by=self.user, status='pending', household=household,
        )
        ScanIntakePage.objects.create(
            job=job, index=0, form_type='c01', form_confidence=0.9, ocr_confidence=0.8,
            fields=[
                {'label': 'Surname', 'value': 'Dlamini', 'target': 'caregiver.surname',
                 'confidence': 0.9, 'confirmed': True},
                {'label': 'ID Number', 'value': id_number, 'target': 'caregiver.id_number',
                 'confidence': 0.9, 'confirmed': True},
                {'label': 'Date of Birth', 'value': '1980-01-01',
                 'target': 'caregiver.date_of_birth', 'confidence': 0.9, 'confirmed': True},
            ],
        )
        return job

    def test_an_id_already_on_another_file_blocks_the_save_and_names_the_file(self):
        job = self._job(VALID)
        r = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(len(r.data['duplicates']), 1)
        dup = r.data['duplicates'][0]
        self.assertEqual(dup['target'], 'caregiver.id_number')
        self.assertEqual(dup['id_number'], VALID)
        self.assertEqual(dup['matches'][0]['org_household_number'], 'KHAYA-104')
        self.assertEqual(dup['matches'][0]['role'], 'caregiver')
        self.assertEqual(dup['matches'][0]['name'], 'Thandi Mokoena')
        # Nothing written while the question is open.
        self.assertEqual(Household.objects.count(), 1)
        self.assertEqual(ScanIntakeJob.objects.get(pk=job.pk).status, 'pending')

    def test_the_same_warning_the_typing_screen_shows(self):
        """The scan warning and IdCheckHint are built from one query."""
        hint = self.client.get('/api/id-check/', {'q': VALID})
        self.assertEqual(hint.status_code, 200)
        job = self._job(VALID)
        scan = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(
            [d['household_id'] for d in hint.data['duplicates']],
            [d['household_id'] for d in scan.data['duplicates'][0]['matches']],
        )

    def test_staff_may_save_once_they_have_seen_the_warning(self):
        job = self._job(VALID)
        blocked = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(blocked.status_code, 400)
        ok = self.client.post(
            f'/api/scan-intake/{job.pk}/confirm/', {'accept_duplicates': True}, format='json',
        )
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertEqual(Household.objects.count(), 2)

    def test_a_new_id_saves_without_a_warning(self):
        job = self._job('9504045300086')
        r = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotIn('duplicates', r.data)

    def test_the_household_being_scanned_into_is_not_its_own_duplicate(self):
        job = self._job(VALID, household=self.other)
        r = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotIn('duplicates', r.data)

    def test_a_training_login_is_not_warned_about_a_live_file(self):
        """scoped_household_qs keeps the two worlds apart, both ways."""
        Group.objects.get_or_create(name='admin')
        demo = User.objects.create_user('demo.admin', password='x')
        demo.groups.add(Group.objects.get(name='admin'))
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=demo).key}')
        job = ScanIntakeJob.objects.create(created_by=demo, status='pending')
        ScanIntakePage.objects.create(
            job=job, index=0, form_type='c01', form_confidence=0.9, ocr_confidence=0.8,
            fields=[
                {'label': 'Surname', 'value': 'Dlamini', 'target': 'caregiver.surname',
                 'confidence': 0.9, 'confirmed': True},
                {'label': 'ID Number', 'value': VALID, 'target': 'caregiver.id_number',
                 'confidence': 0.9, 'confirmed': True},
                {'label': 'Date of Birth', 'value': '1980-01-01',
                 'target': 'caregiver.date_of_birth', 'confidence': 0.9, 'confirmed': True},
            ],
        )
        r = client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotIn('duplicates', r.data)

    def test_a_member_id_on_another_file_is_caught_too(self):
        HouseholdMember.objects.create(
            household=self.other, name='Sipho', surname='Mokoena', id_number='9504045300086',
        )
        job = self._job('9504045300086')
        r = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data['duplicates'][0]['matches'][0]['role'], 'member')

    def test_one_id_read_onto_two_people_in_one_scan_is_raised(self):
        """Keyword extraction can put a child's ID on the caregiver as well."""
        job = ScanIntakeJob.objects.create(created_by=self.user, status='pending')
        ScanIntakePage.objects.create(
            job=job, index=0, form_type='c01', form_confidence=0.9, ocr_confidence=0.8,
            fields=[
                {'label': 'Surname', 'value': 'Dlamini', 'target': 'caregiver.surname',
                 'confidence': 0.9, 'confirmed': True},
                {'label': 'SA ID Number', 'value': '9504045300086',
                 'target': 'caregiver.id_number', 'confidence': 0.9, 'confirmed': True},
                {'label': 'Date of Birth', 'value': '1995-04-04',
                 'target': 'caregiver.date_of_birth', 'confidence': 0.9, 'confirmed': True},
                {'label': 'member.0 Surname', 'value': 'Dlamini',
                 'target': 'member.0.surname', 'confidence': 0.9, 'confirmed': True},
                {'label': 'member.0 ID Number', 'value': '9504045300086',
                 'target': 'member.0.id_number', 'confidence': 0.9, 'confirmed': True},
                {'label': 'member.0 Date of Birth', 'value': '1995-04-04',
                 'target': 'member.0.date_of_birth', 'confidence': 0.9, 'confirmed': True},
            ],
        )
        r = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('two different people', r.data['detail'])
        labels = {d['target']: d['same_scan'] for d in r.data['duplicates']}
        self.assertEqual(labels['caregiver.id_number'], ['member.0 ID Number'])
        self.assertEqual(labels['member.0.id_number'], ['SA ID Number'])
        self.assertEqual(Household.objects.count(), 1)

    def test_two_different_ids_on_one_scan_are_not_duplicates(self):
        job = ScanIntakeJob.objects.create(created_by=self.user, status='pending')
        ScanIntakePage.objects.create(
            job=job, index=0, form_type='c01', form_confidence=0.9, ocr_confidence=0.8,
            fields=[
                {'label': 'Surname', 'value': 'Dlamini', 'target': 'caregiver.surname',
                 'confidence': 0.9, 'confirmed': True},
                {'label': 'SA ID Number', 'value': '9504045300086',
                 'target': 'caregiver.id_number', 'confidence': 0.9, 'confirmed': True},
                {'label': 'Date of Birth', 'value': '1995-04-04',
                 'target': 'caregiver.date_of_birth', 'confidence': 0.9, 'confirmed': True},
                {'label': 'member.0 Surname', 'value': 'Dlamini',
                 'target': 'member.0.surname', 'confidence': 0.9, 'confirmed': True},
                {'label': 'member.0 ID Number', 'value': '9003035200083',
                 'target': 'member.0.id_number', 'confidence': 0.9, 'confirmed': True},
                {'label': 'member.0 Date of Birth', 'value': '1990-03-03',
                 'target': 'member.0.date_of_birth', 'confidence': 0.9, 'confirmed': True},
            ],
        )
        r = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_a_part_read_id_is_not_hunted_for_duplicates(self):
        """'74' is unreadable, so it is dropped rather than matched on."""
        job = self._job('74')
        r = self.client.post(f'/api/scan-intake/{job.pk}/confirm/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotIn('duplicates', r.data)
