from dataclasses import asdict
from io import BytesIO

import pymupdf
import pytest
from docx import Document

from intihal_api.extraction import (
    create_text_chunks,
    extract_and_chunk_document,
    extract_pdf_pages,
    extract_text_file,
)
from intihal_api.uploads.validation import DocumentFormat


def make_text_pdf(*pages: str) -> bytes:
    document = pymupdf.open()
    try:
        for content in pages:
            page = document.new_page()
            page.insert_text((72, 72), content)
        return document.tobytes()
    finally:
        document.close()


def make_docx(content: str) -> bytes:
    document = Document()
    document.add_paragraph(content)
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


@pytest.mark.parametrize(
    ("document_format", "content"),
    [
        (DocumentFormat.PDF, make_text_pdf("Ilk cumle. Ikinci cumle.")),
        (DocumentFormat.DOCX, make_docx("İlk cümle. İkinci cümle.")),
        (DocumentFormat.TXT, "İlk cümle.\r\n İkinci   cümle.".encode()),
    ],
    ids=("pdf", "docx", "txt"),
)
def test_canonical_pipeline_extracts_normalizes_and_chunks_supported_documents(
    document_format: DocumentFormat,
    content: bytes,
) -> None:
    stream = BytesIO(content)

    result = extract_and_chunk_document(stream, document_format)

    assert result.chunks
    assert [chunk.chunk_index for chunk in result.chunks] == list(range(len(result.chunks)))
    assert all(
        result.text[chunk.char_start : chunk.char_end] == chunk.content for chunk in result.chunks
    )
    assert stream.tell() == 0


def test_pipeline_keeps_the_existing_extraction_and_chunk_contract() -> None:
    content = "Türkçe kaynak. İkinci cümle.".encode()

    expected = create_text_chunks((extract_text_file(BytesIO(content)),))
    actual = extract_and_chunk_document(BytesIO(content), DocumentFormat.TXT)

    assert asdict(actual) == asdict(expected)


def test_pdf_pipeline_keeps_page_boundaries_from_the_existing_contract() -> None:
    content = make_text_pdf("Birinci sayfa.", "Ikinci sayfa.")

    expected = create_text_chunks(extract_pdf_pages(BytesIO(content)))
    actual = extract_and_chunk_document(BytesIO(content), DocumentFormat.PDF)

    assert asdict(actual) == asdict(expected)
    assert [chunk.page_number for chunk in actual.chunks] == [1, 2]
