"""Document text extraction primitives."""

from intihal_api.extraction.chunking import ChunkedText, TextChunk, create_text_chunks
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
    OcrRequiredError,
    PdfExtractionError,
    PdfPageExtractionError,
    extract_pdf_pages,
)
from intihal_api.extraction.pipeline import extract_and_chunk_document
from intihal_api.extraction.text import (
    EmptyTextFileError,
    ExtractedTextFile,
    TextExtractionError,
    UnknownTextEncodingError,
    UnsafeTextContentError,
    extract_text_file,
)

__all__ = [
    "ChunkedText",
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
    "OcrRequiredError",
    "PdfExtractionError",
    "PdfPageExtractionError",
    "TextExtractionError",
    "TextChunk",
    "UnknownTextEncodingError",
    "UnsafeTextContentError",
    "create_text_chunks",
    "extract_docx_text",
    "extract_and_chunk_document",
    "extract_pdf_pages",
    "extract_text_file",
]
