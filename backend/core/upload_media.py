"""Supporting-document upload helpers (HEIC → JPEG). No OCR."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile


def _register_heif() -> bool:
    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
        return True
    except Exception:
        return False


def looks_like_heic(name: str, header: bytes = b'') -> bool:
    lower = (name or '').lower()
    if lower.endswith(('.heic', '.heif')):
        return True
    return len(header) > 12 and header[4:8] == b'ftyp' and header[8:12] in {
        b'heic', b'heif', b'mif1', b'msf1',
    }


def convert_heic_to_jpeg(uploaded) -> SimpleUploadedFile:
    """Convert an iPhone HEIC/HEIF upload to JPEG. Raises ValueError on failure."""
    if not _register_heif():
        raise ValueError(
            'This HEIC/HEIF photo cannot be converted on this PC. '
            'Install pillow-heif, or set the iPhone Camera to Most Compatible (JPEG).'
        )
    from PIL import Image

    name = getattr(uploaded, 'name', '') or 'photo.heic'
    raw = uploaded.read()
    if hasattr(uploaded, 'seek'):
        uploaded.seek(0)
    try:
        img = Image.open(BytesIO(raw))
        img.load()
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        elif img.mode == 'L':
            img = img.convert('RGB')
        out = BytesIO()
        img.save(out, format='JPEG', quality=92)
        data = out.getvalue()
    except Exception as exc:
        raise ValueError(
            'Could not convert this HEIC/HEIF photo to JPEG. '
            'Try exporting as JPEG on the phone, or set Camera → Formats → Most Compatible.'
        ) from exc
    jpeg_name = Path(name).with_suffix('.jpg').name
    return SimpleUploadedFile(jpeg_name, data, content_type='image/jpeg')
