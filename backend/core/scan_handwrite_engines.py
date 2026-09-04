"""Handwriting OCR engines for Scan Intake.

TrOCR (microsoft/trocr-base-handwritten) is the primary reader for every
handwriting crop. Qwen2.5-VL-7B-Instruct is the fallback when TrOCR returns
empty or low-confidence text. Both download automatically on first use via
``from_pretrained`` and cache under the local Hugging Face cache.

RapidOCR and Tesseract stay in ``scan_engines`` / ``scan_ocr`` for printed
labels and ID grids only — they are not used here.
"""
from __future__ import annotations

import base64
import io
import logging
import threading

logger = logging.getLogger(__name__)

TROCR_MODEL_ID = 'microsoft/trocr-base-handwritten'
QWEN_MODEL_ID = 'Qwen/Qwen2.5-VL-7B-Instruct'
# Below this, TrOCR is treated as a miss and Qwen is tried.
TROCR_LOW_CONF = 0.45

_lock = threading.Lock()
_trocr = {'processor': None, 'model': None, 'error': '', 'tried': False}
_qwen = {'processor': None, 'model': None, 'error': '', 'tried': False}


def trocr_error() -> str:
    return _trocr['error'] or ''


def qwen_error() -> str:
    return _qwen['error'] or ''


def trocr_available() -> bool:
    return _trocr['model'] is not None


def qwen_available() -> bool:
    return _qwen['model'] is not None


def _device():
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


def _qwen_deps_ok() -> tuple[bool, str]:
    try:
        import torch
        import bitsandbytes  # noqa: F401
        from transformers import AutoProcessor, BitsAndBytesConfig, Qwen2_5_VLForConditionalGeneration  # noqa: F401
        from qwen_vl_utils import process_vision_info  # noqa: F401
        if not torch.cuda.is_available():
            return False, 'Qwen2.5-VL needs a CUDA GPU for 4-bit load on this PC'
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
            device = _device()
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


def _load_qwen():
    """Lazy-load Qwen2.5-VL in 4-bit when CUDA + bitsandbytes allow it."""
    with _lock:
        if _qwen['model'] is not None or _qwen['tried']:
            return _qwen['model'] is not None
        _qwen['tried'] = True
        try:
            import torch
            from transformers import AutoProcessor, BitsAndBytesConfig, Qwen2_5_VLForConditionalGeneration

            if not torch.cuda.is_available():
                _qwen['error'] = 'Qwen2.5-VL needs a CUDA GPU for 4-bit load on this PC'
                return False

            quantization = BitsAndBytesConfig(load_in_4bit=True)
            processor = AutoProcessor.from_pretrained(QWEN_MODEL_ID)
            model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                QWEN_MODEL_ID,
                quantization_config=quantization,
                device_map='auto',
            )
            model.eval()
            _qwen['processor'] = processor
            _qwen['model'] = model
            _qwen['error'] = ''
            logger.info('Qwen2.5-VL loaded in 4-bit from %s', QWEN_MODEL_ID)
            return True
        except Exception as exc:
            _qwen['error'] = str(exc) or type(exc).__name__
            logger.exception('Qwen2.5-VL failed to load')
            return False


def warmup_trocr() -> bool:
    return _load_trocr()


def warmup_qwen() -> bool:
    return _load_qwen()


def engine_status() -> dict:
    """Report handwriting-engine load state without forcing a model download.

    Status polls stay cheap: packages are probed with imports only. Weights
    download on the first handwriting crop via ``from_pretrained``.
    """
    trocr_pkgs, trocr_pkg_err = _trocr_deps_ok()
    qwen_pkgs, qwen_pkg_err = _qwen_deps_ok()
    return {
        'trocr': trocr_available(),
        'trocr_ready': trocr_pkgs,
        'trocr_error': trocr_error() or ('' if trocr_available() or trocr_pkgs else trocr_pkg_err),
        'qwen': qwen_available(),
        'qwen_ready': qwen_pkgs,
        'qwen_error': qwen_error() or ('' if qwen_available() or qwen_pkgs else qwen_pkg_err),
    }


def _confidence_from_generate(out) -> float:
    """Approximate confidence from token log-likelihoods when scores exist."""
    try:
        import torch
        scores = getattr(out, 'scores', None) or []
        sequences = getattr(out, 'sequences', None)
        if not scores or sequences is None:
            return 0.55
        # Skip prompt tokens; for encoder-decoder TrOCR the sequence is new tokens.
        token_ids = sequences[0]
        # Align scores with generated tokens (one score tensor per new token).
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


def read_qwen(image) -> tuple[str, float]:
    """Return (text, confidence) from Qwen2.5-VL. Empty on failure."""
    if image is None or not _load_qwen():
        return '', 0.0
    try:
        import torch
        from qwen_vl_utils import process_vision_info

        processor = _qwen['processor']
        model = _qwen['model']
        buf = io.BytesIO()
        image.convert('RGB').save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode('ascii')
        data_url = f'data:image/png;base64,{b64}'
        messages = [{
            'role': 'user',
            'content': [
                {'type': 'image', 'image': data_url},
                {
                    'type': 'text',
                    'text': (
                        'Read the handwritten text in this form field crop exactly. '
                        'Return only the written words or digits, with no explanation.'
                    ),
                },
            ],
        }]
        prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(
            text=[prompt],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors='pt',
        )
        device = next(model.parameters()).device
        inputs = inputs.to(device)
        with torch.no_grad():
            generated = model.generate(**inputs, max_new_tokens=64)
        trimmed = generated[:, inputs.input_ids.shape[1]:]
        text = processor.batch_decode(
            trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False,
        )[0]
        text = (text or '').strip()
        if not text:
            return '', 0.0
        # VL chat models do not expose a calibrated confidence; treat a clean
        # non-empty reading as usable.
        return text, 0.7
    except Exception:
        logger.exception('Qwen2.5-VL read failed')
        return '', 0.0


def read_handwriting(image) -> tuple[str, float, str]:
    """Primary TrOCR, then Qwen fallback. Returns (text, conf, engine_name)."""
    text, conf = read_trocr(image)
    if text and conf >= TROCR_LOW_CONF:
        return text, conf, 'trocr'
    # Empty or low-confidence TrOCR → Qwen fallback.
    q_text, q_conf = read_qwen(image)
    if q_text:
        return q_text, q_conf, 'qwen'
    if text:
        return text, conf, 'trocr'
    return '', 0.0, 'none'
