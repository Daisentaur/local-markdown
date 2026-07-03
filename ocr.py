#!/usr/bin/env python3
"""
OCR pre-processing for MarkItDown Web.

markitdown extracts *embedded* text but does no character recognition, so
scanned PDFs and photos of text come back empty. This module fills that gap
using two mature, CPU-friendly open-source tools:

  * ocrmypdf  — adds a real text layer to scanned/image-only PDF pages
                (deskew, auto-rotate, language detection under the hood).
  * tesseract — recognises text in standalone image files.

Both are invoked as external CLIs, so nothing here depends on the app's
virtualenv. If either binary is missing, OCR silently no-ops and the caller
falls back to markitdown's normal (text-only) behaviour.

Handwriting note: Tesseract is built for printed/typed text. Handwriting is
recognised poorly or not at all — that needs a vision model and is out of
scope for this CPU-only layer (see README).
"""

import os
import shutil
import subprocess

# Image formats we route through Tesseract directly.
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif"}

# Config (read once at import; overridable via environment).
OCR_ENABLED = os.environ.get("OCR_ENABLED", "1").lower() not in ("0", "false", "no", "")
OCR_LANGUAGE = os.environ.get("OCR_LANGUAGE", "eng")
# A PDF whose markitdown text is shorter than this (after stripping) is treated
# as image-only/scanned and sent through OCR.
OCR_PDF_TEXT_THRESHOLD = int(os.environ.get("OCR_PDF_TEXT_THRESHOLD", "16"))
# Hard cap so a pathological file can't outlive gunicorn's request timeout.
OCR_TIMEOUT = int(os.environ.get("OCR_TIMEOUT", "240"))

_OCRMYPDF = shutil.which("ocrmypdf")
_TESSERACT = shutil.which("tesseract")


def ocr_available() -> bool:
    """True if at least one OCR engine is installed and OCR is enabled."""
    return OCR_ENABLED and bool(_OCRMYPDF or _TESSERACT)


def is_image_ext(ext: str) -> bool:
    return ext.lower() in IMAGE_EXTS


def pdf_needs_ocr(markitdown_text: str) -> bool:
    """A scanned PDF yields little/no embedded text — that's our OCR trigger."""
    return OCR_ENABLED and bool(_OCRMYPDF) and len((markitdown_text or "").strip()) < OCR_PDF_TEXT_THRESHOLD


def ocr_image(data: bytes) -> str:
    """Recognise text in an image. Returns recognised text ('' on failure)."""
    if not (OCR_ENABLED and _TESSERACT):
        return ""
    try:
        # tesseract reads the image from stdin and writes plain text to stdout.
        proc = subprocess.run(
            [_TESSERACT, "stdin", "stdout", "-l", OCR_LANGUAGE],
            input=data, capture_output=True, timeout=OCR_TIMEOUT,
        )
        return proc.stdout.decode("utf-8", "replace").strip()
    except Exception:
        return ""


def ocr_pdf(data: bytes) -> bytes:
    """Return a copy of the PDF with an OCR text layer added.

    Uses --skip-text so pages that already have text are left untouched and
    only image pages get OCR'd. On any failure the original bytes are returned
    so the caller can still fall back to markitdown.
    """
    if not (OCR_ENABLED and _OCRMYPDF):
        return data
    try:
        proc = subprocess.run(
            [_OCRMYPDF, "--skip-text", "--optimize", "0", "--quiet",
             "-l", OCR_LANGUAGE, "-", "-"],
            input=data, capture_output=True, timeout=OCR_TIMEOUT,
        )
        # ocrmypdf uses exit code 0 for success; anything else -> keep original.
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
    except Exception:
        pass
    return data
