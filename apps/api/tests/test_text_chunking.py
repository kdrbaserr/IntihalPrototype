from intihal_api.extraction import (
    ExtractedDocxText,
    ExtractedPdfPage,
    ExtractedTextFile,
    create_text_chunks,
)


def test_creates_sentence_chunks_with_exact_offsets_and_page_numbers() -> None:
    result = create_text_chunks(
        (
            ExtractedPdfPage(1, "İlk cümle. İkinci cümle!"),
            ExtractedPdfPage(2, "Yeni paragraf\nSoru var mı? Evet."),
        )
    )

    assert [chunk.content for chunk in result.chunks] == [
        "İlk cümle.",
        "İkinci cümle!",
        "Yeni paragraf",
        "Soru var mı?",
        "Evet.",
    ]
    assert [chunk.page_number for chunk in result.chunks] == [1, 1, 2, 2, 2]
    assert [chunk.chunk_index for chunk in result.chunks] == list(range(5))
    for chunk in result.chunks:
        assert result.text[chunk.char_start : chunk.char_end] == chunk.content


def test_keeps_global_offsets_when_a_pdf_contains_an_empty_page() -> None:
    result = create_text_chunks(
        (
            ExtractedPdfPage(1, ""),
            ExtractedPdfPage(2, "İkinci sayfa."),
        )
    )

    assert result.text == "\nİkinci sayfa."
    assert result.chunks[0].char_start == 1
    assert result.chunks[0].char_end == len(result.text)
    assert result.chunks[0].page_number == 2


def test_docx_and_text_chunks_do_not_invent_page_numbers() -> None:
    docx_result = create_text_chunks((ExtractedDocxText("DOCX paragrafı."),))
    text_result = create_text_chunks((ExtractedTextFile("TXT paragrafı.", "utf-8"),))

    assert docx_result.chunks[0].page_number is None
    assert text_result.chunks[0].page_number is None


def test_counts_tokens_and_hashes_the_exact_chunk_content() -> None:
    first = create_text_chunks((ExtractedTextFile("Türkçe bir cümle.", "utf-8"),)).chunks[0]
    second = create_text_chunks((ExtractedTextFile("Türkçe bir cümle.", "utf-8"),)).chunks[0]

    assert first.token_count == 3
    assert len(first.content_sha256) == 64
    assert first.content_sha256 == second.content_sha256


def test_common_turkish_abbreviation_does_not_end_a_sentence() -> None:
    result = create_text_chunks((ExtractedTextFile("Dr. Ayşe geldi. Sonra ayrıldı.", "utf-8"),))

    assert [chunk.content for chunk in result.chunks] == [
        "Dr. Ayşe geldi.",
        "Sonra ayrıldı.",
    ]
