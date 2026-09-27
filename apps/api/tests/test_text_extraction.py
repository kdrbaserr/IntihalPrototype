import codecs
from io import BytesIO

import pytest

from intihal_api.extraction import (
    EmptyTextFileError,
    UnknownTextEncodingError,
    extract_text_file,
)


def test_extracts_utf8_text_and_rewinds_stream() -> None:
    stream = BytesIO("Türkçe akademik metin".encode())

    extracted = extract_text_file(stream)

    assert extracted.text == "Türkçe akademik metin"
    assert extracted.encoding == "utf-8"
    assert extracted.page_number is None
    assert stream.tell() == 0


def test_detects_utf16_from_byte_order_mark() -> None:
    extracted = extract_text_file(BytesIO("Başlıklı metin".encode("utf-16")))

    assert extracted.text == "Başlıklı metin"
    assert extracted.encoding == "utf-16"


def test_detects_legacy_turkish_windows_encoding() -> None:
    content = (
        "Türkiye'de eğitim, öğretim ve bilimsel araştırma önemlidir. "
        "Öğrenciler özgün düşünceler geliştirir. "
    ) * 5

    extracted = extract_text_file(BytesIO(content.encode("cp1254")))

    assert extracted.text == content.strip()
    assert extracted.encoding == "windows-1254"


@pytest.mark.parametrize("content", [b"", b" \r\n\t "])
def test_rejects_empty_or_whitespace_only_text(content: bytes) -> None:
    with pytest.raises(EmptyTextFileError) as captured_error:
        extract_text_file(BytesIO(content))

    assert "Metin içeren" in str(captured_error.value)


def test_cleans_controls_and_repeated_spaces_while_preserving_turkish() -> None:
    content = "  Türkçe\x00\t  içerik\u202e  korunur.  \r\n İkinci   satır. "

    extracted = extract_text_file(BytesIO(content.encode()))

    assert extracted.text == "Türkçe içerik korunur.\nİkinci satır."


def test_rejects_malformed_bom_text() -> None:
    with pytest.raises(UnknownTextEncodingError):
        extract_text_file(BytesIO(codecs.BOM_UTF16_LE + b"\x00"))


def test_rejects_binary_data_when_encoding_is_not_reliable() -> None:
    with pytest.raises(UnknownTextEncodingError) as captured_error:
        extract_text_file(BytesIO(bytes(range(1, 256))))

    assert captured_error.value.code == "unknown_text_encoding"
    assert "UTF-8" in str(captured_error.value)
