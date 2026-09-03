"""Checkbox reading: the printed form must never look ticked, and a tick group
must resolve to the box that carries the mark rather than the last one declared.
"""
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import TestCase
from PIL import Image, ImageDraw
from rest_framework.test import APIRequestFactory

from core.form_atlas import FIELDS, fields_for
from core.form_io import apply_buckets
from core.official_blanks import blank_path
from core.scan_align import (
    TICK_EMPTY,
    TICK_MARKED,
    TICK_UNREADABLE,
    checkbox_state,
    crop_box,
)
from core.scan_ocr import (
    INK_KEY,
    TICK_KEY,
    _atlas_fields,
    _resolve_option_groups,
    process_upload,
)

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'handwrite'

# Every checkbox the atlas can write to a household field. Locked down so the
# blank-paper regression test cannot quietly start covering fewer boxes.
TARGETED_CHECKBOXES_ON_BLANKS = 69


def blank_checkbox_specs(targeted_only=True):
    """(code, page, spec, blank image) for each atlas checkbox with a blank page."""
    for code in sorted(FIELDS):
        pages = sorted({f['page'] for f in FIELDS[code] if f['kind'] == 'checkbox'})
        for page in pages:
            path = blank_path(code, page)
            if not path or not path.exists():
                continue
            image = Image.open(path)
            for spec in fields_for(code, page):
                if spec['kind'] != 'checkbox':
                    continue
                if targeted_only and not spec.get('target'):
                    continue
                yield code, page, spec, image


def blank_with_ticks(code, page_index, group, options):
    """The official blank with a pen-style X drawn in the named boxes."""
    image = Image.open(blank_path(code, page_index)).convert('RGB')
    draw = ImageDraw.Draw(image)
    width, height = image.size
    for spec in fields_for(code, page_index):
        if spec['kind'] != 'checkbox' or spec.get('group') != group:
            continue
        if spec.get('option') not in options:
            continue
        x0, y0, x1, y1 = spec['box']
        left, top, right, bottom = x0 * width, y0 * height, x1 * width, y1 * height
        pad = (right - left) * 0.22
        draw.line([left + pad, top + pad, right - pad, bottom - pad], fill='black', width=3)
        draw.line([left + pad, bottom - pad, right - pad, top + pad], fill='black', width=3)
    return image


def tick_items(target, options, marked=(), unreadable=()):
    """Checkbox items shaped exactly as _atlas_fields emits them."""
    items = []
    for option in options:
        if option in marked:
            state = TICK_MARKED
        elif option in unreadable:
            state = TICK_UNREADABLE
        else:
            state = TICK_EMPTY
        items.append({
            'label': 'Race',
            'value': option if state == TICK_MARKED else '',
            'target': target,
            'kind': 'checkbox',
            'page': 0,
            'bbox': [0.1, 0.1, 0.2, 0.2],
            'confidence': 0.8,
            'low_confidence': False,
            'confirmed': False,
            'option': option,
            'group': target,
            TICK_KEY: state,
            INK_KEY: 0.30 if state == TICK_MARKED else (0.09 if state == TICK_UNREADABLE else 0.0),
        })
    return items


class Upload:
    def __init__(self, path):
        self._raw = Path(path).read_bytes()
        self.name = Path(path).name

    def read(self):
        return self._raw

    def seek(self, *args):
        pass


class BlankPaperTicksNothingTests(TestCase):
    """Permanent regression test for the defect that started this: the printed
    box outline alone used to read as a tick on 60 of the 76 atlas checkboxes.
    """

    def test_no_checkbox_on_a_pristine_blank_reads_as_ticked(self):
        specs = list(blank_checkbox_specs(targeted_only=True))
        self.assertEqual(
            len(specs), TARGETED_CHECKBOXES_ON_BLANKS,
            'the set of checkboxes under test changed; update the constant on purpose',
        )
        offenders = []
        for code, page, spec, image in specs:
            state, ratio = checkbox_state(crop_box(image, spec['box']))
            if state != TICK_EMPTY:
                offenders.append(
                    f"{code} p{page} {spec.get('group')}={spec.get('option')} "
                    f'state={state} ratio={ratio:.4f}'
                )
        self.assertEqual(offenders, [], 'blank paper must not read as ticked')

    def test_blank_page_measured_against_itself_has_no_added_ink(self):
        """Discounting the blank leaves nothing, even on a printed outline.

        The CW 05 tick boxes used to sit on printed words; they now sit on the
        empty squares. Either way the reference crop must read empty.
        """
        for code, page, spec, image in blank_checkbox_specs(targeted_only=False):
            crop = crop_box(image, spec['box'])
            state, ratio = checkbox_state(crop, crop_box(image, spec['box']))
            self.assertEqual(
                state, TICK_EMPTY,
                f"{code} p{page} {spec.get('option')} read {state} at {ratio:.4f}",
            )

    def test_a_drawn_tick_is_seen_and_its_neighbours_are_not(self):
        image = blank_with_ticks('c01', 0, 'caregiver.race', {'White'})
        blank = Image.open(blank_path('c01', 0))
        seen = {}
        for spec in fields_for('c01', 0):
            if spec.get('group') != 'caregiver.race':
                continue
            state, _ratio = checkbox_state(
                crop_box(image, spec['box']), crop_box(blank, spec['box']),
            )
            seen[spec['option']] = state
        self.assertEqual(seen.pop('White'), TICK_MARKED)
        self.assertEqual(set(seen.values()), {TICK_EMPTY}, seen)


class OptionGroupResolutionTests(TestCase):
    """A group of boxes sharing one target must not collapse by declaration order."""

    def resolve(self, items):
        out = {}
        for field in _resolve_option_groups(items):
            out[field.get('target')] = field
        return out

    def test_the_marked_option_wins_not_the_last_declared(self):
        options = ['African', 'White', 'Coloured', 'Indian']
        field = self.resolve(
            tick_items('caregiver.race', options, marked={'White'})
        )['caregiver.race']
        self.assertEqual(field['value'], 'White')
        self.assertEqual(field['option'], 'White')
        self.assertEqual(field['options'], options)
        self.assertFalse(field['low_confidence'])
        self.assertNotIn(TICK_KEY, field)
        self.assertNotIn(INK_KEY, field)

    def test_every_option_can_win(self):
        options = ['African', 'White', 'Coloured', 'Indian']
        for option in options:
            with self.subTest(option=option):
                field = self.resolve(
                    tick_items('caregiver.race', options, marked={option})
                )['caregiver.race']
                self.assertEqual(field['value'], option)

    def test_two_marked_options_leave_the_field_blank(self):
        field = self.resolve(tick_items(
            'caregiver.race', ['African', 'White', 'Coloured', 'Indian'],
            marked={'African', 'Indian'},
        ))['caregiver.race']
        self.assertEqual(field['value'], '')
        self.assertNotIn('option', field)
        self.assertTrue(field['low_confidence'])
        self.assertIn('2 boxes are marked', field['note'])

    def test_no_marked_option_leaves_the_field_blank(self):
        field = self.resolve(tick_items(
            'caregiver.race', ['African', 'White', 'Coloured', 'Indian'],
        ))['caregiver.race']
        self.assertEqual(field['value'], '')
        self.assertTrue(field['low_confidence'])
        self.assertIn('no box is marked', field['note'])

    def test_a_reading_too_close_to_call_is_flagged_not_guessed(self):
        field = self.resolve(tick_items(
            'caregiver.race', ['African', 'White', 'Coloured', 'Indian'],
            unreadable={'African'},
        ))['caregiver.race']
        self.assertEqual(field['value'], '')
        self.assertTrue(field['low_confidence'])
        self.assertIn('no box could be read as marked', field['note'])

    def test_a_faint_neighbour_keeps_the_answer_but_asks_for_a_look(self):
        field = self.resolve(tick_items(
            'caregiver.race', ['African', 'White', 'Coloured', 'Indian'],
            marked={'White'}, unreadable={'Indian'},
        ))['caregiver.race']
        self.assertEqual(field['value'], 'White')
        self.assertTrue(field['low_confidence'])
        self.assertIn('too faint', field['note'])

    def test_non_group_fields_pass_through_untouched(self):
        typed = {
            'label': 'Surname', 'value': 'Dlamini', 'target': 'caregiver.surname',
            'kind': 'handwrite', 'page': 0, 'confidence': 0.8,
        }
        out = _resolve_option_groups([typed])
        self.assertEqual(out, [typed])


class SyntheticPageThroughAtlasTests(TestCase):
    """The detector and the resolver wired together on a real atlas page."""

    def test_one_ticked_option_reads_back_through_the_atlas(self):
        # 'White' is deliberately not the last-declared race option, which is
        # what the old merge always returned.
        page = blank_with_ticks('c01', 0, 'caregiver.race', {'White'})
        fields = {
            f['target']: f
            for f in _resolve_option_groups(_atlas_fields('c01', page, 0))
            if f.get('kind') == 'checkbox'
        }
        self.assertEqual(fields['caregiver.race']['value'], 'White')
        self.assertEqual(fields['caregiver.sex']['value'], '')
        self.assertEqual(fields['caregiver.marital_status']['value'], '')

    def test_two_ticked_options_read_back_as_blank_through_the_atlas(self):
        page = blank_with_ticks('c01', 0, 'caregiver.race', {'White', 'Coloured'})
        fields = {
            f['target']: f
            for f in _resolve_option_groups(_atlas_fields('c01', page, 0))
            if f.get('kind') == 'checkbox'
        }
        race = fields['caregiver.race']
        self.assertEqual(race['value'], '')
        self.assertTrue(race['low_confidence'])


class FixtureTicksReachTheFileTests(TestCase):
    """A real photographed C01 with real pen ticks, all the way to the models."""

    def setUp(self):
        Group.objects.get_or_create(name='admin')
        self.user = User.objects.create_user(
            'OrphanCoordinator', password='x', is_staff=True, is_superuser=True,
        )
        self.user.groups.add(Group.objects.get(name='admin'))

    def test_real_pen_ticks_are_written_through_apply_buckets(self):
        pages, _tess = process_upload(Upload(FIXTURES / 'c01_household.jpg'))
        page = pages[0]
        self.assertEqual(page['form_type'], 'c01')
        self.assertFalse(page['alignment_failed'])
        buckets = {
            f['target']: f['value']
            for f in page['fields']
            if f.get('kind') == 'checkbox' and f.get('target') and f.get('value')
        }
        # Read off the form by eye; see the contact sheet of aligned crops.
        self.assertEqual(buckets.get('caregiver.race'), 'African')
        self.assertEqual(buckets.get('caregiver.sex'), 'Female')
        self.assertEqual(buckets.get('caregiver.marital_status'), 'Single')
        self.assertEqual(buckets.get('caregiver.nationality'), 'South African')
        self.assertEqual(buckets.get('caregiver.headship_type'), 'Grand Parent Headed')
        self.assertEqual(buckets.get('caregiver.id_type'), 'SA ID Number')
        self.assertEqual(buckets.get('caregiver.disability'), 'false')
        self.assertEqual(buckets.get('member.0.race'), 'African')

        request = APIRequestFactory().post('/api/scan-intake/')
        request.user = self.user
        household = apply_buckets(request, None, buckets)
        caregiver = household.caregiver
        self.assertEqual(caregiver.race, 'African')
        self.assertEqual(caregiver.sex, 'Female')
        self.assertEqual(caregiver.marital_status, 'Single')
        self.assertEqual(caregiver.headship_type, 'Grand Parent Headed')
        self.assertEqual(caregiver.id_type, 'SA ID Number')
        self.assertFalse(caregiver.disability)
        self.assertEqual(household.members.get().race, 'African')

    def test_no_group_is_a_constant_across_the_member_fixtures(self):
        """The old merge returned the same option on every photo and every slot."""
        seen = {}
        for name in ('c01_members_a.jpg', 'c01_members_b.jpg'):
            pages, _tess = process_upload(Upload(FIXTURES / name))
            for field in pages[0]['fields']:
                if field.get('kind') != 'checkbox' or not field.get('target'):
                    continue
                suffix = field['target'].split('.')[-1]
                seen.setdefault(suffix, set()).add(field.get('value') or '')
        self.assertTrue(seen, 'the member pages produced no checkbox fields')
        varying = {k: v for k, v in seen.items() if len(v) > 1}
        self.assertTrue(
            varying,
            f'every group still reads as a constant across slots and photos: {seen}',
        )
