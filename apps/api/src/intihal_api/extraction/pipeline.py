from __future__ import annotations

from typing import BinaryIO

from intihal_api.extraction.chunking import ChunkedText, create_text_chunks
from intihal_api.extraction.docx import extract_docx_text
from intihal_api.extraction.pdf import extract_pdf_pages
from intihal_api.extraction.text import extract_text_file
from intihal_api.uploads.validation import DocumentFormat


def extract_and_chunk_document(
    stream: BinaryIO,
    document_format: DocumentFormat,
) -> ChunkedText:
    """Run every supported document through the canonical extraction/chunk contract."""

    if document_format is DocumentFormat.PDF:
        parts = extract_pdf_pages(stream)
    elif document_format is DocumentFormat.DOCX:
        parts = (extract_docx_text(stream),)
    else:
        parts = (extract_text_file(stream),)

    return create_text_chunks(parts)
