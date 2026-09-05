"""Handwriting OCR engines for Scan Intake.

TrOCR (microsoft/trocr-base-handwritten) is the primary reader for every
handwriting crop. LightOnOCR-2-1B (lightonai/LightOnOCR-2-1B) is the
fallback when TrOCR returns empty or low-confidence text. LightOnOCR loads
on CPU only (float32, no quantization, no device_map). Both download
automatically on first use via ``from_pretrained`` and cache under the
local Hugging Face cache.

RapidOCR and Tesseract stay in ``scan_engines`` / ``scan_ocr`` for printed
labels and ID grids only — they are not used here.
"""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

TROCR_MODEL_ID = 'microsoft/trocr-base-handwritten'
LIGHTON_MODEL_ID = 'lightonai/LightOnOCR-2-1B'
# Below this, TrOCR is treated as a miss and LightOnOCR is tried.
TROCR_LOW_CONF = 0.45

_lock = threading.Lock()
_trocr = {'processor': None, 'model': None, 'error': '', 'tried': False}
_lighton = {'processor': None, 'model': None, 'error': '', 'tried': False}


def trocr_error() -> str:
    return _trocr['error'] or ''


def lightonocr_error() -> str:
    return _lighton['error'] or ''


def trocr_available() -> bool:
    return _trocr['model'] is not None


def lightonocr_available() -> bool:
    return _lighton['model'] is not None


def _trocr_device():
    try:
        import torch
        if torch.cuda.is_available():
            return 'cuda'
    except Exception:
        pass
    return 'cpu'


def _trocr_deps_ok() -> tuple[bool, str]:
    try:
        import torch  # noqa: F401
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel  # noqa: F401
        return True, ''
    except Exception as exc:
        return False, str(exc) or type(exc).__name__


def _lighton_deps_ok() -> tuple[bool, str]:
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
            # CPU only — no device_map, no quantization.
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
    """Report handwriting-engine load state without forcing a model download.

    Status polls stay cheap: packages are probed with imports only. Weights
    download on the first handwriting crop via ``from_pretrained``.
    """
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
    """Approximate confidence from token log-likelihoods when scores exist."""
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


def read_trocr(image) -> tuple[str, float]:
    """Return (text, confidence) from TrOCR. Empty on failure."""
    if image is None or not _load_trocr():
        return '', 0.0
    try:
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
    except Exception:
        logger.exception('TrOCR read failed')
        return '', 0.0


def read_lightonocr(image) -> tuple[str, float]:
    """Return (text, confidence) from LightOnOCR-2-1B on CPU. Empty on failure."""
    if image is None or not _load_lightonocr():
        return '', 0.0
    try:
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
        # LightOnOCR does not expose a calibrated confidence; treat a clean
        # non-empty reading as usable.
        return text, 0.7
    except Exception:
        logger.exception('LightOnOCR read failed')
        return '', 0.0


def read_handwriting(image) -> tuple[str, float, str]:
    """Primary TrOCR, then LightOnOCR fallback. Returns (text, conf, engine_name)."""
    text, conf = read_trocr(image)
    if text and conf >= TROCR_LOW_CONF:
        return text, conf, 'trocr'
    # Empty or low-confidence TrOCR → LightOnOCR fallback.
    light_text, light_conf = read_lightonocr(image)
    if light_text:
        return light_text, light_conf, 'lightonocr'
    if text:
        return text, conf, 'trocr'
    return '', 0.0, 'none'
