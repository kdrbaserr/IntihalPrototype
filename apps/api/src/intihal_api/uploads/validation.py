from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from io import SEEK_END, SEEK_SET
from pathlib import PurePath
from typing import BinaryIO
from zipfile import BadZipFile, ZipFile, is_zipfile

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024
TEXT_SIGNATURE_SAMPLE_BYTES = 8192
DOCX_REQUIRED_MEMBERS = frozenset({"[Content_Types].xml", "word/document.xml"})
OLE_COMPOUND_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class DocumentFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"


ALLOWED_MIME_TYPES: dict[DocumentFormat, frozenset[str]] = {
    DocumentFormat.PDF: frozenset({"application/pdf"}),
    DocumentFormat.DOCX: frozenset(
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    ),
    DocumentFormat.TXT: frozenset({"text/plain"}),
}
FORMAT_BY_EXTENSION = {
    f".{document_format.value}": document_format for document_format in DocumentFormat
}


class UploadValidationError(ValueError):
    """Base error carrying a stable code for the future upload endpoint."""

    status_code = 400

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class FileTooLargeError(UploadValidationError):
    status_code = 413

    def __init__(self) -> None:
        super().__init__("file_too_large", "Dosya boyutu 20 MB sınırını aşıyor.")


class EmptyUploadError(UploadValidationError):
    def __init__(self) -> None:
        super().__init__("empty_file", "Boş dosya yüklenemez.")


class UnsupportedFileTypeError(UploadValidationError):
    def __init__(self) -> None:
        super().__init__(
            "unsupported_file_type",
            "Yalnızca PDF, DOCX ve TXT dosyaları kabul edilir.",
        )


class FileSignatureMismatchError(UploadValidationError):
    def __init__(self) -> None:
        super().__init__(
            "file_signature_mismatch",
            "Dosya bozuk olabilir veya uzantısı içeriğiyle eşleşmiyor. Dosyayı kendi "
            "uygulamasında açıp yeniden kaydederek yükleyin.",
        )


class EncryptedDocumentError(UploadValidationError):
    def __init__(self) -> None:
        super().__init__(
            "encrypted_document",
            "Şifreli belgeler işlenemez; belgenin şifresini kaldırıp yeniden yükleyin.",
        )


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    filename: str
    document_format: DocumentFormat
    content_type: str
    size_bytes: int


def validate_document_upload(
    *,
    filename: str,
    content_type: str | None,
    stream: BinaryIO,
) -> ValidatedUpload:
    """Validate size, extension, MIME type, and content without consuming the stream."""

    try:
        size_bytes = _measure_stream(stream)
        if size_bytes == 0:
            raise EmptyUploadError
        if size_bytes > MAX_UPLOAD_SIZE_BYTES:
            raise FileTooLargeError

        document_format = _format_from_filename(filename)
        normalized_content_type = _normalize_content_type(content_type)
        if normalized_content_type not in ALLOWED_MIME_TYPES[document_format]:
            raise UnsupportedFileTypeError

        if not _content_matches_format(stream, document_format, size_bytes):
            raise FileSignatureMismatchError

        return ValidatedUpload(
            filename=filename,
            document_format=document_format,
            content_type=normalized_content_type,
            size_bytes=size_bytes,
        )
    finally:
        stream.seek(0, SEEK_SET)


def _measure_stream(stream: BinaryIO) -> int:
    stream.seek(0, SEEK_END)
    size_bytes = stream.tell()
    stream.seek(0, SEEK_SET)
    return size_bytes


def _format_from_filename(filename: str) -> DocumentFormat:
    extension = PurePath(filename.strip()).suffix.lower()
    try:
        return FORMAT_BY_EXTENSION[extension]
    except KeyError as error:
        raise UnsupportedFileTypeError from error


def _normalize_content_type(content_type: str | None) -> str:
    if content_type is None:
        raise UnsupportedFileTypeError
    return content_type.partition(";")[0].strip().lower()


def _content_matches_format(
    stream: BinaryIO,
    document_format: DocumentFormat,
    size_bytes: int,
) -> bool:
    stream.seek(0, SEEK_SET)
    if document_format is DocumentFormat.PDF:
        return _is_readable_pdf(stream)
    if document_format is DocumentFormat.DOCX:
        if stream.read(len(OLE_COMPOUND_SIGNATURE)) == OLE_COMPOUND_SIGNATURE:
            raise EncryptedDocumentError
        return _is_docx(stream)
    return _looks_like_text(stream, size_bytes)


def _is_readable_pdf(stream: BinaryIO) -> bool:
    stream.seek(0, SEEK_SET)
    if stream.read(5) != b"%PDF-":
        return False

    stream.seek(0, SEEK_SET)
    try:
        reader = PdfReader(stream, strict=True)
        if reader.is_encrypted:
            raise EncryptedDocumentError
        # Accessing pages forces pypdf to resolve the page tree instead of only
        # recognizing the header and trailer of a damaged file.
        len(reader.pages)
        return True
    except EncryptedDocumentError:
        raise
    except (PdfReadError, OSError, TypeError, ValueError):
        return False


def _is_docx(stream: BinaryIO) -> bool:
    stream.seek(0, SEEK_SET)
    if not is_zipfile(stream):
        return False

    stream.seek(0, SEEK_SET)
    try:
        with ZipFile(stream) as archive:
            if any(member.flag_bits & 0x1 for member in archive.infolist()):
                raise EncryptedDocumentError
            return DOCX_REQUIRED_MEMBERS.issubset(archive.namelist())
    except (BadZipFile, OSError):
        return False


def _looks_like_text(stream: BinaryIO, size_bytes: int) -> bool:
    sample = stream.read(min(size_bytes, TEXT_SIGNATURE_SAMPLE_BYTES))
    if b"\x00" in sample:
        return False

    permitted_controls = {9, 10, 12, 13}
    suspicious_controls = sum(byte < 32 and byte not in permitted_controls for byte in sample)
    return suspicious_controls / len(sample) <= 0.02
