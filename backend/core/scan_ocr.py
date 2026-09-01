"""Local OCR for Scan Intake. Nothing is sent off this computer."""
from io import BytesIO

from PIL import Image, ImageOps

from .form_atlas import ATLAS_FORMS, fields_for, form_meta, has_geometry
from .official_blanks import ATLAS_VERSION, blank_path
from .sa_id import parse_sa_id
from .scan_templates import classify_text, extract_fields


def ocr_available():
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def engine_status():
    from .scan_align import opencv_available
    tess = ocr_available()
    cv = opencv_available()
    return {
        'tesseract': tess,
        'opencv': cv,
        'scan_engine': tess or cv,
        'message': '' if (tess or cv) else 'Scan engine not installed on this PC',
    }


def _ocr_image(image, psm=6):
    image = ImageOps.exif_transpose(image).convert('L')
    image = ImageOps.autocontrast(image)
    try:
        import pytesseract
        data = pytesseract.image_to_data(
            image, output_type=pytesseract.Output.DICT, config=f'--psm {psm}'
        )
        words, confs = [], []
        for text, conf in zip(data.get('text') or [], data.get('conf') or []):
            token = (text or '').strip()
            try:
                c = float(conf)
            except (TypeError, ValueError):
                c = -1
            if token and c >= 0:
                words.append(token)
                confs.append(c / 100.0)
        blob = ' '.join(words)
        mean = sum(confs) / len(confs) if confs else 0.35
        return blob, mean, 'tesseract'
    except Exception:
        return '', 0.0, 'none'


def _ocr_crop(crop, kind):
    if kind == 'checkbox':
        from .scan_align import ink_fill_ratio
        ratio = ink_fill_ratio(crop)
        ticked = ratio > 0.18
        return ('X' if ticked else ''), (0.8 if ticked or ratio < 0.08 else 0.45)
    psm = 8 if kind == 'sa_id' else 7 if kind in ('printed', 'date') else 6
    cfg = '--psm %s' % psm
    if kind == 'sa_id':
        cfg += ' -c tessedit_char_whitelist=0123456789'
    try:
        import pytesseract
        text = pytesseract.image_to_string(ImageOps.autocontrast(crop.convert('L')), config=cfg)
        text = ' '.join((text or '').split())
        if kind == 'sa_id':
            text = ''.join(ch for ch in text if ch.isdigit())[:13]
        conf = 0.55 if text else 0.2
        if kind == 'narrative':
            conf = min(conf, 0.4)
        return text, conf
    except Exception:
        return '', 0.0


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
    try:
        image = Image.open(BytesIO(raw))
        pages.append((image, '', 'image'))
    except Exception:
        pages.append((None, '', 'none'))
    return pages


def _visual_form_type(image):
    from .scan_align import match_blank, opencv_available
    if not opencv_available() or image is None:
        return None, 0
    best, score = None, 0
    for code in ATLAS_FORMS:
        path = blank_path(code, 0)
        if not path or not path.exists():
            continue
        blank = Image.open(path)
        _, inliers, failed = match_blank(image.copy(), blank)
        if not failed and inliers > score:
            best, score = code, inliers
    if not best:
        return None, 0
    conf = min(0.95, 0.4 + score / 80.0)
    return best, round(conf, 2)


def _atlas_fields(form_type, aligned, ocr_conf):
    from .scan_align import crop_box
    out = []
    for spec in fields_for(form_type):
        crop = crop_box(aligned, spec['box'])
        value, conf = _ocr_crop(crop, spec['kind'])
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
            'low_confidence': float(conf) < 0.72 or spec['kind'] in ('handwrite', 'narrative'),
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


def _process_one(image, pdf_text, engine, have_tess):
    from .scan_align import deskew_and_contrast, match_blank, opencv_available

    alignment_failed = False
    geometry_missing = False
    warped = None
    inliers = 0
    text, conf, ocr_engine = pdf_text, 0.55, engine
    working = image
    try:
        if image is not None:
            working, _ = deskew_and_contrast(image)
            if have_tess:
                text, conf, ocr_engine = _ocr_image(working)
            else:
                ocr_engine = 'none'
        form_type, form_conf = classify_text(text)
        vis_type, vis_conf = _visual_form_type(working)
        if vis_type and vis_conf >= form_conf:
            form_type, form_conf = vis_type, vis_conf
        fields = []
        if working is not None and has_geometry(form_type) and opencv_available():
            path = blank_path(form_type, 0)
            if path and path.exists():
                blank = Image.open(path)
                warped, inliers, alignment_failed = match_blank(working, blank)
                if warped is not None and not alignment_failed:
                    fields = _atlas_fields(form_type, warped, conf)
                    ocr_engine = (ocr_engine + '+atlas')[:32]
        if not fields:
            if working is not None and not has_geometry(form_type):
                geometry_missing = True
            fields = extract_fields(form_type, text, confidence=max(conf, form_conf * 0.7))
            for item in fields:
                item.setdefault('kind', 'printed')
                item.setdefault('bbox', None)
                item.setdefault('page', 0)
        return {
            'image': working or image,
            'warped': warped,
            'ocr_text': text,
            'ocr_engine': ocr_engine,
            'ocr_confidence': round(float(conf), 2),
            'form_type': form_type,
            'form_confidence': form_conf,
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
            'form_confidence': form_conf,
            'fields': extract_fields(form_type, fallback_text, 0.4),
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
