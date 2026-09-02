"""Local OCR for Scan Intake. Nothing is sent off this computer."""
from io import BytesIO

from PIL import Image, ImageFilter, ImageOps

from .form_atlas import fields_for, has_geometry
from .official_blanks import ATLAS_VERSION, blank_path
from .sa_id import parse_sa_id
from .scan_templates import classify_text, extract_fields
from .scan_text import looks_like_gibberish, sanitize_ocr_value


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


def _ocr_crop(crop, kind):
    if kind == 'checkbox':
        from .scan_align import ink_fill_ratio
        ratio = ink_fill_ratio(crop)
        ticked = ratio > 0.12
        return ('X' if ticked else ''), (0.8 if ticked or ratio < 0.08 else 0.45)
    prepared = _prepare_line_crop(crop, kind)
    rapid_text, rapid_conf = '', 0.0
    if kind != 'sa_id':
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
        digits = ''.join(ch for ch in (rapid_text + ' ' + tess_text) if ch.isdigit())
        # Prefer a 13-digit SA ID from either engine.
        blob = ''.join(ch for ch in rapid_text if ch.isdigit()) + ''.join(ch for ch in tess_text if ch.isdigit())
        for candidate in (tess_text, ''.join(ch for ch in rapid_text if ch.isdigit()), digits):
            only = ''.join(ch for ch in (candidate or '') if ch.isdigit())[:13]
            if len(only) == 13:
                return only, 0.75
        only = ''.join(ch for ch in (tess_text or rapid_text or '') if ch.isdigit())[:13]
        return only, (0.7 if only else 0.2)
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


def _atlas_fields(form_type, aligned, page_index):
    from .scan_align import crop_box
    out = []
    for spec in fields_for(form_type, page_index):
        crop = crop_box(aligned, spec['box'])
        value, conf = _ocr_crop(crop, spec['kind'])
        value = sanitize_ocr_value(spec.get('target') or '', value, spec['kind'])
        option = spec.get('option')
        if spec['kind'] == 'checkbox' and option and value == 'X':
            value = option
        elif spec['kind'] == 'checkbox' and value != 'X':
            value = ''
        if spec['kind'] == 'sa_id' and value:
            parsed = parse_sa_id(value)
            if parsed.get('digits'):
                value = parsed['digits']
                conf = 0.9 if parsed.get('luhn_ok') else 0.5
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
        if spec.get('option'):
            item['option'] = spec['option']
        if spec.get('group'):
            item['group'] = spec['group']
        if item['target'] or item['value']:
            out.append(item)
        if spec['kind'] == 'sa_id' and spec.get('target', '').endswith('id_number') and value:
            parsed = parse_sa_id(value)
            prefix = spec['target'].rsplit('.', 1)[0]
            if parsed.get('dob'):
                out.append({
                    'label': 'Date of Birth',
                    'value': parsed['dob'],
                    'target': f'{prefix}.date_of_birth',
                    'kind': 'date',
                    'page': spec['page'],
                    'bbox': list(spec['box']),
                    'confidence': 0.85 if parsed.get('luhn_ok') else 0.45,
                    'low_confidence': not parsed.get('luhn_ok'),
                    'confirmed': False,
                })
            if parsed.get('sex'):
                out.append({
                    'label': 'Sex',
                    'value': parsed['sex'],
                    'target': f'{prefix}.sex',
                    'kind': 'printed',
                    'page': spec['page'],
                    'bbox': list(spec['box']),
                    'confidence': 0.8 if parsed.get('luhn_ok') else 0.4,
                    'low_confidence': not parsed.get('luhn_ok'),
                    'confirmed': False,
                })
    return out


def _merge_extracted(atlas_fields, keyword_fields):
    """Keep atlas boxes; fill empty targets from full-page OCR only when the text is plausible."""
    by_target = {}
    extras = []
    for item in atlas_fields or []:
        target = item.get('target') or ''
        if target:
            by_target[target] = item
        else:
            extras.append(item)
    for item in keyword_fields or []:
        target = item.get('target') or ''
        if not target:
            continue
        incoming = sanitize_ocr_value(target, item.get('value') or '', item.get('kind'))
        if not incoming:
            continue
        item = dict(item)
        item['value'] = incoming
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


def _clean_fields(fields):
    cleaned = []
    for item in fields or []:
        item = dict(item)
        item['value'] = sanitize_ocr_value(item.get('target') or '', item.get('value') or '', item.get('kind'))
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
            fields = _merge_extracted(fields, keywords)
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
