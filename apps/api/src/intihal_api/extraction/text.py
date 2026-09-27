from __future__ import annotations

import codecs
from dataclasses import dataclass
from io import SEEK_SET
from typing import BinaryIO

from charset_normalizer import from_bytes

from intihal_api.extraction.normalization import normalize_extracted_text

MAX_ACCEPTABLE_CHAOS = 0.2
BOM_ENCODINGS = (
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_BE, "utf-16"),
    (codecs.BOM_UTF16_LE, "utf-16"),
)


@dataclass(frozen=True, slots=True)
class ExtractedTextFile:
    """Decoded plain text plus the encoding selected by the safe decoder."""

    text: str
    encoding: str
    page_number: None = None


class TextExtractionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class EmptyTextFileError(TextExtractionError):
    def __init__(self) -> None:
        super().__init__("no_extractable_text", "Metin dosyası boş.")


class UnknownTextEncodingError(TextExtractionError):
    def __init__(self) -> None:
        super().__init__(
            "unknown_text_encoding",
            "Metin dosyasının karakter kodlaması güvenle belirlenemedi.",
        )


class UnsafeTextContentError(TextExtractionError):
    def __init__(self) -> None:
        super().__init__(
            "unsafe_text_content",
            "Dosyada düz metin içinde kabul edilmeyen kontrol karakterleri bulundu.",
        )


def extract_text_file(stream: BinaryIO) -> ExtractedTextFile:
    """Decode and normalize a text stream, then rewind it."""

    stream.seek(0, SEEK_SET)
    try:
        content = stream.read()
        if not content:
            raise EmptyTextFileError

        text, encoding = _decode_text(content)
        text = normalize_extracted_text(text)
        if not text:
            raise EmptyTextFileError
        return ExtractedTextFile(text=text, encoding=encoding)
    finally:
        stream.seek(0, SEEK_SET)


def _decode_text(content: bytes) -> tuple[str, str]:
    for signature, encoding in BOM_ENCODINGS:
        if content.startswith(signature):
            try:
                return content.decode(encoding, errors="strict"), encoding
            except UnicodeDecodeError as error:
                raise UnknownTextEncodingError from error

    try:
        return content.decode("utf-8", errors="strict"), "utf-8"
    except UnicodeDecodeError:
        pass

    match = from_bytes(content).best()
    if match is None or match.chaos > MAX_ACCEPTABLE_CHAOS:
        raise UnknownTextEncodingError

    # The application primarily receives Turkish academic documents. Windows-1254
    # is a strict single-byte superset for their common legacy text characters.
    try:
        return content.decode("cp1254", errors="strict"), "windows-1254"
    except UnicodeDecodeError as error:
        raise UnknownTextEncodingError from error
