from __future__ import annotations

import hmac
from collections.abc import Iterable
from typing import BinaryIO, Protocol
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.sql import Executable
from starlette.concurrency import run_in_threadpool

from intihal_api.core.audit import AuditAction, AuditOutcome, record_audit
from intihal_api.db.models import SourceChunk, SourceDocument, SourceDocumentStatus
from intihal_api.extraction import ChunkedText, extract_and_chunk_document
from intihal_api.uploads import calculate_sha256
from intihal_api.uploads.validation import ALLOWED_MIME_TYPES, DocumentFormat

FORMAT_BY_CONTENT_TYPE = {
    content_type: document_format
    for document_format, content_types in ALLOWED_MIME_TYPES.items()
    for content_type in content_types
}


class SourceProcessingSession(Protocol):
    def add_all(self, instances: Iterable[object]) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...

    async def execute(self, statement: Executable) -> object: ...


class UnsupportedSourceContentTypeError(ValueError):
    """The persisted source MIME type cannot be routed to an extractor."""


class SourceChecksumMismatchError(RuntimeError):
    """Stored source bytes no longer match their registered immutable identity."""

    def __init__(self) -> None:
        super().__init__(
            "Kaynak dosyanın checksum değeri kayıtlı SHA-256 ile eşleşmiyor; "
            "dosya değiştirilmiş olabilir."
        )


class SourceDocumentProcessingService:
    """Extract, normalize, and persist chunks for one licensed source document."""

    async def process(
        self,
        *,
        source_document: SourceDocument,
        stream: BinaryIO,
        session: SourceProcessingSession,
        actor_id: UUID | None = None,
        audit_action: AuditAction = AuditAction.SOURCE_REINDEX,
    ) -> ChunkedText:
        source_id = source_document.id
        if audit_action not in (AuditAction.SOURCE_CREATE, AuditAction.SOURCE_REINDEX):
            raise ValueError("Unsupported source audit action")
        document_format = _document_format_for(source_document.content_type)
        checksum, size_bytes = await run_in_threadpool(calculate_sha256, stream)
        if not hmac.compare_digest(checksum, source_document.sha256) or (
            size_bytes != source_document.size_bytes
        ):
            raise SourceChecksumMismatchError

        source_document.status = SourceDocumentStatus.PROCESSING
        if actor_id is not None and audit_action is AuditAction.SOURCE_REINDEX:
            record_audit(
                session,
                action=audit_action,
                actor_id=actor_id,
                resource_id=source_id,
                outcome=AuditOutcome.STARTED,
            )
        await session.commit()

        try:
            chunked_text = await run_in_threadpool(
                extract_and_chunk_document,
                stream,
                document_format,
            )
        except Exception:
            source_document.status = SourceDocumentStatus.FAILED
            if actor_id is not None:
                record_audit(
                    session,
                    action=audit_action,
                    actor_id=actor_id,
                    resource_id=source_id,
                    outcome=AuditOutcome.FAILED,
                )
            await session.commit()
            raise

        chunks = [
            SourceChunk(
                source_document_id=source_document.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                token_count=chunk.token_count,
                page_number=chunk.page_number,
                content_sha256=chunk.content_sha256,
            )
            for chunk in chunked_text.chunks
        ]
        try:
            await session.execute(
                delete(SourceChunk).where(SourceChunk.source_document_id == source_document.id)
            )
            session.add_all(chunks)
            source_document.status = SourceDocumentStatus.READY
            if actor_id is not None:
                record_audit(
                    session,
                    action=audit_action,
                    actor_id=actor_id,
                    resource_id=source_id,
                )
            await session.commit()
        except Exception:
            await session.rollback()
            source_document.status = SourceDocumentStatus.FAILED
            try:
                if actor_id is not None:
                    record_audit(
                        session,
                        action=audit_action,
                        actor_id=actor_id,
                        resource_id=source_id,
                        outcome=AuditOutcome.FAILED,
                    )
                await session.commit()
            except Exception:
                await session.rollback()
            raise

        return chunked_text


def _document_format_for(content_type: str) -> DocumentFormat:
    try:
        return FORMAT_BY_CONTENT_TYPE[content_type]
    except KeyError as error:
        raise UnsupportedSourceContentTypeError(
            f"Desteklenmeyen kaynak içerik türü: {content_type}"
        ) from error
