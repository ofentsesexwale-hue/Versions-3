"""Handwriting OCR engines for Scan Intake.

TrOCR (microsoft/trocr-base-handwritten) is the primary reader for every
handwriting crop. LightOnOCR-2-1B (lightonai/LightOnOCR-2-1B) is the
fallback when TrOCR returns empty or low-confidence text.

Every crop is preprocessed first (ported from akincal/OCR): polarity
detection, noise reduction, CLAHE contrast, auto-deskew, and adaptive
thresholding. Inference runs on background worker threads with cooperative
cancel so the UI can abort when the window closes or a new scan starts.

LightOnOCR loads on CPU only (float32, no quantization, no device_map).
Both models download on first use via ``from_pretrained`` and cache locally.
TrOCR loads on the first crop; LightOnOCR loads only when the fallback runs.

RapidOCR and Tesseract stay in ``scan_engines`` / ``scan_ocr`` for printed
labels and ID grids only — they are not used here.
"""
from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Callable

logger = logging.getLogger(__name__)

TROCR_MODEL_ID = 'microsoft/trocr-base-handwritten'
LIGHTON_MODEL_ID = 'lightonai/LightOnOCR-2-1B'
TROCR_LOW_CONF = 0.45

_lock = threading.Lock()
_trocr = {'processor': None, 'model': None, 'error': '', 'tried': False}
_lighton = {'processor': None, 'model': None, 'error': '', 'tried': False}

# Two workers: a cancelled inference may still finish on one thread while the
# next scan starts on the other (torch generate cannot be forcibly aborted).
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='handwrite-ocr')
_sessions_lock = threading.Lock()
# session_id -> {cancel: Event, futures: [Future], progress: {field_key: state}}
_sessions: dict[str, dict] = {}
_worker_local = threading.local()


class HandwriteCancelled(Exception):
    """Raised when a scan session is cancelled mid-inference."""


def trocr_error() -> str:
    return _trocr['error'] or ''


def lightonocr_error() -> str:
    return _lighton['error'] or ''


def trocr_available() -> bool:
    return _trocr['model'] is not None


def lightonocr_available() -> bool:
    return _lighton['model'] is not None


# ---------------------------------------------------------------------------
# Preprocessing — ported from github.com/akincal/OCR scripts/ocr_inference.py
# ---------------------------------------------------------------------------

def analyze_image_quality(image) -> dict:
    """Quality metrics that drive adaptive preprocessing (akincal/OCR)."""
    import cv2
    import numpy as np

    gray = np.array(image.convert('L'))
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    contrast_score = float(gray.std())
    dy = np.abs(np.diff(gray.astype(np.float32), axis=0))
    noise_score = float(np.mean(dy)) if dy.size else 0.0
    return {
        'blur': blur_score,
        'contrast': contrast_score,
        'noise': noise_score,
    }


def fix_polarity(image):
    """Smart polarity detection: dark ink on a light background (akincal/OCR)."""
    import numpy as np
    from PIL import ImageOps

    rgb = image.convert('RGB')
    gray = np.array(rgb.convert('L'))
    if gray.size == 0:
        return rgb
    h, w = gray.shape[:2]
    if h < 2 or w < 2:
        return rgb
    border = np.concatenate([gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]])
    bg = float(np.median(border))
    mean = float(np.mean(gray))
    dark_fraction = float(np.mean(gray < 128))
    if bg < 127 or (mean < 100 and dark_fraction > 0.55):
        return ImageOps.invert(rgb)
    return rgb


def reduce_noise(image, quality=None):
    """Bilateral filter when noisy, light median otherwise (akincal/OCR)."""
    import cv2
    import numpy as np
    from PIL import Image, ImageFilter

    if quality is None:
        quality = analyze_image_quality(image)
    rgb = image.convert('RGB')
    if float(quality.get('noise') or 0) > 30:
        arr = np.array(rgb)
        denoised = cv2.bilateralFilter(arr, 9, 75, 75)
        return Image.fromarray(denoised)
    return rgb.filter(ImageFilter.MedianFilter(size=3))


def enhance_clahe(image, quality=None):
    """CLAHE contrast enhancement for low-contrast crops (akincal/OCR)."""
    import cv2
    import numpy as np
    from PIL import Image, ImageEnhance, ImageOps

    if quality is None:
        quality = analyze_image_quality(image)
    rgb = image.convert('RGB')
    if float(quality.get('contrast') or 0) < 40:
        gray = np.array(rgb.convert('L'))
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        rgb = Image.fromarray(enhanced).convert('RGB')
        contrast_factor = 1.3
    else:
        rgb = ImageOps.autocontrast(rgb, cutoff=1)
        contrast_factor = 1.15
    rgb = ImageEnhance.Contrast(rgb).enhance(contrast_factor)
    sharpness_factor = 1.4 if float(quality.get('blur') or 0) < 100 else 1.15
    return ImageEnhance.Sharpness(rgb).enhance(sharpness_factor)


def deskew_image(image):
    """Auto-deskew via minAreaRect on ink pixels (akincal/OCR deskew_image)."""
    import cv2
    import numpy as np
    from PIL import Image

    arr = np.array(image.convert('RGB'))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    h, w = gray.shape[:2]
    row_ink = np.sum(binary > 0, axis=1)
    strong_rows = row_ink > (0.6 * w)
    if np.any(strong_rows):
        strong_count = int(np.count_nonzero(strong_rows))
        if strong_count <= max(3, int(0.01 * h)):
            return image.convert('RGB')
    coords = np.column_stack(np.where(binary > 0))
    if len(coords) < 100:
        return image.convert('RGB')
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.8 or abs(angle) > 5:
        return image.convert('RGB')
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        arr, matrix, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return Image.fromarray(rotated)


def adaptive_binarize(image):
    """Adaptive Gaussian thresholding (akincal/OCR adaptive_binarize)."""
    import cv2
    import numpy as np
    from PIL import Image

    arr = np.array(image.convert('RGB'))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 21, 10,
    )
    kernel = np.ones((1, 1), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    return Image.fromarray(binary).convert('RGB')


def preprocess_handwriting_crop(image):
    """Run akincal/OCR preprocess steps on every handwriting crop.

    Mirrors ``scripts/ocr_inference.py`` usage order for field crops:
    polarity → deskew → noise reduction → CLAHE → adaptive threshold.
    (Full-page document detection / OSD orientation are skipped — crops are
    already aligned field boxes from Scan Intake.)
    """
    if image is None:
        return image
    try:
        from PIL import ImageOps
        image = ImageOps.exif_transpose(image.convert('RGB'))
        image = fix_polarity(image)
        quality = analyze_image_quality(image)
        image = deskew_image(image)
        image = reduce_noise(image, quality=quality)
        image = enhance_clahe(image, quality=quality)
        image = adaptive_binarize(image)
        return image
    except Exception:
        logger.exception('Handwriting preprocess failed; using original crop')
        try:
            return image.convert('RGB')
        except Exception:
            return image


# ---------------------------------------------------------------------------
# Session / cancel / background workers
# ---------------------------------------------------------------------------

def begin_handwrite_session(session_id: str | None = None) -> str:
    """Start (or reset) a handwriting OCR session. Returns the session id."""
    sid = session_id or uuid.uuid4().hex
    with _sessions_lock:
        previous = _sessions.pop(sid, None)
        if previous:
            previous['cancel'].set()
            for fut in previous.get('futures') or []:
                fut.cancel()
        _sessions[sid] = {
            'cancel': threading.Event(),
            'futures': [],
            'progress': {},
        }
    return sid


def cancel_handwrite_session(session_id: str | None = None) -> None:
    """Cancel one session, or every active session when session_id is None."""
    with _sessions_lock:
        targets = [session_id] if session_id else list(_sessions.keys())
        for sid in targets:
            session = _sessions.get(sid)
            if not session:
                continue
            session['cancel'].set()
            for fut in list(session.get('futures') or []):
                fut.cancel()
            for key, state in list((session.get('progress') or {}).items()):
                if state in ('queued', 'running'):
                    session['progress'][key] = 'cancelled'


def end_handwrite_session(session_id: str) -> None:
    with _sessions_lock:
        _sessions.pop(session_id, None)


def handwrite_session_progress(session_id: str) -> dict:
    with _sessions_lock:
        session = _sessions.get(session_id) or {}
        progress = dict(session.get('progress') or {})
        cancel = session.get('cancel')
        cancelled = bool(cancel and cancel.is_set())
    return {
        'session_id': session_id,
        'cancelled': cancelled,
        'fields': progress,
        'pending': sum(1 for v in progress.values() if v in ('queued', 'running')),
        'done': sum(1 for v in progress.values() if v == 'done'),
    }


def _session_cancel(session_id: str | None):
    if not session_id:
        return None
    with _sessions_lock:
        session = _sessions.get(session_id)
        return session['cancel'] if session else None


def _set_progress(session_id: str | None, field_key: str, state: str) -> None:
    if not session_id or not field_key:
        return
    with _sessions_lock:
        session = _sessions.get(session_id)
        if session is None:
            return
        session['progress'][field_key] = state


def _check_cancel(cancel) -> None:
    if cancel is not None and cancel.is_set():
        raise HandwriteCancelled()


def _trocr_device():
    try:
        import torch
        if torch.cuda.is_available():
            return 'cuda'
    except Exception:
        pass
    return 'cpu'


def _trocr_deps_ok():
    try:
        import torch  # noqa: F401
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel  # noqa: F401
        return True, ''
    except Exception as exc:
        return False, str(exc) or type(exc).__name__


def _lighton_deps_ok():
    try:
        import torch  # noqa: F401
        from transformers import LightOnOcrForConditionalGeneration, LightOnOcrProcessor  # noqa: F401
        return True, ''
    except Exception as exc:
        return False, str(exc) or type(exc).__name__


def _load_trocr():
    """Lazy-load TrOCR once; download + cache on first call."""
    with _lock:
        if _trocr['model'] is not None or _trocr['tried']:
            return _trocr['model'] is not None
        _trocr['tried'] = True
        try:
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel

            processor = TrOCRProcessor.from_pretrained(TROCR_MODEL_ID)
            model = VisionEncoderDecoderModel.from_pretrained(TROCR_MODEL_ID)
            device = _trocr_device()
            model.to(device)
            model.eval()
            _trocr['processor'] = processor
            _trocr['model'] = model
            _trocr['error'] = ''
            logger.info('TrOCR loaded on %s from %s', device, TROCR_MODEL_ID)
            return True
        except Exception as exc:
            _trocr['error'] = str(exc) or type(exc).__name__
            logger.exception('TrOCR failed to load')
            return False


def _load_lightonocr():
    """Lazy-load LightOnOCR-2-1B on CPU only (float32, no quantization)."""
    with _lock:
        if _lighton['model'] is not None or _lighton['tried']:
            return _lighton['model'] is not None
        _lighton['tried'] = True
        try:
            import torch
            from transformers import LightOnOcrForConditionalGeneration, LightOnOcrProcessor

            processor = LightOnOcrProcessor.from_pretrained(
                LIGHTON_MODEL_ID,
                trust_remote_code=True,
            )
            model = LightOnOcrForConditionalGeneration.from_pretrained(
                LIGHTON_MODEL_ID,
                torch_dtype=torch.float32,
                trust_remote_code=True,
            )
            model.to('cpu')
            model.eval()
            _lighton['processor'] = processor
            _lighton['model'] = model
            _lighton['error'] = ''
            logger.info('LightOnOCR loaded on CPU (float32) from %s', LIGHTON_MODEL_ID)
            return True
        except Exception as exc:
            _lighton['error'] = str(exc) or type(exc).__name__
            logger.exception('LightOnOCR failed to load')
            return False


def warmup_trocr() -> bool:
    return _load_trocr()


def warmup_lightonocr() -> bool:
    return _load_lightonocr()


def engine_status() -> dict:
    """Report handwriting-engine load state without forcing a model download."""
    trocr_pkgs, trocr_pkg_err = _trocr_deps_ok()
    lighton_pkgs, lighton_pkg_err = _lighton_deps_ok()
    return {
        'trocr': trocr_available(),
        'trocr_ready': trocr_pkgs,
        'trocr_error': trocr_error() or ('' if trocr_available() or trocr_pkgs else trocr_pkg_err),
        'lightonocr': lightonocr_available(),
        'lightonocr_ready': lighton_pkgs,
        'lightonocr_error': lightonocr_error() or (
            '' if lightonocr_available() or lighton_pkgs else lighton_pkg_err
        ),
    }


def _confidence_from_generate(out) -> float:
    try:
        import torch
        scores = getattr(out, 'scores', None) or []
        sequences = getattr(out, 'sequences', None)
        if not scores or sequences is None:
            return 0.55
        token_ids = sequences[0]
        start = max(0, len(token_ids) - len(scores))
        probs = []
        for step_scores, token_id in zip(scores, token_ids[start:]):
            step_prob = torch.softmax(step_scores[0], dim=-1)[int(token_id)].item()
            probs.append(float(step_prob))
        if not probs:
            return 0.55
        return max(0.05, min(0.99, sum(probs) / len(probs)))
    except Exception:
        return 0.55


def _infer_trocr(image):
    if image is None or not _load_trocr():
        return '', 0.0
    import torch
    processor = _trocr['processor']
    model = _trocr['model']
    rgb = image.convert('RGB')
    pixel_values = processor(images=rgb, return_tensors='pt').pixel_values
    device = next(model.parameters()).device
    pixel_values = pixel_values.to(device)
    with torch.no_grad():
        out = model.generate(
            pixel_values,
            max_new_tokens=64,
            output_scores=True,
            return_dict_in_generate=True,
        )
    text = processor.batch_decode(out.sequences, skip_special_tokens=True)[0]
    text = (text or '').strip()
    if not text:
        return '', 0.0
    return text, _confidence_from_generate(out)


def _infer_lightonocr(image):
    if image is None or not _load_lightonocr():
        return '', 0.0
    import torch
    processor = _lighton['processor']
    model = _lighton['model']
    rgb = image.convert('RGB')
    conversation = [{
        'role': 'user',
        'content': [
            {'type': 'image', 'image': rgb},
            {
                'type': 'text',
                'text': (
                    'Read the handwritten text in this form field crop exactly. '
                    'Return only the written words or digits, with no explanation.'
                ),
            },
        ],
    }]
    inputs = processor.apply_chat_template(
        conversation,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors='pt',
    )
    inputs = {
        key: (
            value.to(device='cpu', dtype=torch.float32)
            if hasattr(value, 'is_floating_point') and value.is_floating_point()
            else value.to('cpu') if hasattr(value, 'to') else value
        )
        for key, value in inputs.items()
    }
    with torch.no_grad():
        output_ids = model.generate(**inputs, max_new_tokens=64)
    prompt_len = inputs['input_ids'].shape[1]
    generated = output_ids[0, prompt_len:]
    text = processor.decode(generated, skip_special_tokens=True)
    text = (text or '').strip()
    if not text:
        return '', 0.0
    return text, 0.7


def _run_on_worker(fn, image):
    """Mark the call stack as already on a handwrite worker (avoid nested pool wait)."""
    _worker_local.on_worker = True
    try:
        return fn(image)
    finally:
        _worker_local.on_worker = False


def _submit_inference(fn, image, cancel, session_id):
    """Run ``fn(image)`` on the handwriting worker thread; honour cancel."""
    _check_cancel(cancel)
    # Already on the pool (e.g. submit_handwriting → read_handwriting): run inline.
    if getattr(_worker_local, 'on_worker', False):
        return fn(image)
    future = _executor.submit(_run_on_worker, fn, image)
    if session_id:
        with _sessions_lock:
            session = _sessions.get(session_id)
            if session is not None:
                session['futures'].append(future)
    while True:
        _check_cancel(cancel)
        try:
            return future.result(timeout=0.2)
        except FuturesTimeout:
            continue
        except HandwriteCancelled:
            future.cancel()
            raise


def read_trocr(image, cancel=None, session_id=None, *, preprocessed=False):
    """Return (text, confidence) from TrOCR. Empty on failure.

    Preprocesses the crop unless ``preprocessed=True`` (when the caller already
    ran ``preprocess_handwriting_crop``).
    """
    if image is None:
        return '', 0.0
    try:
        _check_cancel(cancel)
        prepared = image if preprocessed else preprocess_handwriting_crop(image)
        _check_cancel(cancel)
        return _submit_inference(_infer_trocr, prepared, cancel, session_id)
    except HandwriteCancelled:
        raise
    except Exception:
        logger.exception('TrOCR read failed')
        return '', 0.0


def read_lightonocr(image, cancel=None, session_id=None, *, preprocessed=False):
    """Return (text, confidence) from LightOnOCR. Empty on failure."""
    if image is None:
        return '', 0.0
    try:
        _check_cancel(cancel)
        prepared = image if preprocessed else preprocess_handwriting_crop(image)
        _check_cancel(cancel)
        return _submit_inference(_infer_lightonocr, prepared, cancel, session_id)
    except HandwriteCancelled:
        raise
    except Exception:
        logger.exception('LightOnOCR read failed')
        return '', 0.0


def read_handwriting(image, cancel=None, session_id=None, field_key=''):
    """Primary TrOCR, then LightOnOCR fallback. Returns (text, conf, engine_name).

    Models stay lazy: TrOCR loads on first crop; LightOnOCR loads only when
    the fallback path actually runs. Inference runs on a background worker.
    Preprocess runs once per crop before either engine.
    """
    if cancel is None and session_id:
        cancel = _session_cancel(session_id)
    if field_key:
        _set_progress(session_id, field_key, 'running')
    try:
        _check_cancel(cancel)
        prepared = preprocess_handwriting_crop(image)
        _check_cancel(cancel)
        text, conf = read_trocr(prepared, cancel=cancel, session_id=session_id, preprocessed=True)
        if text and conf >= TROCR_LOW_CONF:
            if field_key:
                _set_progress(session_id, field_key, 'done')
            return text, conf, 'trocr'
        _check_cancel(cancel)
        light_text, light_conf = read_lightonocr(
            prepared, cancel=cancel, session_id=session_id, preprocessed=True,
        )
        if light_text:
            if field_key:
                _set_progress(session_id, field_key, 'done')
            return light_text, light_conf, 'lightonocr'
        if text:
            if field_key:
                _set_progress(session_id, field_key, 'done')
            return text, conf, 'trocr'
        if field_key:
            _set_progress(session_id, field_key, 'done')
        return '', 0.0, 'none'
    except HandwriteCancelled:
        if field_key:
            _set_progress(session_id, field_key, 'cancelled')
        return '', 0.0, 'cancelled'
    except Exception:
        logger.exception('Handwriting read failed')
        if field_key:
            _set_progress(session_id, field_key, 'error')
        return '', 0.0, 'none'


def submit_handwriting(image, session_id, field_key, on_done=None):
    """Queue a handwriting crop on the worker pool; updates session progress."""
    with _sessions_lock:
        if session_id not in _sessions:
            _sessions[session_id] = {
                'cancel': threading.Event(),
                'futures': [],
                'progress': {},
            }
        _sessions[session_id]['progress'][field_key] = 'queued'

    def _job():
        text, conf, engine = read_handwriting(
            image, session_id=session_id, field_key=field_key,
        )
        if on_done:
            try:
                on_done(text, conf, engine)
            except Exception:
                logger.exception('Handwriting on_done callback failed for %s', field_key)
        return text, conf, engine

    future = _executor.submit(_job)
    with _sessions_lock:
        session = _sessions.get(session_id)
        if session is not None:
            session['futures'].append(future)
    return future
