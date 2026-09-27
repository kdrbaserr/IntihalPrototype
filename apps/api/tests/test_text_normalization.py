from intihal_api.extraction.normalization import normalize_extracted_text


def test_normalizes_decomposed_turkish_letters_without_ascii_transliteration() -> None:
    assert normalize_extracted_text("I\u0307stanbul, Tu\u0308rkc\u0327e") == "İstanbul, Türkçe"


def test_preserves_paragraph_boundaries_while_cleaning_horizontal_space() -> None:
    text = "  İlk\t\t satır  \r\n\r\n  İkinci\u00a0\u00a0satır  "

    assert normalize_extracted_text(text) == "İlk satır\n\nİkinci satır"
