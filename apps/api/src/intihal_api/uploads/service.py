from __future__ import annotations

import unicodedata
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import SEEK_SET
from pathlib import PurePath
from typing import BinaryIO, Protocol
from uuid import UUID, uuid4

from starlette.concurrency import run_in_threadpool

from intihal_api.core.diagnostics import log_error
from intihal_api.db.models import Document, DocumentStatus
from intihal_api.storage import StorageError, StoredObject, build_document_storage_key
from intihal_api.uploads.validation import ValidatedUpload, validate_document_upload

HASH_CHUNK_SIZE_BYTES = 1024 * 1024
MAX_ORIGINAL_FILENAME_LENGTH = 255


class DocumentSession(Protocol):
    def add(self, instance: object) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class DocumentStorage(Protocol):
    def upload_object(
        self,
        *,
        key: str,
        stream: BinaryIO,
        size_bytes: int,
        content_type: str,
    ) -> StoredObject: ...

    def remove_object(self, key: str) -> None: ...


class UploadContentChangedError(RuntimeError):
    """The stream changed after validation and before persistence."""


class InvalidOriginalFilenameError(ValueError):
    """The client filename has no safe displayable component."""


class DocumentUploadService:
    """Coordinate validation, object upload, and document metadata persistence."""

    def __init__(self, storage: DocumentStorage) -> None:
        self.storage = storage

    async def create_document(
        self,
        *,
        owner_id: UUID,
        filename: str,
        content_type: str | None,
        stream: BinaryIO,
        session: DocumentSession,
        retention_days: int = 7,
    ) -> Document:
        if retention_days not in (7, 30):
            raise ValueError("retention_days must be 7 or 30")
        validated = await run_in_threadpool(
            validate_document_upload,
            filename=filename,
            content_type=content_type,
            stream=stream,
        )
        original_filename = sanitize_original_filename(validated.filename)
        checksum, measured_size = await run_in_threadpool(calculate_sha256, stream)
        _require_unchanged_content(validated, measured_size)

        document_id = uuid4()
        storage_key = build_document_storage_key(owner_id, document_id)
        stored_object = await run_in_threadpool(
            self.storage.upload_object,
            key=storage_key,
            stream=stream,
            size_bytes=measured_size,
            content_type=validated.content_type,
        )

        document = Document(
            id=document_id,
            owner_id=owner_id,
            original_filename=original_filename,
            content_type=validated.content_type,
            size_bytes=measured_size,
            sha256=checksum,
            status=DocumentStatus.UPLOADED,
            storage_bucket=stored_object.bucket,
            storage_key=stored_object.key,
            storage_etag=stored_object.etag,
            retention_days=retention_days,
            expires_at=datetime.now(UTC) + timedelta(days=retention_days),
        )

        try:
            session.add(document)
            await session.commit()
        except Exception:
            await session.rollback()
            await self._remove_orphaned_object(stored_object.key)
            raise

        return document

    async def _remove_orphaned_object(self, storage_key: str) -> None:
        try:
            await run_in_threadpool(self.storage.remove_object, storage_key)
        except StorageError as error:
            log_error(
                error,
                code="storage_unavailable",
                event="document_cleanup_failed",
                storage_key=storage_key,
            )


def calculate_sha256(stream: BinaryIO) -> tuple[str, int]:
    """Hash a stream incrementally and leave it ready for a subsequent upload."""

    digest = sha256()
    size_bytes = 0
    stream.seek(0, SEEK_SET)
    try:
        while chunk := stream.read(HASH_CHUNK_SIZE_BYTES):
            digest.update(chunk)
            size_bytes += len(chunk)
        return digest.hexdigest(), size_bytes
    finally:
        stream.seek(0, SEEK_SET)


def sanitize_original_filename(filename: str) -> str:
    """Keep a safe display name while discarding client-supplied path components."""

    leaf_name = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    normalized_name = unicodedata.normalize("NFC", leaf_name)
    safe_name = "".join(
        character
        for character in normalized_name
        if not unicodedata.category(character).startswith("C")
    ).strip()
    if not safe_name or safe_name in {".", ".."}:
        raise InvalidOriginalFilenameError("Dosyanın geçerli bir adı bulunmuyor.")

    if len(safe_name) <= MAX_ORIGINAL_FILENAME_LENGTH:
        return safe_name

    suffix = PurePath(safe_name).suffix
    stem_length = MAX_ORIGINAL_FILENAME_LENGTH - len(suffix)
    return f"{safe_name[:stem_length]}{suffix}"


def _require_unchanged_content(validated: ValidatedUpload, measured_size: int) -> None:
    if measured_size != validated.size_bytes:
        raise UploadContentChangedError("Dosya doğrulama sırasında değişti; yeniden yükleyin.")
