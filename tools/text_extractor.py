"""
Text Extractor Tool
Purpose: Extract plain text from uploaded resume/cover letter files.
Supports: PDF, DOCX, DOC, TXT
"""

import io
from typing import Optional


def extract_text(file_bytes: bytes, filename: str) -> str:
    """
    Extract plain text from file bytes.
    Routes by file extension first, then falls back to magic-byte detection.

    Args:
        file_bytes: Raw bytes of the uploaded file
        filename: Original filename (used to determine format)

    Returns:
        Extracted plain text string
    """
    name_lower = (filename or "").lower()

    if name_lower.endswith(".pdf") or _is_pdf(file_bytes):
        return _extract_pdf(file_bytes)
    elif name_lower.endswith(".docx") or name_lower.endswith(".doc") or _is_docx(file_bytes):
        return _extract_docx(file_bytes)
    else:
        return file_bytes.decode("utf-8", errors="replace")


def _is_pdf(file_bytes: bytes) -> bool:
    """Detect PDF by magic bytes (%PDF header)."""
    return file_bytes[:4] == b"%PDF"


def _is_docx(file_bytes: bytes) -> bool:
    """Detect DOCX/ZIP by magic bytes (PK header)."""
    return file_bytes[:2] == b"PK"


def _extract_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF bytes using pdfminer.six."""
    from pdfminer.high_level import extract_text_to_fp
    from pdfminer.layout import LAParams

    output = io.StringIO()
    extract_text_to_fp(
        io.BytesIO(file_bytes),
        output,
        laparams=LAParams(),
        output_type="text",
        codec="utf-8",
    )
    return output.getvalue().strip()


def _extract_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX bytes using python-docx."""
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return "\n".join(paragraphs)
