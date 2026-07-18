"""PDF text extraction (PyMuPDF)."""

from __future__ import annotations

import fitz  # PyMuPDF


def extract_text_from_pdf(data: bytes) -> str:
    with fitz.open(stream=data, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)
