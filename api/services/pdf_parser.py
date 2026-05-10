import io
import re
import shutil
import subprocess
import tempfile
from typing import List, Tuple

from core.observability import get_logger

logger = get_logger("pdf_parser")


def parse_pdf(file_stream: io.BytesIO) -> Tuple[str, List[str]]:
    """Parse a PDF file and extract text.

    Tries multiple strategies in order:
      1. PyPDF2 (fast, works for text-based PDFs).
      2. pdftotext (poppler) — better extraction for some PDFs.
      3. OCR via pdf2image + pytesseract — fallback for scanned/image PDFs.

    Returns:
        (extracted_text, warnings)
    """
    warnings: List[str] = []
    content = file_stream.read()

    # --- Strategy 1: PyPDF2 ---
    try:
        text = _extract_with_pypdf2(io.BytesIO(content))
        if len(text.strip()) >= 500:
            return text, warnings
        if text.strip():
            warnings.append("PyPDF2 extracted limited text; trying fallback extractors")
        else:
            warnings.append("PyPDF2 produced no text; trying fallback extractors")
    except Exception as exc:
        warnings.append(f"PyPDF2 extraction failed: {exc}")

    # --- Strategy 2: pdftotext (poppler) ---
    try:
        text = _extract_with_pdftotext(content)
        if len(text.strip()) >= 500:
            warnings.append("Used pdftotext fallback for better extraction")
            return text, warnings
        if text.strip():
            warnings.append("pdftotext extracted limited text; may be scanned PDF")
        else:
            warnings.append("pdftotext produced no text; may be scanned PDF")
    except Exception as exc:
        warnings.append(f"pdftotext fallback failed: {exc}")

    # --- Strategy 3: OCR ---
    try:
        text = _extract_with_ocr(content)
        if text.strip():
            warnings.append("Used OCR (Tesseract) to extract text from scanned PDF")
            return text, warnings
        warnings.append("OCR produced no text")
    except Exception as exc:
        warnings.append(f"OCR fallback failed: {exc}")

    raise ValueError("No text extracted from PDF")


def _extract_with_pypdf2(file_stream: io.BytesIO) -> str:
    from PyPDF2 import PdfReader
    reader = PdfReader(file_stream)
    if len(reader.pages) == 0:
        raise ValueError("PDF has no pages")

    pages = []
    for i, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text)
            else:
                logger.debug("Page %d produced no text (PyPDF2)", i)
        except Exception as exc:
            logger.debug("Failed to extract page %d with PyPDF2: %s", i, exc)

    return "\n".join(pages)


def _extract_with_pdftotext(content: bytes) -> str:
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext not found in PATH")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as pdf_tmp:
        pdf_tmp.write(content)
        pdf_path = pdf_tmp.name

    with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as txt_tmp:
        txt_path = txt_tmp.name

    try:
        result = subprocess.run(
            ["pdftotext", "-layout", pdf_path, txt_path],
            capture_output=True,
            text=True,
            check=True,
        )
        with open(txt_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    finally:
        import os
        os.unlink(pdf_path)
        os.unlink(txt_path)


def _extract_with_ocr(content: bytes) -> str:
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
    except ImportError as exc:
        raise RuntimeError(
            "OCR dependencies missing. Install with: pip install pdf2image pytesseract"
        ) from exc

    logger.info("Starting OCR extraction (%d bytes)", len(content))
    # Use lower DPI and parallel rendering for speed. 150 dpi is usually
    # sufficient for patent text while being ~2× faster than 200 dpi.
    images = convert_from_bytes(
        content,
        dpi=150,
        thread_count=4,
        grayscale=True,
        fmt="ppm",
    )
    pages = []
    for i, image in enumerate(images):
        try:
            page_text = pytesseract.image_to_string(
                image,
                config="--psm 6",  # Assume a single uniform block of text
            )
            if page_text:
                pages.append(page_text)
            else:
                logger.debug("Page %d produced no text (OCR)", i)
        except Exception as exc:
            logger.warning("OCR failed on page %d: %s", i, exc)

    return "\n".join(pages)
