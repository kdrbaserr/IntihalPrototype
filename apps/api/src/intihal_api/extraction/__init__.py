"""Document text extraction primitives."""

from intihal_api.extraction.docx import (
    DocxExtractionError,
    ExtractedDocxText,
    InvalidDocxError,
    NoExtractableDocxTextError,
    extract_docx_text,
)
from intihal_api.extraction.pdf import (
    EmptyPdfError,
    EncryptedPdfError,
    ExtractedPdfPage,
    InvalidPdfError,
    NoExtractableTextError,
    PdfExtractionError,
    PdfPageExtractionError,
    extract_pdf_pages,
)
from intihal_api.extraction.text import (
    EmptyTextFileError,
    ExtractedTextFile,
    TextExtractionError,
    UnknownTextEncodingError,
    UnsafeTextContentError,
    extract_text_file,
)

__all__ = [
    "DocxExtractionError",
    "EmptyPdfError",
    "EmptyTextFileError",
    "EncryptedPdfError",
    "ExtractedDocxText",
    "ExtractedPdfPage",
    "ExtractedTextFile",
    "InvalidPdfError",
    "InvalidDocxError",
    "NoExtractableDocxTextError",
    "NoExtractableTextError",
    "PdfExtractionError",
    "PdfPageExtractionError",
    "TextExtractionError",
    "UnknownTextEncodingError",
    "UnsafeTextContentError",
    "extract_docx_text",
    "extract_pdf_pages",
    "extract_text_file",
]
