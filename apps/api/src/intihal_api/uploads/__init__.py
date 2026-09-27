"""Validation primitives for user-supplied document uploads."""

from intihal_api.uploads.validation import (
    MAX_UPLOAD_SIZE_BYTES,
    EmptyUploadError,
    FileSignatureMismatchError,
    FileTooLargeError,
    UnsupportedFileTypeError,
    UploadValidationError,
    ValidatedUpload,
    validate_document_upload,
)

__all__ = [
    "MAX_UPLOAD_SIZE_BYTES",
    "EmptyUploadError",
    "FileSignatureMismatchError",
    "FileTooLargeError",
    "UnsupportedFileTypeError",
    "UploadValidationError",
    "ValidatedUpload",
    "validate_document_upload",
]
