from __future__ import annotations

from dataclasses import dataclass
from io import SEEK_SET
from typing import BinaryIO

import pymupdf

from intihal_api.extraction.normalization import normalize_extracted_text


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
        super().__init__(
            "invalid_pdf",
            "PDF açılamadı. Dosya bozuk veya eksik olabilir; dosyayı yeniden kaydedip "
            "tekrar yükleyin.",
        )


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
            "PDF'de analiz edilebilecek metin bulunamadı. Metin içeren başka bir dosya yükleyin.",
        )


class OcrRequiredError(PdfExtractionError):
    def __init__(self) -> None:
        super().__init__(
            "ocr_required",
            "Bu PDF taranmış sayfa görüntülerinden oluşuyor; seçilebilir metin bulunamadı. "
            "Dosyaya OCR uygulayıp metni aranabilir hâle getirdikten sonra yeniden yükleyin.",
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
            requires_ocr = not any(page.text for page in pages) and _contains_page_images(document)
        finally:
            document.close()

        if not any(page.text for page in pages):
            if requires_ocr:
                raise OcrRequiredError
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
        raw_text = document.load_page(page_index).get_text("text", sort=True)
        if not isinstance(raw_text, str):
            raise TypeError("PDF text extraction returned an unexpected value")
        text = normalize_extracted_text(raw_text)
    except (RuntimeError, TypeError, ValueError) as error:
        raise PdfPageExtractionError(page_number) from error
    return ExtractedPdfPage(page_number=page_number, text=text)


def _contains_page_images(document: pymupdf.Document) -> bool:
    return any(
        document.load_page(page_index).get_images() for page_index in range(document.page_count)
    )
