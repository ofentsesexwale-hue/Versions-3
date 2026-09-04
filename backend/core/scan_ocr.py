"""Local OCR for Scan Intake. Nothing is sent off this computer."""
from difflib import SequenceMatcher
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageFilter, ImageOps

from .form_atlas import fields_for, has_geometry
from .official_blanks import ATLAS_VERSION, blank_path
from .sa_id import SA_ID_LENGTH, parse_sa_id, repair_sa_id_digits
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
        r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe',
        r'C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe',
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
    # Official Word C01 rows are ~25px tall. RapidOCR drops letter tops when the
    # crop is a thin strip, so pad before any upscale.
    if height < 40:
        pad = max(12, (48 - height) // 2)
        padded = Image.new('RGB', (width, height + pad * 2), (255, 255, 255))
        padded.paste(image, (0, pad))
        image = padded
        width, height = image.size
    if height < 48:
        scale = 48 / max(height, 1)
        image = image.resize((max(1, int(width * scale)), 48), Image.Resampling.LANCZOS)
    if kind in ('handwrite', 'printed', 'date', 'sa_id') and max(image.size) < 900:
        image = image.resize((image.size[0] * 3, image.size[1] * 3), Image.Resampling.LANCZOS)
        image = image.filter(ImageFilter.SHARPEN)
    return image


def _remove_ruling_lines(image):
    """Blank printed table rules so RapidOCR does not turn them into letters."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return image
    gray = np.array(image.convert('L'))
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    h, w = bw.shape
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(24, w // 6), 1))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(10, h // 2)))
    mask = cv2.bitwise_or(
        cv2.morphologyEx(bw, cv2.MORPH_OPEN, hk),
        cv2.morphologyEx(bw, cv2.MORPH_OPEN, vk),
    )
    mask = cv2.dilate(mask, np.ones((2, 2), np.uint8), iterations=1)
    cleaned = gray.copy()
    cleaned[mask > 0] = 255
    return Image.fromarray(cleaned).convert('RGB')


def _handwrite_variants(crop):
    """Ruling-stripped padded preps (caller also tries the plain prep)."""
    base = ImageOps.exif_transpose(crop.convert('RGB'))
    variants = []
    cleaned = _remove_ruling_lines(base)
    for source in (cleaned, base):
        width, height = source.size
        pad = max(14, (56 - height) // 2)
        padded = Image.new('RGB', (width, height + pad * 2), (255, 255, 255))
        padded.paste(source, (0, pad))
        big = padded.resize((padded.width * 3, padded.height * 3), Image.Resampling.LANCZOS)
        variants.append(ImageOps.autocontrast(big))
        # Mild contrast stretch helps faint freehand without inventing strokes.
        try:
            import cv2
            import numpy as np
            gray = np.array(big.convert('L'))
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            boosted = Image.fromarray(clahe.apply(gray)).convert('RGB')
            variants.append(ImageOps.autocontrast(boosted))
        except Exception:
            pass
    # Deduplicate by size/mode only; content differs.
    return variants[:4]


# Blank Known As / Describe cells still pick up ruling noise or the previous
# row's descenders. Only those often-empty targets use the ink gate.
EMPTY_CELL_INK_MAX = 0.045
_EMPTY_INK_SUFFIXES = ('known_as', 'disability_description')


def _crop_has_handwriting(crop, reference=None, target=''):
    if reference is None:
        return True
    short = (target or '').rsplit('.', 1)[-1]
    if short not in _EMPTY_INK_SUFFIXES and not (target or '').endswith('_describe'):
        return True
    from .scan_align import ink_fill_ratio
    return ink_fill_ratio(crop, reference, inset=0.12) > EMPTY_CELL_INK_MAX


def _score_handwrite_candidate(text, conf):
    letters = ''.join(ch for ch in (text or '') if ch.isalpha())
    if not letters:
        return None
    # Only drop true keyboard-smash or printed form labels. The old gate also
    # rejected plausible handwritten names that the charset heuristics mis-flagged,
    # which is what produced empty fields on clean iPhone JPEGs.
    from .scan_text import _looks_like_smash
    from .form_labels import looks_like_form_label
    if looks_like_form_label(text) or _looks_like_smash(text):
        return None
    # Prefer engine confidence, then longer letter runs (full names beat scraps).
    return (float(conf or 0), len(letters))


def best_sa_id_reading(readings):
    """Pick the best 13-digit ID among what the engines saw.

    An SA ID is handwritten digits in a printed cell grid, which both engines
    misread in different ways, so the checksum is the tie-breaker rather than
    either engine's own confidence. Order of preference: a reading that passes
    every SA ID rule (including after a unique single-digit OCR repair), then
    any 13-digit reading, then engine confidence. If no reading is 13 digits
    long the field is unreadable and stays empty - a partial digit string is
    never an ID.
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
        if len(trimmed) != SA_ID_LENGTH:
            continue
        repaired = repair_sa_id_digits(trimmed)
        parsed = parse_sa_id(repaired)
        chosen = repaired if parsed['valid'] else trimmed
        rank = (
            0 if parsed['valid'] else 1,
            0 if parse_sa_id(chosen)['is_sa_length'] else 1,
            -conf,
        )
        if best_rank is None or rank < best_rank:
            best, best_rank = chosen, rank
    if len(best) != SA_ID_LENGTH:
        return '', 0.2
    return best, (0.9 if parse_sa_id(best)['valid'] else 0.55)


def _ocr_sa_id_variants(crop):
    """Digit readings from plain, ruling-stripped, and extra-upscaled preps."""
    readings = []
    prepared = _prepare_line_crop(crop, 'sa_id')
    from .scan_engines import read_line

    def _add_image(image):
        rapid_text, rapid_conf = read_line(image.convert('RGB'))
        readings.append((rapid_text, rapid_conf))
        try:
            import pytesseract
            cfg = '--oem 1 --psm 7 -c tessedit_char_whitelist=0123456789'
            text = pytesseract.image_to_string(
                ImageOps.autocontrast(image.convert('L')), config=cfg,
            )
            digits = ''.join(ch for ch in (text or '') if ch.isdigit())
            if digits:
                readings.append((digits, 0.55))
        except Exception:
            pass

    _add_image(prepared)
    # Extra scale often recovers an 8 that plain prep reads as 6.
    bigger = prepared.resize(
        (prepared.width * 2, prepared.height * 2), Image.Resampling.LANCZOS,
    )
    _add_image(ImageOps.autocontrast(bigger.filter(ImageFilter.SHARPEN)))
    for image in _handwrite_variants(crop):
        _add_image(image)
    digits, conf = best_sa_id_reading(readings)
    if digits:
        repaired = repair_sa_id_digits(digits)
        if repaired and repaired != digits and parse_sa_id(repaired)['valid']:
            return repaired, 0.85
    return digits, conf


def _ocr_handwrite_variants(crop):
    """Plain padded prep plus ruling-stripped / CLAHE retries; keep the best reading."""
    from .scan_engines import read_line
    prepared = _prepare_line_crop(crop, 'handwrite')
    best_text, best_conf = read_line(prepared)
    best_score = _score_handwrite_candidate(best_text, best_conf)
    if best_score is None:
        best_text, best_conf = '', 0.0
    for image in _handwrite_variants(crop):
        text, conf = read_line(image)
        score = _score_handwrite_candidate(text, conf)
        if score is None:
            continue
        if best_score is None or score > best_score:
            best_text, best_conf, best_score = text, conf, score
    if not best_text:
        return '', 0.0
    return best_text, max(float(best_conf or 0), 0.2)


def _ocr_crop(crop, kind, reference=None, target=''):
    if kind == 'checkbox':
        from .scan_align import checkbox_state
        state, _ratio = checkbox_state(crop, reference)
        if state == TICK_UNREADABLE:
            return '', 0.45
        return ('X' if state == TICK_MARKED else ''), 0.8
    if kind == 'handwrite' and not _crop_has_handwriting(crop, reference, target=target):
        return '', 0.6
    if kind == 'sa_id':
        return _ocr_sa_id_variants(crop)
    if kind == 'handwrite':
        text, mean = _ocr_handwrite_variants(crop)
        if not text:
            return '', mean or 0.0
        # Keep short low-confidence scraps for staff to confirm instead of wiping
        # them. The old gate dropped anything under 0.22 conf with fewer than 3
        # letters, which silently blanked real short names on clean photos.
        return text, max(float(mean or 0), 0.2)
    prepared = _prepare_line_crop(crop, kind)
    from .scan_engines import read_line
    rapid_text, rapid_conf = read_line(prepared)
    psm = 7
    cfg = f'--oem 1 --psm {psm}'
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
            if token:
                words.append(token)
                confs.append(c / 100.0)
        tess_text = ' '.join(words)
        tess_conf = sum(confs) / len(confs) if confs else 0.0
    except Exception:
        pass
    if rapid_text and (rapid_conf >= tess_conf or not tess_text):
        text, mean = rapid_text, rapid_conf
    else:
        text, mean = tess_text, tess_conf
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
    """EXIF-orient and shrink after the paper has been cropped.

    Cap is high enough that Official C01 phone photos (~2100×3100) keep enough
    detail for Word-blank feature match. Shrinking to 2400 used to flip page 2
    onto the page-1 blank (91 inliers vs 185 at full size).
    """
    image = ImageOps.exif_transpose(image)
    if image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')
    width, height = image.size
    longest = max(width, height)
    if longest > 3600:
        scale = 3600 / longest
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
    from .scan_vocab import CLOSED_TEXT, match_closed_text

    target = item.get('target') or ''
    if item.get('vocab_match'):
        return item
    raw = (item.get('value') or '')
    hit, score = match_geo_field(target, raw)
    if hit:
        item['value'] = hit
        item['confidence'] = max(float(item.get('confidence') or 0), score)
        item['vocab_match'] = True
    elif raw and not match_closed_text(target, raw)[0]:
        # Nothing close on either list — leave the raw reading but flag it.
        item['low_confidence'] = True
        item['note'] = (item.get('note') or '') + ' No close match in the known list.'
    return item


def _atlas_fields(image, form_type, page_index, reference=None):
    """Read every measured box on this page."""
    items = []
    for spec in fields_for(form_type, page_index):
        crop = crop_box(image, spec['box'])
        kind = spec.get('kind', 'handwrite')
        text, conf = _ocr_crop(crop, kind, reference=reference, target=spec.get('target', ''))
        item = {
            'label': spec.get('label', ''),
            'value': text,
            'target': spec.get('target', ''),
            'confidence': conf,
            'kind': kind,
        }
        if spec.get('target'):
            item = sanitize_field(item, reference)
        if item.get('target'):
            item = _apply_geo_vocab(item)
        items.append(item)
    return items


def sanitize_field(item, reference=None):
    """Blank values the engines cannot defend, using the field's own rules."""
    target = item.get('target') or ''
    kind = item.get('kind')
    raw = item.get('value') or ''
    cleaned = sanitize_ocr_value(target, raw, kind)
    if cleaned != raw:
        item = dict(item)
        item['value'] = cleaned
        if not cleaned:
            item['confidence'] = min(float(item.get('confidence') or 0.2), 0.2)
            item['note'] = (item.get('note') or '') + ' Rejected by field rules.'
    return item


def process_upload(uploaded, form_hint=None):
    """Full pipeline: pages → aligned → fields. Returns (pages, tess_ok)."""
    pages_out = []
    tess_ok = ocr_available()
    for image, pre_text, engine in render_pages(uploaded):
        if image is None:
            pages_out.append({
                'form_type': 'unknown', 'form_page': None, 'form_confidence': 0.0,
                'ocr_text': pre_text, 'ocr_confidence': 0.0, 'engine': engine,
                'fields': [], 'alignment_failed': True, 'inliers': 0,
            })
            continue
        form_type, page_index, aligned, inliers, failed = identify_form_page(image, hint=form_hint)
        if failed or aligned is None:
            pages_out.append({
                'form_type': form_type or 'unknown', 'form_page': page_index,
                'form_confidence': 0.0, 'ocr_text': pre_text, 'ocr_confidence': 0.0,
                'engine': engine, 'fields': [], 'alignment_failed': True,
                'inliers': inliers or 0,
            })
            continue
        reference = _blank_reference(form_type, page_index) if form_type else None
        fields = _atlas_fields(aligned, form_type, page_index, reference=reference)
        # Full-page text still helps classify sheets the atlas has not measured.
        page_text = ' '.join(f.get('value') or '' for f in fields if f.get('value'))
        if pre_text:
            page_text = (pre_text + ' ' + page_text).strip()
        pages_out.append({
            'form_type': form_type, 'form_page': page_index,
            'form_confidence': 0.0, 'ocr_text': page_text,
            'ocr_confidence': max((f.get('confidence') or 0) for f in fields) if fields else 0.0,
            'engine': engine, 'fields': fields, 'alignment_failed': False,
            'inliers': inliers or 0,
        })
    return pages_out, tess_ok
