"""OCR extraction for WhatsApp screenshot/image messages.

A separate, provider-agnostic concern from extraction/llm_client.py's text-based
criteria extraction - OCR must work regardless of which LLM_PROVIDER is configured,
since it only ever produces a plain text string that feeds into the same existing
extraction pipeline downstream.
"""

from __future__ import annotations

import io
import threading

import numpy as np
from PIL import Image

_reader = None
_reader_lock = threading.Lock()


def _get_reader():
    """Lazily construct and cache the EasyOCR Reader (expensive: loads model weights)."""
    global _reader
    if _reader is None:
        with _reader_lock:
            if _reader is None:
                import easyocr
                _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def extract_text_from_image(image_bytes: bytes) -> str:
    """Run OCR on raw image bytes and return the extracted text, in reading order.

    Returns "" on any decode/OCR failure rather than raising, so a bad or
    unreadable image degrades to "no OCR text" instead of blocking the whole
    message (callers combine this with any caption text, which may still be
    usable on its own).
    """
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return ""

    try:
        results = _get_reader().readtext(np.array(image))
        return "\n".join(text for (_bbox, text, _conf) in results).strip()
    except Exception:
        return ""
