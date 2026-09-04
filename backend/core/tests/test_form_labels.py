"""The form's own printed wording must never be saved as somebody's answer,
and the full-page text scraper must stand down wherever the atlas can measure
the field instead.
"""
from pathlib import Path

from django.test import TestCase

from core.form_atlas import FIELDS, atlas_coverage, fields_for
from core.form_labels import (
    EXTRACTION_LABELS,
    SCANNED_FORMS,
    SHORT_FORM_LABELS,
    looks_like_form_label,
    normalise_label,
    option_targets,
    printed_labels,
)
from core.scan_templates import _after_label, _first_sa_id, extract_fields
from core.scan_text import looks_like_gibberish, normalise_date_value, sanitize_ocr_value

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'handwrite'

# Junk taken off the real photographs, not invented for the test.
FIXTURE_JUNK_DATES = (
    '99b1 Ol11/', 'be-no-bloe', 'H1-&o-6ooe', 'Z1107o2 12', 'sllloi tno7',
    '2001 28', 'Z8', '(Eee eRe oni es',
)

NAME_TARGETS = (
    'caregiver.surname', 'caregiver.name', 'caregiver.known_as',
    'member.0.surname', 'member.2.name', 'process_note.client_surname',
)


class PrintedLabelsAreNotValuesTests(TestCase):
    """Built from the atlas and the print templates, so it cannot drift."""

    def test_every_label_on_the_five_scanned_sheets_is_refused(self):
        labels = printed_labels()
        self.assertGreater(len(labels), 80, 'the lexicon looks like it stopped loading')
        for label in labels:
            with self.subTest(label=label):
                self.assertTrue(
                    looks_like_form_label(label),
                    f'{label!r} is printed on the paper but would pass as a value',
                )

    def test_a_label_is_refused_as_a_name_however_it_was_typed(self):
        for label in printed_labels():
            for written in (label, label.upper(), label.lower(), f'{label}:', f' {label} '):
                with self.subTest(label=label, written=written):
                    self.assertTrue(looks_like_gibberish(written))
                    for target in NAME_TARGETS:
                        self.assertEqual(
                            sanitize_ocr_value(target, written, 'handwrite'), '',
                            f'{written!r} reached {target}',
                        )

    def test_the_lexicon_is_drawn_from_the_atlas_and_the_templates(self):
        """Every atlas label and tick caption on those sheets is in the list."""
        known = {normalise_label(label) for label in printed_labels()}
        for code in SCANNED_FORMS:
            for spec in fields_for(code):
                if spec.get('label'):
                    self.assertIn(normalise_label(spec['label']), known)
                option = spec.get('option')
                if option and option not in ('true', 'false'):
                    self.assertIn(normalise_label(option), known)
        for labels in EXTRACTION_LABELS.values():
            for label in labels:
                self.assertIn(normalise_label(label), known)

    def test_the_short_printed_forms_on_the_paper_are_refused(self):
        """'ID NO' and 'FIRST NAME' are printed on C01 but shortened."""
        for label in SHORT_FORM_LABELS:
            with self.subTest(label=label):
                self.assertTrue(looks_like_form_label(label))

    def test_real_names_and_places_still_get_through(self):
        keep = [
            'Dlamini', 'Thandi Mokoena', 'Mpilo', 'Motswaledi', 'Ncube', 'Hallie',
            'Westonaria', 'Nkululuthweni', 'Isixhosa', 'Sesotho', 'Grandchild',
            'Khaayi', 'Kgocsi', 'Masego',
        ]
        for value in keep:
            with self.subTest(value=value):
                self.assertFalse(
                    looks_like_form_label(value), f'{value!r} was mistaken for a label',
                )
                self.assertFalse(looks_like_gibberish(value))

    def test_the_charset_rules_still_do_their_own_job(self):
        """The lexicon is added to the old heuristics, it does not replace them."""
        for smash in ('hgftrujyfdyt', 'bcdfghjklmnp', 'sdfghjklzxcvbn'):
            with self.subTest(smash=smash):
                self.assertTrue(looks_like_gibberish(smash))
        self.assertEqual(sanitize_ocr_value('caregiver.surname', 'Hallie', 'handwrite'), 'Hallie')

    def test_a_tick_answer_is_not_treated_as_a_label(self):
        """'Female' and 'Passport Number' are printed captions and real answers."""
        for value, target in (
            ('Female', 'caregiver.sex'),
            ('African', 'caregiver.race'),
            ('South African', 'caregiver.nationality'),
            ('Passport Number', 'caregiver.id_type'),
            ('SA ID Number', 'member.0.id_type'),
            ('Grand Parent Headed', 'caregiver.headship_type'),
        ):
            with self.subTest(value=value):
                self.assertTrue(looks_like_form_label(value))
                self.assertEqual(sanitize_ocr_value(target, value, 'checkbox'), value)
                # but not as free text on a name field
                self.assertEqual(sanitize_ocr_value('caregiver.surname', value, 'handwrite'), '')


class AfterLabelIsAFallbackOnlyTests(TestCase):
    """Scraping the flattened page text is a last resort, not a primary path."""

    ATLAS_FORMS_WITH_GEOMETRY = ('c01', 'c02', 'c03', 'intake', 'cow2_note')

    def _dense_page_text(self):
        return (
            'Surname Name Known As Nationality Date of Birth Sex ID Number\n'
            'Primary Client Surname Caregiver Surname Town Street Province Ward\n'
        )

    def test_no_scraped_field_comes_back_from_an_atlas_covered_sheet(self):
        for code in self.ATLAS_FORMS_WITH_GEOMETRY:
            covered, _targets = atlas_coverage(code)
            with self.subTest(code=code):
                self.assertTrue(covered, f'{code} should have measured geometry')
                for field in extract_fields(code, self._dense_page_text()):
                    self.assertFalse(
                        field['target'],
                        f'{code} scraped {field["target"]} out of the page text',
                    )

    def test_a_target_with_an_atlas_box_is_never_scraped(self):
        """The literal rule: an atlas crop exists, so the scraper stands down."""
        for code in sorted(FIELDS):
            _covered, targets = atlas_coverage(code)
            for field in extract_fields(code, self._dense_page_text()):
                with self.subTest(code=code, target=field['target']):
                    self.assertNotIn(field['target'], targets)

    def test_an_atlas_free_sheet_still_gets_its_values(self):
        text = 'Client surname Dlamini\nClient first name Thandi\nFile no KHAYA-104\n'
        got = {f['target']: f['value'] for f in extract_fields('process_note', text)}
        self.assertEqual(got.get('process_note.client_surname'), 'Dlamini')
        self.assertEqual(got.get('process_note.client_first_name'), 'Thandi')

    def test_a_label_never_answers_for_another_label(self):
        """What follows a label in the blob is usually the next label."""
        for label_list in EXTRACTION_LABELS.values():
            for label in label_list:
                for other in ('Surname', 'ID NO', 'Date of Birth', 'First name', 'Nationality'):
                    text = f'{label} {other}'
                    with self.subTest(label=label, other=other):
                        self.assertEqual(_after_label(text, [label]), '')

    def test_the_scraper_returns_a_real_value_when_there_is_one(self):
        self.assertEqual(_after_label('Surname Dlamini', ['Surname']), 'Dlamini')
        self.assertEqual(_after_label('Known As Mpilo', ['Known As']), 'Mpilo')


class PageWideIdIsNotAttributedTests(TestCase):
    """A 13-digit run found loose on the page belongs to nobody in particular."""

    VALID = '8001015009087'

    def test_an_atlas_sheet_offers_the_number_without_naming_a_person(self):
        text = f'C01 Household Details some text {self.VALID} more text'
        fields = extract_fields('c01', text)
        self.assertEqual(len(fields), 1)
        field = fields[0]
        self.assertEqual(field['value'], self.VALID)
        self.assertEqual(field['target'], '')
        self.assertTrue(field['unassigned'])
        self.assertTrue(field['low_confidence'])
        self.assertIn('nothing says whose', field['note'])

    def test_no_caregiver_field_is_written_from_a_page_wide_scan(self):
        text = f'C01 Household Details {self.VALID}'
        for code in ('c01', 'c02', 'c03', 'intake', 'cow2_note'):
            with self.subTest(code=code):
                targets = {f['target'] for f in extract_fields(code, text)}
                self.assertNotIn('caregiver.id_number', targets)
                self.assertNotIn('caregiver.date_of_birth', targets)
                self.assertNotIn('caregiver.sex', targets)

    def test_an_atlas_free_sheet_keeps_the_old_behaviour(self):
        fields = {f['target']: f['value'] for f in extract_fields(
            'process_note', f'CW 11 process note {self.VALID}',
        )}
        self.assertEqual(fields['caregiver.id_number'], self.VALID)
        self.assertEqual(fields['caregiver.date_of_birth'], '1980-01-01')
        self.assertEqual(fields['caregiver.sex'], 'Male')

    def test_an_invalid_number_on_an_atlas_free_sheet_derives_nothing(self):
        fields = {f['target']: f for f in extract_fields('process_note', 'note 8001015009088')}
        field = fields['caregiver.id_number']
        self.assertEqual(field['value'], '8001015009088')
        self.assertTrue(field['invalid_id'])
        self.assertIn('Not a valid SA ID', field['note'])
        self.assertNotIn('caregiver.date_of_birth', fields)
        self.assertNotIn('caregiver.sex', fields)

    def test_the_scan_prefers_a_valid_number_over_the_first_one_seen(self):
        parsed = _first_sa_id('8001015009088 and then 8001015009087')
        self.assertEqual(parsed['digits'], '8001015009087')
        self.assertTrue(parsed['valid'])


class FixturePagesTests(TestCase):
    """The real photographs, through the real pipeline."""

    class Upload:
        def __init__(self, path):
            self._raw = Path(path).read_bytes()
            self.name = Path(path).name

        def read(self):
            return self._raw

        def seek(self, *args):
            pass

    def _pages(self, name):
        from core.scan_ocr import process_upload
        pages, _tess = process_upload(self.Upload(FIXTURES / name))
        return pages

    def test_the_childs_id_does_not_land_on_the_caregiver(self):
        """Official C01 page 2 is members only: it has no caregiver ID box at all."""
        _covered, targets = atlas_coverage('c01')
        pages = self._pages('c01_official_page1.jpg')
        self.assertEqual(len(pages), 1)
        page = pages[0]
        self.assertEqual(page['form_type'], 'c01')
        self.assertEqual(page['form_page'], 1)
        self.assertEqual(
            [f['target'] for f in fields_for('c01', 1) if f['target'].startswith('caregiver.')],
            [], 'this page is not supposed to describe the caregiver',
        )

        by_target = {f['target']: f for f in page['fields'] if f['target']}
        for field in ('id_number', 'date_of_birth', 'sex'):
            self.assertNotIn(f'caregiver.{field}', by_target)

        # The number is still shown, attached to nobody, when found loose — or
        # it lands in the member box that owns it.
        member_ids = {
            t: (f.get('value') or '')
            for t, f in by_target.items()
            if t.endswith('.id_number')
        }
        self.assertTrue(any(member_ids.values()), member_ids)
        for target, value in member_ids.items():
            if value:
                self.assertTrue(target.startswith('member.'), target)

    def test_no_printed_label_is_saved_as_a_value_on_any_fixture(self):
        names = ('c01_official_page0.jpg', 'c01_official_page1.jpg',
                 'c02_adult.jpg', 'c03_mpilo.jpg', 'c03_ticks.jpg')
        checked = 0
        for name in names:
            if not (FIXTURES / name).exists():
                continue
            for page in self._pages(name):
                for field in page['fields'] or []:
                    value = (field.get('value') or '').strip()
                    if not value or field.get('kind') == 'checkbox':
                        continue
                    if (field.get('target') or '') in option_targets():
                        continue
                    checked += 1
                    with self.subTest(fixture=name, target=field.get('target')):
                        self.assertFalse(
                            looks_like_form_label(value),
                            f'{name} put the printed label {value!r} in '
                            f'{field.get("target")!r}',
                        )
        self.assertGreater(checked, 0, 'no fixture values were checked')

    def test_no_junk_date_is_offered_on_any_fixture(self):
        names = ('c01_official_page0.jpg', 'c01_official_page1.jpg',
                 'c02_adult.jpg', 'c03_mpilo.jpg', 'c03_ticks.jpg')
        for name in names:
            if not (FIXTURES / name).exists():
                continue
            for page in self._pages(name):
                for field in page['fields'] or []:
                    target = field.get('target') or ''
                    is_date = field.get('kind') == 'date' or target.endswith(
                        ('date_of_birth', 'date_joined', 'date_registered'))
                    value = (field.get('value') or '').strip()
                    if not is_date or not value:
                        continue
                    with self.subTest(fixture=name, target=target):
                        self.assertEqual(
                            normalise_date_value(value), value,
                            f'{name} offered {value!r} as a date in {target}',
                        )


class JunkDateIsNotOfferedTests(TestCase):
    """A half-read date box is unread, not a value needing a confirm click."""

    def test_the_junk_off_the_real_photos_is_refused(self):
        for junk in FIXTURE_JUNK_DATES:
            with self.subTest(junk=junk):
                self.assertEqual(normalise_date_value(junk), '')
                self.assertEqual(
                    sanitize_ocr_value('caregiver.date_of_birth', junk, 'date'), '',
                )
                self.assertEqual(
                    sanitize_ocr_value('member.2.date_joined', junk, 'date'), '',
                )

    def test_a_real_date_survives_however_it_was_written(self):
        wanted = {
            '2022-12-28': '2022-12-28',
            '1980-01-01': '1980-01-01',
            '01/02/1980': '1980-02-01',
            '28.12.2022': '2022-12-28',
            '1 2 1980': '1980-02-01',
            '20221228': '2022-12-28',
        }
        for written, iso in wanted.items():
            with self.subTest(written=written):
                self.assertEqual(normalise_date_value(written), iso)
                self.assertEqual(
                    sanitize_ocr_value('caregiver.date_of_birth', written, 'date'), iso,
                )

    def test_a_two_digit_year_is_read_as_a_birth_date_not_the_future(self):
        self.assertEqual(normalise_date_value('01-02-55'), '1955-02-01')
        self.assertEqual(normalise_date_value('01-02-99'), '1999-02-01')

    def test_a_date_nobody_could_have_been_born_on_is_refused(self):
        for impossible in ('2099-01-01', '1107-2-12', '1899-01-01', '2022-13-01', '2022-02-30'):
            with self.subTest(impossible=impossible):
                self.assertEqual(normalise_date_value(impossible), '')

    def test_a_part_read_date_is_refused_rather_than_guessed_at(self):
        for partial in ('1980', '12-28', '2022-12', '28'):
            with self.subTest(partial=partial):
                self.assertEqual(normalise_date_value(partial), '')
