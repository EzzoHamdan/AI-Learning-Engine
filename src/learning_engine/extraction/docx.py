"""Word document text extraction (python-docx)."""

from __future__ import annotations

import io

import docx


def extract_text_from_docx(data: bytes) -> str:
    doc = docx.Document(io.BytesIO(data))
    return "\n".join(para.text for para in doc.paragraphs)
