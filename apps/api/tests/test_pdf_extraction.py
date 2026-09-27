from io import BytesIO

import pymupdf
import pytest
from pypdf import PdfWriter

from file_samples import make_pdf_bytes
from intihal_api.extraction import (
    EmptyPdfError,
    EncryptedPdfError,
    InvalidPdfError,
    NoExtractableTextError,
    extract_pdf_pages,
)


def make_text_pdf(*page_texts: str) -> bytes:
    document = pymupdf.open()
    try:
        for text in page_texts:
            page = document.new_page()
            page.insert_text((72, 72), text)
        return document.tobytes()
    finally:
        document.close()


def test_extracts_text_with_one_based_page_numbers() -> None:
    stream = BytesIO(make_text_pdf("First   page", "Second page"))

    pages = extract_pdf_pages(stream)

    assert [(page.page_number, page.text) for page in pages] == [
        (1, "First page"),
        (2, "Second page"),
    ]
    assert stream.tell() == 0


def test_keeps_blank_pages_when_another_page_contains_text() -> None:
    pages = extract_pdf_pages(BytesIO(make_text_pdf("", "Readable text")))

    assert [(page.page_number, page.text) for page in pages] == [
        (1, ""),
        (2, "Readable text"),
    ]


def test_rejects_pdf_without_extractable_text() -> None:
    with pytest.raises(NoExtractableTextError) as captured_error:
        extract_pdf_pages(BytesIO(make_pdf_bytes()))

    assert captured_error.value.code == "no_extractable_text"


def test_rejects_pdf_without_pages() -> None:
    stream = BytesIO()
    PdfWriter().write(stream)

    with pytest.raises(EmptyPdfError) as captured_error:
        extract_pdf_pages(stream)

    assert captured_error.value.code == "empty_pdf"
    assert stream.tell() == 0


def test_rejects_encrypted_pdf_and_rewinds_stream() -> None:
    stream = BytesIO(make_pdf_bytes(password="secret"))

    with pytest.raises(EncryptedPdfError) as captured_error:
        extract_pdf_pages(stream)

    assert captured_error.value.code == "encrypted_pdf"
    assert stream.tell() == 0


@pytest.mark.parametrize("content", [b"", b"not a pdf", b"%PDF-1.7\ntruncated"])
def test_rejects_invalid_pdf(content: bytes) -> None:
    with pytest.raises(InvalidPdfError) as captured_error:
        extract_pdf_pages(BytesIO(content))

    assert captured_error.value.code == "invalid_pdf"
