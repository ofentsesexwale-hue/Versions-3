"""TrOCR handwriting engine for Scan Intake.

RapidOCR and Tesseract are printed-text engines. On the handwritten fields of
the OVC forms they misread letters no matter how clean the iPhone JPEG is.
Microsoft's trocr-base-handwritten model is trained on real cursive, so it
replaces them on the handwrite path while RapidOCR/Tesseract keep the printed
labels and the 13-digit ID grids.

The model (~1.3 GB safetensors) downloads from Hugging Face on first run and
is then cached under the HF home directory. First scan after install is slow;
every scan after that is normal speed.
"""
from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)

_MODEL_ID = 'microsoft/trocr-base-handwritten'
_processor = None
_model = None
_device = None
_load_error = ''
_loading = False
_lock = threading.Lock()


def _env_flag(name, default='1'):
    return os.environ.get(name, default).strip().lower() not in ('0', 'false', 'no', 'off')


def trocr_enabled():
    return _env_flag('SCAN_TROCR', '1')


def _pick_device():
    try:
        import torch
        if torch.cuda.is_available():
            return torch.device('cuda')
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return torch.device('mps')
    except Exception:
        pass
    return None


def _load():
    """Lazy-load processor + model once. Safe to call from many threads."""
    global _processor, _model, _device, _load_error, _loading
    if _processor is not None and _model is not None:
        return True
    if _load_error:
        return False
    with _lock:
        if _processor is not None and _model is not None:
            return True
        if _load_error:
            return False
        if _loading:
            return False
        _loading = True
        try:
            import torch
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel

            _device = _pick_device()
            logger.info('Loading TrOCR (%s) on %s — first run downloads ~1.3 GB', _MODEL_ID, _device or 'cpu')
            _processor = TrOCRProcessor.from_pretrained(_MODEL_ID)
            kwargs = {'use_safetensors': True}
            if _device is not None:
                kwargs['device_map'] = { '': _device }
            _model = VisionEncoderDecoderModel.from_pretrained(_MODEL_ID, **kwargs)
            _model.eval()
            # Decoder start token must match the processor or generation drifts.
            _model.config.decoder_start_token_id = _processor.tokenizer.cls_token_id
            _model.config.pad_token_id = _processor.tokenizer.pad_token_id
            _model.config.vocab_size = _model.config.decoder.vocab_size
            _load_error = ''
            logger.info('TrOCR ready')
            return True
        except Exception as exc:
            _load_error = str(exc) or type(exc).__name__
            logger.exception('TrOCR failed to load')
            _processor = None
            _model = None
            return False
        finally:
            _loading = False


def trocr_status():
    """Cheap status for the engine panel — does not trigger a download."""
    if not trocr_enabled():
        return {'available': False, 'ready': False, 'error': 'disabled via SCAN_TROCR=0', 'device': None}
    ready = _processor is not None and _model is not None
    return {
        'available': True,
        'ready': ready,
        'loading': _loading,
        'error': _load_error,
        'device': str(_device) if _device is not None else 'cpu',
        'model': _MODEL_ID,
    }


def warmup():
    """Optional eager load so engine_status can report readiness."""
    if not trocr_enabled():
        return False
    return _load()


def read_line(image):
    """Return (text, confidence, engine_name) for one handwriting crop.

    Confidence is a heuristic: TrOCR has no per-character score, so we reward
    longer alphabetic runs and penalise anything the smash/label filters would
    reject. Empty string on failure so callers fall back to RapidOCR.
    """
    if image is None or not trocr_enabled():
        return '', 0.0, 'none'
    if not _load():
        return '', 0.0, 'none'
    try:
        import torch
        from PIL import ImageOps

        rgb = ImageOps.exif_transpose(image).convert('RGB')
        pixel_values = _processor(images=rgb, return_tensors='pt').pixel_values
        if _device is not None:
            pixel_values = pixel_values.to(_device)
        with torch.inference_mode():
            generated = _model.generate(
                pixel_values,
                max_new_tokens=64,
                num_beams=4,
                early_stopping=True,
            )
        text = _processor.batch_decode(generated, skip_special_tokens=True)[0]
        text = ' '.join((text or '').split())
        if not text:
            return '', 0.0, 'trocr'
        from .scan_text import _looks_like_smash
        from .form_labels import looks_like_form_label
        if looks_like_form_label(text) or _looks_like_smash(text):
            return '', 0.0, 'trocr'
        letters = sum(1 for ch in text if ch.isalpha())
        conf = min(0.92, 0.45 + 0.04 * letters)
        return text, conf, 'trocr'
    except Exception as exc:
        logger.exception('TrOCR read_line failed')
        return '', 0.0, 'none'
