import codecs
from io import BytesIO

import pytest

from intihal_api.extraction import (
    EmptyTextFileError,
    UnknownTextEncodingError,
    UnsafeTextContentError,
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
    with pytest.raises(EmptyTextFileError):
        extract_text_file(BytesIO(content))


@pytest.mark.parametrize(
    "content",
    [
        b"safe prefix\x00binary suffix",
        "visible\u202etext".encode(),
        codecs.BOM_UTF16_LE + b"\x00",
    ],
)
def test_rejects_unsafe_or_malformed_text(content: bytes) -> None:
    with pytest.raises((UnsafeTextContentError, UnknownTextEncodingError)):
        extract_text_file(BytesIO(content))


def test_rejects_binary_data_when_encoding_is_not_reliable() -> None:
    with pytest.raises(UnknownTextEncodingError) as captured_error:
        extract_text_file(BytesIO(bytes(range(1, 256))))

    assert captured_error.value.code == "unknown_text_encoding"
