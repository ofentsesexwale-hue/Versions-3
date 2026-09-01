"""Local OCR for Scan Intake. Nothing is sent off this computer."""
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from .scan_templates import classify_text, extract_fields


def ocr_available():
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _ocr_image(image):
    image = ImageOps.exif_transpose(image).convert('L')
    image = ImageOps.autocontrast(image)
    try:
        import pytesseract
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config='--psm 6')
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


def process_upload(uploaded):
    """OCR + classify one uploaded PDF or image. Returns page dicts (no files yet)."""
    results = []
    have_tess = ocr_available()
    for image, pdf_text, engine in render_pages(uploaded):
        text, conf, ocr_engine = pdf_text, 0.55, engine
        if image is not None:
            if have_tess:
                text, conf, ocr_engine = _ocr_image(image)
            else:
                ocr_engine = 'none'
        form_type, form_conf = classify_text(text)
        fields = extract_fields(form_type, text, confidence=max(conf, form_conf * 0.7))
        results.append({
            'image': image,
            'ocr_text': text,
            'ocr_engine': ocr_engine,
            'ocr_confidence': round(float(conf), 2),
            'form_type': form_type,
            'form_confidence': form_conf,
            'fields': fields,
        })
    return results, have_tess
