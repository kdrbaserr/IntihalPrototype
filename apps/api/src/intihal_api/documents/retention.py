"""Bounded, repeatable retention sweep for the trusted background worker."""

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from intihal_api.core.diagnostics import log_error
from intihal_api.db.models import Document, DocumentStatus
from intihal_api.documents.cleanup import ACTIVE_STATES, cleanup_document
from intihal_api.storage import ObjectStorageService


async def cleanup_expired_documents(
    session: AsyncSession,
    storage: ObjectStorageService,
    *,
    limit: int = 100,
    now: datetime | None = None,
) -> int:
    now = now or datetime.now(UTC)
    eligible = (
        Document.cleaned_at.is_(None),
        Document.status.not_in(ACTIVE_STATES),
        or_(Document.expires_at <= now, Document.status == DocumentStatus.DELETED),
    )
    identifiers = list(
        await session.scalars(
            select(Document.id)
            .where(*eligible)
            .order_by(Document.updated_at, Document.id)
            .limit(limit)
        )
    )
    await session.rollback()
    cleaned = 0
    for identifier in identifiers:
        # Recheck under a row lock: an analysis may have been queued after candidate selection.
        document = await session.scalar(
            select(Document)
            .where(Document.id == identifier, *eligible)
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
        if document is None:
            await session.rollback()
            continue
        try:
            await cleanup_document(document, session, storage)
            cleaned += 1
        except Exception as error:
            await session.rollback()
            log_error(
                error,
                code="document_cleanup_pending",
                event="retention_cleanup_failed",
                document_id=str(identifier),
            )
    return cleaned
