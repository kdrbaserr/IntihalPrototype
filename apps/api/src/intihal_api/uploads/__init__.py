"""Validation primitives for user-supplied document uploads."""

from intihal_api.uploads.service import (
    DocumentUploadService,
    InvalidOriginalFilenameError,
    UploadContentChangedError,
    calculate_sha256,
    sanitize_original_filename,
)
from intihal_api.uploads.validation import (
    MAX_UPLOAD_SIZE_BYTES,
    EmptyUploadError,
    EncryptedDocumentError,
    FileSignatureMismatchError,
    FileTooLargeError,
    UnsupportedFileTypeError,
    UploadValidationError,
    ValidatedUpload,
    validate_document_upload,
)

__all__ = [
    "MAX_UPLOAD_SIZE_BYTES",
    "DocumentUploadService",
    "EmptyUploadError",
    "EncryptedDocumentError",
    "FileSignatureMismatchError",
    "FileTooLargeError",
    "InvalidOriginalFilenameError",
    "UnsupportedFileTypeError",
    "UploadValidationError",
    "UploadContentChangedError",
    "ValidatedUpload",
    "calculate_sha256",
    "sanitize_original_filename",
    "validate_document_upload",
]
