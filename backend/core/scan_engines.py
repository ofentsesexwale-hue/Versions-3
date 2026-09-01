"""Second local OCR engine so Tesseract is not the only reader.

RapidOCR (ONNX) stays on this PC. It is used for handwritten names and
printed lines. Tesseract still reads ID digits and form titles.
"""
from __future__ import annotations

_ENGINE = None
_FAILED = False


def rapidocr_available():
    if _FAILED:
        return False
    try:
        import rapidocr_onnxruntime  # noqa: F401
        import numpy  # noqa: F401
        return True
    except Exception:
        return False


def _engine():
    global _ENGINE, _FAILED
    if _FAILED:
        return None
    if _ENGINE is not None:
        return _ENGINE
    try:
        from rapidocr_onnxruntime import RapidOCR
        _ENGINE = RapidOCR()
        return _ENGINE
    except Exception:
        _FAILED = True
        return None


def read_image(image):
    """Return (full text, mean confidence, engine name). Empty if RapidOCR is missing."""
    engine = _engine()
    if engine is None or image is None:
        return '', 0.0, 'none'
    import numpy as np
    rgb = image.convert('RGB')
    result, _elapsed = engine(np.array(rgb))
    if not result:
        return '', 0.0, 'rapidocr'
    words, confs = [], []
    for item in result:
        if not item or len(item) < 3:
            continue
        text = str(item[1] or '').strip()
        try:
            conf = float(item[2])
        except (TypeError, ValueError):
            conf = 0.0
        if text:
            words.append(text)
            confs.append(conf)
    blob = ' '.join(words)
    mean = sum(confs) / len(confs) if confs else 0.0
    return blob, mean, 'rapidocr'


def read_line(image):
    text, conf, name = read_image(image)
    return text, conf if name != 'none' else 0.0
