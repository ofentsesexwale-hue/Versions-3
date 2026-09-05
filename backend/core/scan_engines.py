"""Printed-label and ID-grid OCR (RapidOCR).

RapidOCR (ONNX) stays on this PC for printed labels, form titles, and SA ID
cell grids. Handwriting crops use TrOCR + LightOnOCR in ``scan_handwrite_engines``.
"""
from __future__ import annotations

import logging
import subprocess
import sys

_ENGINE = None
_FAILED = False
_ERROR = ''
_TRIED_INSTALL = False

logger = logging.getLogger(__name__)


def rapidocr_error():
    return _ERROR


def _try_install():
    """If the venv predates RapidOCR, install it into this same Python once."""
    global _TRIED_INSTALL
    if _TRIED_INSTALL:
        return
    _TRIED_INSTALL = True
    try:
        subprocess.check_call(
            [
                sys.executable,
                '-m',
                'pip',
                'install',
                '--disable-pip-version-check',
                'rapidocr-onnxruntime>=1.4',
                'onnxruntime>=1.16',
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        logger.warning('Could not pip-install RapidOCR: %s', exc)


def rapidocr_available():
    if _FAILED:
        return False
    try:
        import numpy  # noqa: F401
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except Exception:
        _try_install()
        try:
            import numpy  # noqa: F401
            import rapidocr_onnxruntime  # noqa: F401
            return True
        except Exception:
            return False


def _engine():
    global _ENGINE, _FAILED, _ERROR
    if _FAILED:
        return None
    if _ENGINE is not None:
        return _ENGINE
    if not rapidocr_available():
        _FAILED = True
        _ERROR = 'RapidOCR package is missing from this Python (pip install rapidocr-onnxruntime)'
        return None
    try:
        from rapidocr_onnxruntime import RapidOCR
        _ENGINE = RapidOCR()
        _ERROR = ''
        return _ENGINE
    except Exception as exc:
        _FAILED = True
        _ERROR = str(exc) or type(exc).__name__
        logger.exception('RapidOCR failed to start')
        return None


def warmup():
    """Load RapidOCR once so engine_status reports constructor failures."""
    return _engine() is not None


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
