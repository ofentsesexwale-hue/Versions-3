"""Local OCR for Scan Intake. Nothing is sent off this computer."""
from difflib import SequenceMatcher
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageFilter, ImageOps

from .form_atlas import fields_for, has_geometry
from .official_blanks import ATLAS_VERSION, blank_path
from .sa_id import SA_ID_LENGTH, parse_sa_id
from .scan_align import TICK_MARKED, TICK_UNREADABLE
from .scan_templates import classify_text, extract_fields
from .scan_text import looks_like_gibberish, sanitize_ocr_value

# Per-box tick evidence, carried from the detector to the group resolver and
# stripped there so it never reaches the stored page or the browser.
TICK_KEY = '_tick'
INK_KEY = '_ink'
# Marks a date of birth or sex worked out from the ID digits rather than read
# off the paper. Stripped once the two readings have been reconciled.
DERIVED_KEY = '_from_id'


def _register_heif():
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        return True
    except Exception:
        return False


_HEIF_OK = _register_heif()


def _find_tesseract():
    """pytesseract is only a wrapper — Windows needs tesseract.exe on disk."""
    import os
    import shutil

    found = shutil.which('tesseract')
    candidates = [
        found,
        os.environ.get('TESSERACT_CMD'),
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        '/usr/bin/tesseract',
        '/usr/local/bin/tesseract',
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def _configure_tesseract():
    exe = _find_tesseract()
    if not exe:
        return False
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = exe
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


_TESS_OK = _configure_tesseract()


def ocr_available():
    global _TESS_OK
    if _TESS_OK:
        return True
    _TESS_OK = _configure_tesseract()
    return _TESS_OK


def engine_status():
    from .scan_align import opencv_available
    from .scan_engines import rapidocr_error, warmup
    tess = ocr_available()
    cv = opencv_available()
    rapid = warmup()
    parts = []
    if not tess and not cv and not rapid:
        parts.append('Scan engine not installed on this PC')
    elif rapid:
        parts.append('Handwritten names use RapidOCR on this PC; Tesseract still reads ID numbers')
        if not tess:
            parts.append('Install Tesseract-OCR (UB Mannheim) on this PC so printed ID numbers read better')
    else:
        reason = rapidocr_error()
        if reason:
            parts.append(f'RapidOCR did not start: {reason}')
        else:
            parts.append(
                'RapidOCR is not installed in this Python. '
                'Run start-local / install-python-and-engine, or pip install rapidocr-onnxruntime onnxruntime'
            )
        if not tess:
            parts.append('Install Tesseract-OCR (UB Mannheim) for printed ID numbers')
    if not _HEIF_OK:
        parts.append('iPhone HEIC photos need pillow-heif on this PC (or set Camera to Most Compatible)')
    return {
        'tesseract': tess,
        'opencv': cv,
        'heic': _HEIF_OK,
        'rapidocr': rapid,
        'rapidocr_error': rapidocr_error(),
        'scan_engine': tess or cv or rapid,
        'message': '. '.join(parts),
    }


def _ocr_image(image, psm=6):
    from .scan_engines import read_image as rapid_read
    image = ImageOps.exif_transpose(image).convert('RGB')
    rapid_text, rapid_conf, rapid_name = rapid_read(image)
    gray = ImageOps.autocontrast(image.convert('L'))
    tess_text, tess_conf, tess_name = '', 0.0, 'none'
    try:
        import pytesseract
        data = pytesseract.image_to_data(
            gray, output_type=pytesseract.Output.DICT, config=f'--oem 1 --psm {psm}'
        )
        words, confs = [], []
        for text, conf in zip(data.get('text') or [], data.get('conf') or []):
            token = (text or '').strip()
            try:
                c = float(conf)
            except (TypeError, ValueError):
                c = -1
            if token and c >= 40 and not looks_like_gibberish(token):
                words.append(token)
                confs.append(c / 100.0)
        tess_text = ' '.join(words)
        tess_conf = sum(confs) / len(confs) if confs else 0.35
        tess_name = 'tesseract'
    except Exception:
        pass
    # RapidOCR for handwriting/photo text; Tesseract still helps printed titles (C01, CW 05).
    blob = ' '.join(part for part in (rapid_text, tess_text) if part).strip()
    if rapid_name == 'rapidocr' and tess_name == 'tesseract':
        return blob, max(rapid_conf, tess_conf), 'rapidocr+tess'
    if rapid_name == 'rapidocr':
        return rapid_text, rapid_conf, 'rapidocr'
    return tess_text, tess_conf, tess_name


def _prepare_line_crop(crop, kind):
    image = ImageOps.exif_transpose(crop.convert('RGB'))
    image = ImageOps.autocontrast(image)
    width, height = image.size
    if height < 48:
        scale = 48 / max(height, 1)
        image = image.resize((max(1, int(width * scale)), 48), Image.Resampling.LANCZOS)
    if kind in ('handwrite', 'printed', 'date') and max(image.size) < 900:
        image = image.resize((image.size[0] * 3, image.size[1] * 3), Image.Resampling.LANCZOS)
        image = image.filter(ImageFilter.SHARPEN)
    return image


def best_sa_id_reading(readings):
    """Pick the best 13-digit ID among what the engines saw.

    An SA ID is handwritten digits in a printed cell grid, which both engines
    misread in different ways, so the checksum is the tie-breaker rather than
    either engine's own confidence. Order of preference: a reading that passes
    every SA ID rule, then any 13-digit reading, then engine confidence. If no
    reading is 13 digits long the field is unreadable and stays empty - a
    partial digit string is never an ID.
    """
    candidates = []
    seen = set()
    digit_runs = [''.join(ch for ch in (text or '') if ch.isdigit()) for text, _c in readings]
    for (_text, conf), digits in zip(readings, digit_runs):
        if digits and digits not in seen:
            seen.add(digits)
            candidates.append((digits, float(conf or 0.0)))
    # Each engine may catch a different part of the cell grid, so a joined
    # reading is worth testing - but only when the checksum vouches for it.
    # Otherwise two partial reads would be stitched into a plausible-looking
    # ID that nobody wrote.
    joined = ''.join(digit_runs)[:SA_ID_LENGTH]
    if joined not in seen and parse_sa_id(joined)['valid']:
        candidates.append((joined, 0.0))

    best, best_rank = '', None
    for digits, conf in candidates:
        trimmed = digits[:SA_ID_LENGTH]
        parsed = parse_sa_id(trimmed)
        rank = (
            0 if parsed['valid'] else 1,
            0 if parsed['is_sa_length'] else 1,
            -conf,
        )
        if best_rank is None or rank < best_rank:
            best, best_rank = trimmed, rank
    if len(best) != SA_ID_LENGTH:
        return '', 0.2
    return best, (0.9 if parse_sa_id(best)['valid'] else 0.55)


def _ocr_crop(crop, kind, reference=None):
    if kind == 'checkbox':
        from .scan_align import checkbox_state
        state, _ratio = checkbox_state(crop, reference)
        if state == TICK_UNREADABLE:
            return '', 0.45
        return ('X' if state == TICK_MARKED else ''), 0.8
    prepared = _prepare_line_crop(crop, kind)
    from .scan_engines import read_line
    rapid_text, rapid_conf = read_line(prepared)
    if kind == 'handwrite' and looks_like_gibberish(rapid_text):
        rapid_text, rapid_conf = '', 0.0
    psm = 8 if kind == 'sa_id' else 7
    cfg = f'--oem 1 --psm {psm}'
    if kind == 'sa_id':
        cfg += ' -c tessedit_char_whitelist=0123456789'
    tess_text, tess_conf = '', 0.0
    try:
        import pytesseract
        data = pytesseract.image_to_data(
            ImageOps.autocontrast(prepared.convert('L')),
            output_type=pytesseract.Output.DICT,
            config=cfg,
        )
        words, confs = [], []
        for text, conf in zip(data.get('text') or [], data.get('conf') or []):
            token = (text or '').strip()
            try:
                c = float(conf)
            except (TypeError, ValueError):
                c = -1
            if not token or c < 0:
                continue
            if kind == 'sa_id':
                token = ''.join(ch for ch in token if ch.isdigit())
            if kind == 'handwrite' and looks_like_gibberish(token):
                continue
            if token:
                words.append(token)
                confs.append(c / 100.0)
        tess_text = ' '.join(words)
        tess_conf = sum(confs) / len(confs) if confs else 0.0
        if kind == 'sa_id':
            tess_text = ''.join(ch for ch in tess_text if ch.isdigit())[:13]
    except Exception:
        pass
    if kind == 'sa_id':
        return best_sa_id_reading([(tess_text, tess_conf), (rapid_text, rapid_conf)])
    # Prefer RapidOCR on names/handwriting; Tesseract only if RapidOCR is empty.
    if rapid_text and (kind == 'handwrite' or rapid_conf >= tess_conf or not tess_text):
        text, mean = rapid_text, rapid_conf
    else:
        text, mean = tess_text, tess_conf
    if kind == 'handwrite' and not text:
        return '', mean
    if kind == 'handwrite' and mean < 0.22 and len(''.join(ch for ch in text if ch.isalpha())) < 3:
        return '', mean
    if kind == 'narrative':
        mean = min(mean or 0.4, 0.4)
    if not text:
        return '', 0.2
    return text, max(mean, 0.2)


def _pdf_pages_to_images(raw):
    images = []
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(raw)
        for i in range(len(pdf)):
            page = pdf[i]
            bitmap = page.render(scale=2)
            images.append(bitmap.to_pil())
        return images, 'pypdfium2'
    except Exception:
        pass
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(raw))
        texts = []
        for page in reader.pages:
            texts.append(page.extract_text() or '')
        return texts, 'pypdf-text'
    except Exception:
        return [], 'none'


def _is_heic(raw, name):
    if name.endswith(('.heic', '.heif')):
        return True
    return len(raw) > 12 and raw[4:8] == b'ftyp' and raw[8:12] in {b'heic', b'heif', b'mif1', b'msf1'}


def _open_photo(raw, name):
    """Open a phone photo (JPEG/PNG/WebP/HEIC) or fail."""
    if _is_heic(raw, name):
        _register_heif()
    try:
        return Image.open(BytesIO(raw))
    except Exception:
        if _register_heif():
            try:
                return Image.open(BytesIO(raw))
            except Exception:
                return None
        return None


def _prepare_photo(image):
    """EXIF-orient and shrink after the paper has been cropped."""
    image = ImageOps.exif_transpose(image)
    if image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')
    width, height = image.size
    longest = max(width, height)
    if longest > 2400:
        scale = 2400 / longest
        image = image.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)
    return image


def render_pages(uploaded):
    """Yield (PIL image or None, pre-extracted text, engine)."""
    name = (getattr(uploaded, 'name', '') or '').lower()
    raw = uploaded.read()
    uploaded.seek(0)
    pages = []
    if name.endswith('.pdf') or (raw[:4] == b'%PDF'):
        rendered, engine = _pdf_pages_to_images(raw)
        if engine == 'pypdf-text':
            for text in rendered:
                pages.append((None, text, engine))
        else:
            for image in rendered:
                pages.append((image, '', engine))
        return pages
    image = _open_photo(raw, name)
    if image is None:
        pages.append((None, '', 'none'))
        return pages
    from .scan_align import crop_document
    paper, _cropped = crop_document(image)
    pages.append((_prepare_photo(paper), '', 'heic' if _is_heic(raw, name) else 'image'))
    return pages


@lru_cache(maxsize=24)
def _blank_reference(form_type, page_index):
    """The official blank for this page, used to discount printed ink.

    _atlas_fields only ever runs on an image warped onto this blank, so the
    same atlas box covers the same printed content in both.
    """
    path = blank_path(form_type, page_index)
    if not path or not path.exists():
        return None
    return Image.open(path).convert('L')


def _apply_geo_vocab(item):
    """Replace a closed-list OCR near-miss, or flag it if nothing is close."""
    from .service_area import GEO_LISTS, match_geo_field

    target = item.get('target') or ''
    if target not in GEO_LISTS:
        return item
    if item.get('vocab_match'):
        return item
    raw = (item.get('ocr_raw') or item.get('value') or '').strip()
    if not raw:
        return item
    hit, score = match_geo_field(target, raw)
    item['ocr_raw'] = raw
    if hit:
        item['value'] = hit
        item['vocab_match'] = hit
        item['vocab_score'] = score
        item['low_confidence'] = False
        item['confidence'] = round(max(float(item.get('confidence') or 0), float(score or 0)), 2)
    else:
        item['vocab_match'] = ''
        item['low_confidence'] = True
        flag = 'Not close to a known place name — check this value.'
        note = item.get('note') or ''
        if flag not in note:
            item['note'] = f'{note}; {flag}' if note else flag
    return item


def _atlas_fields(form_type, aligned, page_index):
    from .scan_align import checkbox_state, crop_box
    blank = _blank_reference(form_type, page_index)
    out = []
    for spec in fields_for(form_type, page_index):
        crop = crop_box(aligned, spec['box'])
        tick, ratio = None, 0.0
        if spec['kind'] == 'checkbox':
            reference = crop_box(blank, spec['box']) if blank is not None else None
            tick, ratio = checkbox_state(crop, reference)
            value = ''
            conf = 0.45 if tick == TICK_UNREADABLE else 0.8
        else:
            value, conf = _ocr_crop(crop, spec['kind'])
        value = sanitize_ocr_value(spec.get('target') or '', value, spec['kind'])
        option = spec.get('option')
        if spec['kind'] == 'checkbox':
            # The group resolver decides which option wins; on its own a box
            # only knows whether it carries a mark.
            value = option if (option and tick == TICK_MARKED) else ''
        id_problems = []
        if spec['kind'] == 'sa_id' and value:
            parsed = parse_sa_id(value)
            value = parsed['digits']
            id_problems = parsed['problems']
            conf = 0.9 if parsed['valid'] else 0.5
        item = {
            'label': spec['label'],
            'value': value,
            'target': spec.get('target') or '',
            'kind': spec['kind'],
            'page': spec['page'],
            'bbox': list(spec['box']),
            'confidence': round(float(conf), 2),
            'low_confidence': float(conf) < 0.72 or spec['kind'] in ('handwrite', 'narrative') or not value,
            'confirmed': False,
        }
        _apply_geo_vocab(item)
        if id_problems:
            # Shown to staff rather than blanked, but never treated as usable.
            item['invalid_id'] = True
            item['low_confidence'] = True
            item['note'] = 'Not a valid SA ID: ' + '; '.join(id_problems)
        if spec.get('option'):
            item['option'] = spec['option']
        if spec.get('group'):
            item['group'] = spec['group']
        if tick is not None:
            item[TICK_KEY] = tick
            item[INK_KEY] = round(float(ratio), 4)
        if item['target'] or item['value'] or tick is not None:
            out.append(item)
        if spec['kind'] == 'sa_id' and spec.get('target', '').endswith('id_number') and value:
            parsed = parse_sa_id(value)
            prefix = spec['target'].rsplit('.', 1)[0]
            # parse_sa_id only fills these once every rule passes, so an ID
            # that fails the date or the checksum derives nothing.
            if parsed['dob']:
                out.append({
                    'label': 'Date of Birth',
                    'value': parsed['dob'],
                    'target': f'{prefix}.date_of_birth',
                    'kind': 'date',
                    'page': spec['page'],
                    'bbox': list(spec['box']),
                    'confidence': 0.85,
                    'low_confidence': False,
                    'confirmed': False,
                    DERIVED_KEY: True,
                })
            if parsed['sex']:
                out.append({
                    'label': 'Sex',
                    'value': parsed['sex'],
                    'target': f'{prefix}.sex',
                    'kind': 'printed',
                    'page': spec['page'],
                    'bbox': list(spec['box']),
                    'confidence': 0.8,
                    'low_confidence': False,
                    'confirmed': False,
                    DERIVED_KEY: True,
                })
    return out


def _resolve_option_groups(fields):
    """Collapse each mutually-exclusive tick group to the option actually marked.

    Every option in a group (race, sex, marital status, disability,
    nationality, headship, type of ID, type of engagement) shares one target,
    so keeping whichever was declared last in the atlas turns the whole group
    into a constant. Exactly one marked box gives the answer. None marked,
    several marked, or a reading too close to call leaves the field blank and
    flagged for a person, because a blank box is safe and a wrong tick is not.
    """
    groups = {}
    order = []
    passthrough = []
    for item in fields or []:
        key = item.get('group') or ''
        if item.get('kind') != 'checkbox' or not key:
            passthrough.append(_without_tick_keys(item))
            continue
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)

    resolved = []
    for key in order:
        options = groups[key]
        marked = [o for o in options if o.get(TICK_KEY) == TICK_MARKED]
        unreadable = [o for o in options if o.get(TICK_KEY) == TICK_UNREADABLE]
        if len(marked) == 1 and not unreadable:
            chosen, note, confidence = marked[0], '', 0.8
        elif len(marked) == 1:
            chosen, note, confidence = marked[0], 'one box is too faint to be sure', 0.5
        elif len(marked) > 1:
            chosen = None
            note = f"{len(marked)} boxes are marked"
            confidence = 0.35
        else:
            chosen = None
            note = 'no box could be read as marked' if unreadable else 'no box is marked'
            confidence = 0.4 if unreadable else 0.6
        base = _without_tick_keys(chosen or options[0])
        base['value'] = chosen.get('value') if chosen else ''
        base['confidence'] = confidence
        base['low_confidence'] = not chosen or bool(unreadable)
        base['options'] = [o.get('option') for o in options if o.get('option')]
        if not chosen:
            base.pop('option', None)
        if note:
            base['note'] = note
        resolved.append(base)
    return passthrough + resolved


def _without_tick_keys(item):
    out = dict(item)
    out.pop(TICK_KEY, None)
    out.pop(INK_KEY, None)
    return out


def _reconcile_id_derived(fields):
    """Settle a date of birth or sex that the ID digits and the paper both give.

    A valid ID number yields a date of birth and a sex, and C01 also has a
    written date-of-birth box and a sex tick group. Filling an empty box from
    the ID is useful. Quietly replacing what somebody wrote is not: where the
    two disagree, neither reading is presented as the answer, and both are put
    on the field so staff can settle it. A blank date of birth is still filled
    from the confirmed ID when the file is written (see form_io.apply_buckets).
    """
    grouped = {}
    order = []
    out = []
    for item in fields or []:
        target = item.get('target') or ''
        if not target:
            out.append(item)
            continue
        if target not in grouped:
            grouped[target] = {'paper': [], 'from_id': None}
            order.append(target)
        if item.get(DERIVED_KEY):
            grouped[target]['from_id'] = {k: v for k, v in item.items() if k != DERIVED_KEY}
        else:
            grouped[target]['paper'].append(item)

    for target in order:
        paper_items = grouped[target]['paper']
        from_id = grouped[target]['from_id']
        if from_id is None:
            out.extend(paper_items)
            continue
        paper = next((p for p in paper_items if (p.get('value') or '').strip()), None)
        if paper is None:
            # Nothing written in the box: take the ID's answer, but keep the
            # box it belongs to so the canvas still draws it in the right place.
            filled = dict(paper_items[0]) if paper_items else {}
            filled.update({
                'value': from_id['value'],
                'confidence': from_id.get('confidence', 0.85),
                'low_confidence': False,
            })
            out.append(filled or from_id)
            continue
        out.extend(p for p in paper_items if p is not paper)
        paper_value = (paper.get('value') or '').strip()
        id_value = (from_id.get('value') or '').strip()
        if paper_value == id_value:
            out.append(paper)
            continue
        conflicted = dict(paper)
        conflicted['value'] = ''
        conflicted['low_confidence'] = True
        conflicted['confidence'] = 0.35
        conflicted['conflict'] = {'from_form': paper_value, 'from_id_number': id_value}
        conflicted['note'] = (
            f'The form reads "{paper_value}" but the ID number gives "{id_value}". '
            'Check the document and type the right one.'
        )
        out.append(conflicted)
    return out


def _atlas_priority(item):
    """Rank two atlas boxes that claim the same target, so order cannot decide.

    C01 puts a free-text "Describe" box on caregiver.nationality, the target
    its tick group already owns. The group is the structural answer for that
    field, and where the group could not be read a blank beats stray text.
    """
    return (
        0 if item.get('kind') == 'checkbox' else 1,
        0 if (item.get('value') or '').strip() else 1,
    )


def _merge_extracted(atlas_fields, keyword_fields):
    """Keep atlas boxes; fill empty targets from full-page OCR only when the text is plausible."""
    by_target = {}
    extras = []
    for item in _reconcile_id_derived(_resolve_option_groups(atlas_fields)):
        target = item.get('target') or ''
        if not target:
            extras.append(item)
            continue
        prev = by_target.get(target)
        if prev is None or _atlas_priority(item) < _atlas_priority(prev):
            by_target[target] = item
    for item in keyword_fields or []:
        target = item.get('target') or ''
        if not target:
            # A reading nobody could place, e.g. an ID found loose in the page
            # text. It belongs to no field, so it is shown, not written.
            if (item.get('value') or '').strip():
                extras.append(item)
            continue
        incoming = sanitize_ocr_value(target, item.get('value') or '', item.get('kind'))
        if not incoming:
            continue
        item = dict(item)
        item['value'] = incoming
        _apply_geo_vocab(item)
        prev = by_target.get(target)
        if not prev:
            by_target[target] = item
        elif not (prev.get('value') or '').strip():
            filled = dict(prev)
            filled['value'] = incoming
            filled['low_confidence'] = True
            filled['confidence'] = min(float(prev.get('confidence') or 0.5), float(item.get('confidence') or 0.5))
            by_target[target] = filled
    return extras + list(by_target.values())


# A 13-cell crop that includes an extra ruling often yields a 13-digit
# near-miss (invalid date or checksum). The same page text usually still
# contains the real number. Only replace when the two readings look like
# the same ID — never copy a page-wide number onto an empty box.
_PAGE_ID_NEAR_MISS = 0.65


def _derived_id_fields(prefix, parsed, page, bbox):
    extra = []
    if parsed.get('dob'):
        extra.append({
            'label': 'Date of Birth',
            'value': parsed['dob'],
            'target': f'{prefix}.date_of_birth',
            'kind': 'date',
            'page': page,
            'bbox': list(bbox or [0, 0, 1, 1]),
            'confidence': 0.85,
            'low_confidence': False,
            'confirmed': False,
            DERIVED_KEY: True,
        })
    if parsed.get('sex'):
        extra.append({
            'label': 'Sex',
            'value': parsed['sex'],
            'target': f'{prefix}.sex',
            'kind': 'printed',
            'page': page,
            'bbox': list(bbox or [0, 0, 1, 1]),
            'confidence': 0.8,
            'low_confidence': False,
            'confirmed': False,
            DERIVED_KEY: True,
        })
    return extra


def _adopt_valid_page_id(fields):
    """If a box read an invalid 13-digit near-miss of a valid page ID, keep the valid one."""
    valid_page = []
    for item in fields or []:
        if not item.get('unassigned'):
            continue
        parsed = parse_sa_id(item.get('value') or '')
        if parsed['valid']:
            valid_page.append(parsed['digits'])
    if not valid_page:
        return list(fields or [])

    out = []
    adopted = []
    for item in fields or []:
        target = item.get('target') or ''
        if item.get('kind') != 'sa_id' or not target.endswith('id_number'):
            out.append(item)
            continue
        parsed = parse_sa_id(item.get('value') or '')
        if parsed['valid'] or not parsed['is_sa_length']:
            out.append(item)
            continue
        best, best_ratio = None, 0.0
        for cand in valid_page:
            ratio = SequenceMatcher(None, parsed['digits'], cand).ratio()
            if ratio > best_ratio:
                best, best_ratio = cand, ratio
        if not best or best_ratio < _PAGE_ID_NEAR_MISS:
            out.append(item)
            continue
        fixed = dict(item)
        winner = parse_sa_id(best)
        fixed['value'] = winner['digits']
        fixed['confidence'] = 0.85
        fixed['low_confidence'] = False
        fixed.pop('invalid_id', None)
        if 'Not a valid SA ID' in (fixed.get('note') or ''):
            fixed.pop('note', None)
        out.append(fixed)
        adopted.append((target.rsplit('.', 1)[0], winner, item.get('page'), item.get('bbox')))
    for prefix, parsed, page, bbox in adopted:
        out.extend(_derived_id_fields(prefix, parsed, page, bbox))
    return out


def _clean_fields(fields):
    cleaned = []
    for item in fields or []:
        item = dict(item)
        item['value'] = sanitize_ocr_value(item.get('target') or '', item.get('value') or '', item.get('kind'))
        _apply_geo_vocab(item)
        cleaned.append(item)
    return cleaned


def _process_one(image, pdf_text, engine, have_tess):
    from .scan_align import deskew_and_contrast, identify_form_page, match_blank, opencv_available

    alignment_failed = False
    geometry_missing = False
    warped = None
    inliers = 0
    text, conf, ocr_engine = pdf_text, 0.55, engine
    working = image
    form_page = 0
    try:
        if image is not None:
            working, _ = deskew_and_contrast(image)
            text, conf, ocr_engine = _ocr_image(working)
        form_type, form_conf = classify_text(text)
        vis_type, vis_page, vis_warp, vis_inliers, vis_failed = identify_form_page(working, hint=form_type)
        if vis_type and not vis_failed:
            form_type, form_conf = vis_type, min(0.95, 0.45 + vis_inliers / 80.0)
            form_page = vis_page if vis_page is not None else 0
            warped = vis_warp
            inliers = vis_inliers
            alignment_failed = False
        elif vis_type:
            form_type = vis_type
            form_page = vis_page or 0
            alignment_failed = True
        fields = []
        if warped is not None and has_geometry(form_type):
            fields = _atlas_fields(form_type, warped, form_page)
            ocr_engine = (ocr_engine + '+atlas')[:32]
        elif working is not None and has_geometry(form_type) and opencv_available() and warped is None:
            path = blank_path(form_type, form_page)
            if path and path.exists():
                blank = Image.open(path)
                warped, inliers, alignment_failed = match_blank(working, blank)
                if warped is not None and not alignment_failed:
                    fields = _atlas_fields(form_type, warped, form_page)
                    ocr_engine = (ocr_engine + '+atlas')[:32]
        keywords = extract_fields(form_type, text, confidence=max(conf, form_conf * 0.7))
        for item in keywords:
            item.setdefault('kind', 'printed')
            item.setdefault('bbox', None)
            item.setdefault('page', form_page)
        if not fields:
            if working is not None and not has_geometry(form_type):
                geometry_missing = True
            fields = keywords
        else:
            fields = _adopt_valid_page_id(_merge_extracted(fields, keywords))
            fields = _reconcile_id_derived(fields)
        fields = _clean_fields(fields)
        return {
            'image': working or image,
            'warped': warped,
            'ocr_text': text,
            'ocr_engine': ocr_engine,
            'ocr_confidence': round(float(conf), 2),
            'form_type': form_type,
            'form_page': form_page,
            'form_confidence': round(float(form_conf), 2),
            'fields': fields,
            'alignment_failed': alignment_failed,
            'geometry_missing': geometry_missing,
            'inliers': inliers,
            'atlas_version': ATLAS_VERSION,
        }
    except Exception as exc:
        fallback_text = text or pdf_text or ''
        form_type, form_conf = classify_text(fallback_text)
        return {
            'image': image,
            'warped': None,
            'ocr_text': fallback_text,
            'ocr_engine': ocr_engine or 'fallback',
            'ocr_confidence': round(float(conf or 0), 2),
            'form_type': form_type,
            'form_page': 0,
            'form_confidence': form_conf,
            'fields': _clean_fields(extract_fields(form_type, fallback_text, 0.4)),
            'alignment_failed': True,
            'geometry_missing': False,
            'inliers': 0,
            'atlas_version': ATLAS_VERSION,
            'error': str(exc)[:200],
        }


def process_upload(uploaded):
    """OCR + classify one uploaded PDF or image. Returns page dicts (no files yet)."""
    results = []
    have_tess = ocr_available()
    for image, pdf_text, engine in render_pages(uploaded):
        results.append(_process_one(image, pdf_text, engine, have_tess))
    return results, have_tess
