"""Retryable cleanup across PostgreSQL and object storage."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from intihal_api.core.audit import AuditAction, AuditActor, AuditOutcome, record_audit
from intihal_api.db.models import Analysis, Document, DocumentChunk, DocumentStatus, Match
from intihal_api.storage import ObjectStorageService, build_document_storage_key

ACTIVE_STATES = {DocumentStatus.QUEUED, DocumentStatus.EXTRACTING, DocumentStatus.ANALYZING}


class DocumentCleanupError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


async def cleanup_document(
    document: Document,
    session: AsyncSession,
    storage: ObjectStorageService,
    *,
    actor_id: UUID | None = None,
) -> None:
    """Caller must hold the owner's document row lock; never purge active work."""
    if document.cleaned_at is not None:
        return
    if document.status in ACTIVE_STATES:
        raise DocumentCleanupError("document_processing")
    # Do not let a corrupt/legacy location delete an unrelated bucket or corpus object.
    if (
        document.storage_bucket != storage.bucket_name
        or document.storage_key != build_document_storage_key(document.owner_id, document.id)
    ):
        raise DocumentCleanupError("document_storage_mismatch")

    identifier = document.id
    key = document.storage_key
    actor_kind = AuditActor.USER if actor_id is not None else AuditActor.SYSTEM
    if document.status is not DocumentStatus.DELETED:
        record_audit(
            session,
            action=AuditAction.DOCUMENT_DELETE,
            actor_id=actor_id,
            actor_kind=actor_kind,
            resource_id=identifier,
            outcome=AuditOutcome.STARTED,
        )
    document.status = DocumentStatus.DELETED
    document.next_attempt_at = None
    document.failure_reason = None
    # Durable tombstone hides all dependent data before the irreversible storage call.
    # A failure after this commit can be resumed with the same owner-checked request.
    await session.commit()
    await run_in_threadpool(storage.remove_object, key)

    # The tombstone commit released the first lock. Serialize completion so concurrent
    # retries cannot publish two successful audit events for the same cleanup.
    document = await session.scalar(
        select(Document)
        .where(Document.id == identifier)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if document is None or document.cleaned_at is not None:
        await session.rollback()
        return

    analysis_ids = select(Analysis.id).where(Analysis.document_id == identifier)
    await session.execute(delete(Match).where(Match.analysis_id.in_(analysis_ids)))
    await session.execute(delete(Analysis).where(Analysis.document_id == identifier))
    await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == identifier))
    # Keep only the document's tombstone/metadata for ownership and idempotent retries.
    document.cleaned_at = datetime.now(UTC)
    record_audit(
        session,
        action=AuditAction.DOCUMENT_DELETE,
        actor_id=actor_id,
        actor_kind=actor_kind,
        resource_id=identifier,
    )
    await session.commit()
