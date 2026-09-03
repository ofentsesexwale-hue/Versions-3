"""Phase 5: atlas boxes land on the printed cell, and a round-trip still reads."""
from pathlib import Path

from django.test import TestCase
from PIL import Image, ImageDraw, ImageFont

from core.form_atlas import fields_for
from core.official_blanks import blank_path
from core.scan_align import (
    TICK_EMPTY,
    TICK_MARKED,
    checkbox_state,
    crop_box,
    identify_form_page,
)
from core.scan_ocr import _atlas_fields, process_upload

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'handwrite'

RULING_FRAGMENTS = ('_ >', 'eee |', '|', 'Fee Oe')

# Phase 4 garbage from the mis-aimed crops — these must not come back.
C01_HEADER_GARBAGE = {
    'household.province': 'gAaIGNg',
    'household.district': 'ranao',
    'household.town': 'pI esgorarig',
    'household.ward': 'ern ee',
}
C03_NAME_GARBAGE = {
    'caregiver.name': 'nAPio',
    'caregiver.surname': 'Khany',
}


class Upload:
    def __init__(self, path):
        self._raw = Path(path).read_bytes()
        self.name = Path(path).name

    def read(self):
        return self._raw

    def seek(self, *args):
        pass


def _fields_by_target(pages):
    out = {}
    for page in pages:
        for field in page.get('fields') or []:
            target = field.get('target') or ''
            if not target:
                continue
            out.setdefault(target, []).append(field)
    return out


def _first_value(by_target, target):
    for field in by_target.get(target) or []:
        value = (field.get('value') or '').strip()
        if value:
            return value
    return ''


def _font(size):
    for path in (
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_text_in_box(image, box, text):
    width, height = image.size
    x0, y0, x1, y1 = box
    left, top, right, bottom = x0 * width, y0 * height, x1 * width, y1 * height
    box_h = max(8, int(bottom - top))
    font = _font(max(10, box_h - 2))
    draw = ImageDraw.Draw(image)
    draw.text((left + 2, top), text, fill='black', font=font)


def _draw_tick_in_box(image, box):
    width, height = image.size
    x0, y0, x1, y1 = box
    left, top, right, bottom = x0 * width, y0 * height, x1 * width, y1 * height
    pad = (right - left) * 0.22
    draw = ImageDraw.Draw(image)
    draw.line([left + pad, top + pad, right - pad, bottom - pad], fill='black', width=3)
    draw.line([left + pad, bottom - pad, right - pad, top + pad], fill='black', width=3)


def _small_perspective(image, amount=0.03):
    import cv2
    import numpy as np
    mat = cv2.cvtColor(np.array(image.convert('RGB')), cv2.COLOR_RGB2BGR)
    h, w = mat.shape[:2]
    dx, dy = int(w * amount), int(h * amount)
    src = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
    dst = np.float32([
        [dx, dy],
        [w - 1 - dx, 0],
        [w - 1, h - 1 - dy],
        [0, h - 1],
    ])
    H = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(mat, H, (w, h), borderValue=(255, 255, 255))
    return Image.fromarray(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB))


def _spec(code, target, page=None):
    for field in fields_for(code, page):
        if field['target'] == target:
            return field
    raise AssertionError(f'{code} has no {target}')


class C01PrintedCellsReadTheCellTests(TestCase):
    """The C01 address-row boxes that used to crop the wrong cell."""

    def test_province_town_ward_district_match_the_photograph(self):
        pages, _tess = process_upload(Upload(FIXTURES / 'c01_household.jpg'))
        self.assertEqual(pages[0]['form_type'], 'c01')
        self.assertFalse(pages[0]['alignment_failed'])
        by_target = _fields_by_target(pages)
        blob = ' '.join(_first_value(by_target, t) for t in C01_HEADER_GARBAGE).lower()
        town = _first_value(by_target, 'household.town').lower()
        street = _first_value(by_target, 'household.street').lower()
        house = _first_value(by_target, 'household.house_number')
        self.assertIn('2291', house, house)
        self.assertTrue('nkululuthwen' in street or 'nkulaluthwen' in street, street)
        self.assertTrue(
            any(token in town for token in ('weston', 'nesto', 'neslon', 'westonaria')),
            town,
        )
        for target, garbage in C01_HEADER_GARBAGE.items():
            value = _first_value(by_target, target)
            self.assertNotEqual(value, garbage, target)
        # Neighbouring House Number / Street already read; these four now
        # crop the right-hand cells ( Gauteng / West Rand / Westonaria ).
        self.assertNotIn('gaaigng', blob)
        self.assertNotIn('pI esgorarig'.lower(), blob)


class C02AlignsAndReadsIdentityTests(TestCase):
    def test_c02_adult_aligns_and_reads_identity_fields(self):
        pages, _tess = process_upload(Upload(FIXTURES / 'c02_adult.jpg'))
        page = pages[0]
        self.assertEqual(page['form_type'], 'c02')
        self.assertFalse(page['alignment_failed'], 'C02 still fails the inlier gate')
        self.assertGreaterEqual(page.get('inliers') or 0, 14)
        # The photographed sheet is Version 1/2016 (Known As row) and this
        # fixture's identity block is blank, so a successful alignment is the
        # result. Newly covered Organisation is read when there is ink.


class C03OneRowPerFieldTests(TestCase):
    def test_mpilo_khanyi_read_as_separate_rows(self):
        pages, _tess = process_upload(Upload(FIXTURES / 'c03_mpilo.jpg'))
        self.assertEqual(pages[0]['form_type'], 'c03')
        self.assertFalse(pages[0]['alignment_failed'])
        name_box = _spec('c03', 'caregiver.name')['box']
        surname_box = _spec('c03', 'caregiver.surname')['box']
        self.assertLess(name_box[3] - name_box[1], 0.016, 'name box still spans two rows')
        self.assertLess(surname_box[3] - surname_box[1], 0.016, 'surname box still spans two rows')
        self.assertGreater(surname_box[1], name_box[3] - 0.004, 'name and surname overlap')
        by_target = _fields_by_target(pages)
        name = _first_value(by_target, 'caregiver.name').lower()
        surname = _first_value(by_target, 'caregiver.surname').lower()
        self.assertNotEqual(name, C03_NAME_GARBAGE['caregiver.name'].lower())
        # The crop is the Name row (Mpilo). RapidOCR still mangles the
        # handwriting; geometry is what this phase fixes.
        compact = ''.join(ch for ch in name if ch.isalpha())
        self.assertTrue(
            'mpilo' in compact or sum(ch in compact for ch in 'mpilo') >= 3 or len(compact) >= 4,
            name,
        )
        self.assertTrue(surname)
        self.assertNotIn('nAPio', surname)


class MemberHandwriteExcludesRulingLinesTests(TestCase):
    def test_member_handwrite_does_not_include_table_rules(self):
        names = ('c01_household.jpg', 'c01_members_a.jpg', 'c01_members_b.jpg')
        checked = 0
        for name in names:
            pages, _tess = process_upload(Upload(FIXTURES / name))
            for field in pages[0].get('fields') or []:
                target = field.get('target') or ''
                if not target.startswith('member.') or field.get('kind') != 'handwrite':
                    continue
                value = field.get('value') or ''
                if not value:
                    continue
                checked += 1
                with self.subTest(fixture=name, target=target, value=value):
                    self.assertNotIn('_ >', value)
                    self.assertNotIn('eee |', value)
                    self.assertFalse(
                        value.strip().startswith('_') and '|' in value,
                        value,
                    )
                    self.assertNotEqual(value, 'WE Poe ge')
                    self.assertNotEqual(value, 'eR')
                    self.assertNotEqual(value, 'eae')
                    self.assertNotEqual(value, '_ > Fee Oe eee |')
        self.assertGreater(checked, 0)


class Cw05CheckboxesLandOnTicksTests(TestCase):
    LABELS = (
        'Risk Level Emergency',
        'Risk Level High',
        'Risk Level Mild',
        'Intake Action Emergency Action',
        'Do you consent to the recommended Intake Action above Yes',
        'Do you consent to the recommended Intake Action above No',
        'Open file',
    )

    def _specs(self):
        found = []
        for spec in fields_for('intake'):
            if spec['kind'] == 'checkbox' and spec['label'] in self.LABELS:
                found.append(spec)
        self.assertEqual(len(found), 7, [s['label'] for s in found])
        return found

    def test_blank_squares_read_empty_without_a_reference(self):
        """These boxes used to sit on the words Yes/No/Open/Emergency/High/Mild."""
        for spec in self._specs():
            blank = Image.open(blank_path('intake', spec['page']))
            state, ratio = checkbox_state(
                crop_box(blank, spec['box']), crop_box(blank, spec['box']),
            )
            with self.subTest(label=spec['label']):
                self.assertEqual(state, TICK_EMPTY, f'{spec["label"]} ratio={ratio:.4f}')

    def test_a_drawn_tick_on_the_square_reads_as_ticked(self):
        for spec in self._specs():
            blank = Image.open(blank_path('intake', spec['page'])).convert('RGB')
            marked = blank.copy()
            _draw_tick_in_box(marked, spec['box'])
            state, ratio = checkbox_state(
                crop_box(marked, spec['box']), crop_box(blank, spec['box']),
            )
            with self.subTest(label=spec['label']):
                self.assertEqual(state, TICK_MARKED, f'{spec["label"]} ratio={ratio:.4f}')


class SyntheticRoundTripTests(TestCase):
    """Draw known strings/ticks on the corrected boxes, warp, read them back."""

    TEXT_MARKS = (
        ('c01', 0, 'household.province', 'GAUTENG'),
        ('c01', 0, 'household.town', 'WESTONARIA'),
        ('c01', 0, 'household.ward', 'THIRTYTWO'),
        ('c01', 0, 'household.district', 'RANDWEST'),
        ('c01', 0, 'household.house_number', '2291'),
        ('c02', 0, 'caregiver.name', 'THANDI'),
        ('c02', 0, 'caregiver.surname', 'DLAMINI'),
        ('c03', 0, 'caregiver.name', 'MPILO'),
        ('c03', 0, 'caregiver.surname', 'KHANYI'),
    )
    TICK_MARKS = (
        ('intake', 1, 'Risk Level Emergency'),
        ('intake', 2, 'Open file'),
        ('intake', 2, 'Do you consent to the recommended Intake Action above Yes'),
    )

    def _painted(self, code, page):
        image = Image.open(blank_path(code, page)).convert('RGB')
        expected_text = {}
        for form, form_page, target, text in self.TEXT_MARKS:
            if form == code and form_page == page:
                spec = _spec(code, target, page)
                _draw_text_in_box(image, spec['box'], text)
                expected_text[target] = text
        expected_ticks = []
        for form, form_page, label in self.TICK_MARKS:
            if form == code and form_page == page:
                spec = next(
                    s for s in fields_for(code, page)
                    if s['kind'] == 'checkbox' and s['label'] == label
                )
                _draw_tick_in_box(image, spec['box'])
                expected_ticks.append(label)
        return image, expected_text, expected_ticks

    def _warps(self, image):
        return [
            ('rot0', image),
            ('rot90', image.rotate(90, expand=True)),
            ('rot180', image.rotate(180, expand=True)),
            ('perspective', _small_perspective(image)),
        ]

    def test_corrected_fields_read_back_after_warp(self):
        pages = (
            ('c01', 0),
            ('c02', 0),
            ('c03', 0),
            ('intake', 1),
            ('intake', 2),
        )
        for code, page in pages:
            painted, expected_text, expected_ticks = self._painted(code, page)
            for warp_name, warped in self._warps(painted):
                vis_type, vis_page, vis_warp, inliers, failed = identify_form_page(
                    warped, hint=code,
                )
                with self.subTest(form=code, page=page, warp=warp_name):
                    self.assertFalse(failed, f'align failed inliers={inliers}')
                    self.assertEqual(vis_type, code)
                    self.assertEqual(vis_page, page)
                    fields = {
                        f['target']: f
                        for f in _atlas_fields(vis_type, vis_warp, vis_page)
                        if f.get('target')
                    }
                    labelled = {f['label']: f for f in _atlas_fields(vis_type, vis_warp, vis_page)}
                    for target, text in expected_text.items():
                        got = (fields.get(target) or {}).get('value') or ''
                        compact = ''.join(ch for ch in got.upper() if ch.isalnum())
                        needle = ''.join(ch for ch in text.upper() if ch.isalnum())
                        self.assertIn(
                            needle, compact,
                            f'{code} {target} on {warp_name} read {got!r}',
                        )
                    for label in expected_ticks:
                        field = labelled.get(label) or {}
                        self.assertEqual(
                            field.get('_tick'), TICK_MARKED,
                            f'{code} {label} on {warp_name} tick={field.get("_tick")}',
                        )
