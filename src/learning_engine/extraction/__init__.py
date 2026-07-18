"""Document text extraction: one dispatcher, one module per format.

Extractors take raw bytes (not file handles) so callers can cache on content —
the UI wraps extract_text in @st.cache_data keyed on the uploaded bytes.

This module must not import Streamlit (architecture rule R1).
"""

from __future__ import annotations

from learning_engine.extraction.docx import extract_text_from_docx
from learning_engine.extraction.pdf import extract_text_from_pdf
from learning_engine.extraction.pptx import extract_text_from_pptx

SUPPORTED_FORMATS = ("pdf", "docx", "pptx")


class ExtractionError(Exception):
    """Base class for extraction failures."""


class UnsupportedFormatError(ExtractionError):
    """The file type has no extractor."""


class FileTooLargeError(ExtractionError):
    """The file exceeds the configured upload limit."""


_EXTRACTORS = {
    "pdf": extract_text_from_pdf,
    "docx": extract_text_from_docx,
    "pptx": extract_text_from_pptx,
}


def extract_text(data: bytes, file_type: str, *, max_mb: int | None = None) -> str:
    """Extract plain text from a document given its raw bytes and extension.

    Raises UnsupportedFormatError for unknown extensions, FileTooLargeError when
    `max_mb` is given and exceeded, and ExtractionError when the underlying
    parser fails.
    """
    kind = file_type.lower().lstrip(".")
    extractor = _EXTRACTORS.get(kind)
    if extractor is None:
        raise UnsupportedFormatError(
            f"Unsupported file format: {file_type!r} (supported: {', '.join(SUPPORTED_FORMATS)})"
        )

    if max_mb is not None and len(data) > max_mb * 1024 * 1024:
        size_mb = len(data) / (1024 * 1024)
        raise FileTooLargeError(f"File is {size_mb:.1f}MB, which exceeds the {max_mb}MB limit")

    try:
        return extractor(data)
    except Exception as exc:
        raise ExtractionError(f"Error reading {kind.upper()} file: {exc}") from exc
