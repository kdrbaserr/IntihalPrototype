from __future__ import annotations

from dataclasses import dataclass
from io import SEEK_SET
from typing import BinaryIO

import pymupdf


@dataclass(frozen=True, slots=True)
class ExtractedPdfPage:
    """Plain text extracted from one PDF page."""

    page_number: int
    text: str


class PdfExtractionError(RuntimeError):
    """Base error with a stable code suitable for logs, jobs, and API responses."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class InvalidPdfError(PdfExtractionError):
    def __init__(self) -> None:
        super().__init__("invalid_pdf", "PDF açılamadı veya dosya yapısı bozuk.")


class EncryptedPdfError(PdfExtractionError):
    def __init__(self) -> None:
        super().__init__(
            "encrypted_pdf",
            "Şifreli PDF dosyalarından metin çıkarılamaz.",
        )


class EmptyPdfError(PdfExtractionError):
    def __init__(self) -> None:
        super().__init__("empty_pdf", "PDF içinde sayfa bulunamadı.")


class NoExtractableTextError(PdfExtractionError):
    def __init__(self) -> None:
        super().__init__(
            "no_extractable_text",
            "PDF içinde çıkarılabilir metin bulunamadı; belge OCR gerektiriyor olabilir.",
        )


class PdfPageExtractionError(PdfExtractionError):
    def __init__(self, page_number: int) -> None:
        self.page_number = page_number
        super().__init__(
            "page_extraction_failed",
            f"PDF'in {page_number}. sayfasındaki metin okunamadı.",
        )


def extract_pdf_pages(stream: BinaryIO) -> tuple[ExtractedPdfPage, ...]:
    """Extract plain text page by page and rewind the input stream afterwards."""

    stream.seek(0, SEEK_SET)
    try:
        pdf_bytes = stream.read()
        document = _open_pdf(pdf_bytes)
        try:
            if document.needs_pass:
                raise EncryptedPdfError
            if document.page_count == 0:
                raise EmptyPdfError

            pages = tuple(
                _extract_page(document, page_index) for page_index in range(document.page_count)
            )
        finally:
            document.close()

        if not any(page.text for page in pages):
            raise NoExtractableTextError
        return pages
    finally:
        stream.seek(0, SEEK_SET)


def _open_pdf(pdf_bytes: bytes) -> pymupdf.Document:
    try:
        document = pymupdf.open(stream=pdf_bytes)
    except (RuntimeError, TypeError, ValueError) as error:
        raise InvalidPdfError from error

    if not document.is_pdf:
        document.close()
        raise InvalidPdfError
    return document


def _extract_page(document: pymupdf.Document, page_index: int) -> ExtractedPdfPage:
    page_number = page_index + 1
    try:
        text = document.load_page(page_index).get_text("text", sort=True).strip()
    except (RuntimeError, TypeError, ValueError) as error:
        raise PdfPageExtractionError(page_number) from error
    return ExtractedPdfPage(page_number=page_number, text=text)
