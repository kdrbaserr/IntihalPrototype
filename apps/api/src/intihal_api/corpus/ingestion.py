from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import BinaryIO, Protocol
from uuid import uuid4

from starlette.concurrency import run_in_threadpool

from intihal_api.corpus.service import SourceDocumentProcessingService, SourceProcessingSession
from intihal_api.db.models import LicenseStatus, SourceDocument, SourceDocumentStatus
from intihal_api.storage import StorageError, StoredObject, build_source_storage_key
from intihal_api.uploads import (
    UploadContentChangedError,
    calculate_sha256,
    sanitize_original_filename,
    validate_document_upload,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    title: str
    license_name: str
    rights_holder: str
    license_evidence_reference: str
    author: str | None = None
    publisher: str | None = None
    source_url: str | None = None
    license_url: str | None = None
    attribution_text: str | None = None
    license_valid_from: date | None = None
    license_valid_until: date | None = None


class SourceStorage(Protocol):
    def upload_object(
        self,
        *,
        key: str,
        stream: BinaryIO,
        size_bytes: int,
        content_type: str,
    ) -> StoredObject: ...

    def remove_object(self, key: str) -> None: ...


class SourceIngestionSession(SourceProcessingSession, Protocol):
    def add(self, instance: object) -> None: ...


class SourceDocumentIngestionService:
    """Validate, store, register, and process one licensed corpus source."""

    def __init__(self, storage: SourceStorage) -> None:
        self.storage = storage

    async def create_source(
        self,
        *,
        metadata: SourceMetadata,
        filename: str,
        content_type: str | None,
        stream: BinaryIO,
        session: SourceIngestionSession,
    ) -> SourceDocument:
        normalized_metadata = _normalize_metadata(metadata)
        validated = await run_in_threadpool(
            validate_document_upload,
            filename=filename,
            content_type=content_type,
            stream=stream,
        )
        original_filename = sanitize_original_filename(validated.filename)
        checksum, measured_size = await run_in_threadpool(calculate_sha256, stream)
        if measured_size != validated.size_bytes:
            raise UploadContentChangedError("Dosya doğrulama sırasında değişti; yeniden yükleyin.")
        source_id = uuid4()
        storage_key = build_source_storage_key(source_id)
        stored_object = await run_in_threadpool(
            self.storage.upload_object,
            key=storage_key,
            stream=stream,
            size_bytes=measured_size,
            content_type=validated.content_type,
        )
        source = SourceDocument(
            id=source_id,
            title=normalized_metadata.title,
            author=normalized_metadata.author,
            publisher=normalized_metadata.publisher,
            source_url=normalized_metadata.source_url,
            status=SourceDocumentStatus.PENDING,
            license_status=LicenseStatus.PENDING,
            license_name=normalized_metadata.license_name,
            rights_holder=normalized_metadata.rights_holder,
            license_url=normalized_metadata.license_url,
            attribution_text=normalized_metadata.attribution_text,
            license_evidence_reference=normalized_metadata.license_evidence_reference,
            license_valid_from=normalized_metadata.license_valid_from,
            license_valid_until=normalized_metadata.license_valid_until,
            original_filename=original_filename,
            content_type=validated.content_type,
            size_bytes=measured_size,
            sha256=checksum,
            storage_bucket=stored_object.bucket,
            storage_key=stored_object.key,
            storage_etag=stored_object.etag,
        )

        try:
            session.add(source)
            await session.commit()
        except Exception:
            await session.rollback()
            await self._remove_orphaned_object(stored_object.key)
            raise

        await SourceDocumentProcessingService().process(
            source_document=source,
            stream=stream,
            session=session,
        )
        await session.refresh(source)
        return source

    async def _remove_orphaned_object(self, storage_key: str) -> None:
        try:
            await run_in_threadpool(self.storage.remove_object, storage_key)
        except StorageError:
            logger.exception(
                "Could not remove source object after metadata persistence failed",
                extra={"storage_key": storage_key},
            )


def _required(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label} boş bırakılamaz.")
    return cleaned


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _normalize_metadata(metadata: SourceMetadata) -> SourceMetadata:
    if (
        metadata.license_valid_from is not None
        and metadata.license_valid_until is not None
        and metadata.license_valid_until < metadata.license_valid_from
    ):
        raise ValueError("Lisans bitiş tarihi başlangıç tarihinden önce olamaz.")

    return SourceMetadata(
        title=_required(metadata.title, "Kaynak başlığı"),
        author=_optional(metadata.author),
        publisher=_optional(metadata.publisher),
        source_url=_optional(metadata.source_url),
        license_name=_required(metadata.license_name, "Lisans türü"),
        rights_holder=_required(metadata.rights_holder, "Hak sahibi"),
        license_url=_optional(metadata.license_url),
        attribution_text=_optional(metadata.attribution_text),
        license_evidence_reference=_required(
            metadata.license_evidence_reference,
            "Lisans kanıt referansı",
        ),
        license_valid_from=metadata.license_valid_from,
        license_valid_until=metadata.license_valid_until,
    )
