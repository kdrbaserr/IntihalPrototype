from io import BytesIO
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest

from file_samples import make_pdf_bytes
from intihal_api.uploads import (
    MAX_UPLOAD_SIZE_BYTES,
    EmptyUploadError,
    EncryptedDocumentError,
    FileSignatureMismatchError,
    FileTooLargeError,
    UnsupportedFileTypeError,
    validate_document_upload,
)

PDF_MIME_TYPE = "application/pdf"
DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def make_docx(*, include_document: bool = True, total_size: int | None = None) -> BytesIO:
    document_content = b"<w:document />" if include_document else b""
    compression = ZIP_STORED if total_size is not None else ZIP_DEFLATED

    def write_stream(content: bytes) -> BytesIO:
        result = BytesIO()
        with ZipFile(result, mode="w", compression=compression) as archive:
            archive.writestr("[Content_Types].xml", "<Types />")
            if include_document:
                archive.writestr("word/document.xml", content)
        result.seek(0)
        return result

    stream = write_stream(document_content)
    if total_size is not None:
        document_content += b"x" * (total_size - len(stream.getvalue()))
        stream = write_stream(document_content)
        assert len(stream.getvalue()) == total_size
    return stream


def test_valid_pdf_is_accepted_and_stream_is_rewound() -> None:
    stream = BytesIO(make_pdf_bytes())

    result = validate_document_upload(
        filename="tez.PDF",
        content_type=PDF_MIME_TYPE,
        stream=stream,
    )

    assert result.document_format == "pdf"
    assert result.size_bytes == len(stream.getvalue())
    assert stream.tell() == 0


def test_file_at_exactly_twenty_megabytes_is_accepted() -> None:
    stream = make_docx(total_size=MAX_UPLOAD_SIZE_BYTES)

    result = validate_document_upload(
        filename="sinir.docx",
        content_type=DOCX_MIME_TYPE,
        stream=stream,
    )

    assert result.size_bytes == MAX_UPLOAD_SIZE_BYTES


def test_file_over_twenty_megabytes_is_rejected_with_413() -> None:
    stream = BytesIO(b"%PDF-" + b"x" * (MAX_UPLOAD_SIZE_BYTES - 4))

    with pytest.raises(FileTooLargeError) as captured_error:
        validate_document_upload(
            filename="buyuk.pdf",
            content_type=PDF_MIME_TYPE,
            stream=stream,
        )

    assert captured_error.value.status_code == 413
    assert captured_error.value.code == "file_too_large"
    assert stream.tell() == 0


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("zararli.exe", "application/octet-stream"),
        ("tez.pdf.exe", PDF_MIME_TYPE),
        ("uzantisiz", PDF_MIME_TYPE),
        ("arsiv.zip", "application/zip"),
    ],
)
def test_extension_allowlist_rejects_unsupported_files(
    filename: str,
    content_type: str,
) -> None:
    with pytest.raises(UnsupportedFileTypeError):
        validate_document_upload(
            filename=filename,
            content_type=content_type,
            stream=BytesIO(b"%PDF-1.7"),
        )


def test_mime_type_must_match_extension() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        validate_document_upload(
            filename="sahte.pdf",
            content_type="text/plain",
            stream=BytesIO(b"%PDF-1.7"),
        )


def test_mime_type_parameters_are_normalized() -> None:
    result = validate_document_upload(
        filename="notlar.txt",
        content_type="Text/Plain; charset=windows-1254",
        stream=BytesIO("Türkçe notlar".encode("cp1254")),
    )

    assert result.content_type == "text/plain"


def test_pdf_extension_with_wrong_signature_is_rejected() -> None:
    with pytest.raises(FileSignatureMismatchError):
        validate_document_upload(
            filename="sahte.pdf",
            content_type=PDF_MIME_TYPE,
            stream=BytesIO(b"not really a PDF"),
        )


def test_pdf_with_valid_header_but_broken_structure_is_rejected() -> None:
    with pytest.raises(FileSignatureMismatchError):
        validate_document_upload(
            filename="bozuk.pdf",
            content_type=PDF_MIME_TYPE,
            stream=BytesIO(b"%PDF-1.7\n1 0 obj\ntruncated"),
        )


def test_password_protected_pdf_is_rejected() -> None:
    with pytest.raises(EncryptedDocumentError) as captured_error:
        validate_document_upload(
            filename="sifreli.pdf",
            content_type=PDF_MIME_TYPE,
            stream=BytesIO(make_pdf_bytes(password="secret")),
        )

    assert captured_error.value.code == "encrypted_document"


def test_encrypted_office_container_renamed_as_docx_is_rejected() -> None:
    with pytest.raises(EncryptedDocumentError):
        validate_document_upload(
            filename="sifreli.docx",
            content_type=DOCX_MIME_TYPE,
            stream=BytesIO(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"encrypted-package"),
        )


def test_valid_docx_container_is_accepted() -> None:
    result = validate_document_upload(
        filename="tez.docx",
        content_type=DOCX_MIME_TYPE,
        stream=make_docx(),
    )

    assert result.document_format == "docx"


def test_plain_zip_renamed_as_docx_is_rejected() -> None:
    with pytest.raises(FileSignatureMismatchError):
        validate_document_upload(
            filename="sahte.docx",
            content_type=DOCX_MIME_TYPE,
            stream=make_docx(include_document=False),
        )


def test_binary_content_renamed_as_txt_is_rejected() -> None:
    with pytest.raises(FileSignatureMismatchError):
        validate_document_upload(
            filename="sahte.txt",
            content_type="text/plain",
            stream=BytesIO(b"text-looking prefix\x00binary remainder"),
        )


def test_empty_file_is_rejected() -> None:
    with pytest.raises(EmptyUploadError):
        validate_document_upload(
            filename="bos.txt",
            content_type="text/plain",
            stream=BytesIO(),
        )
