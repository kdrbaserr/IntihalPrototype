import asyncio
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from hashlib import blake2b
from typing import Any
from uuid import UUID

from billiard.exceptions import SoftTimeLimitExceeded
from celery.utils.time import get_exponential_backoff_interval
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from intihal_api.core.config import get_settings
from intihal_api.core.diagnostics import log_error
from intihal_api.db.models import AnalysisStatus, Document, DocumentStatus
from intihal_api.documents.retention import cleanup_expired_documents
from intihal_api.jobs.app import TransientJobError
from intihal_api.jobs.states import transition_document
from intihal_api.jobs.workflow import analyze_document, extract_document, latest_analysis
from intihal_api.storage import StorageConnectionError, create_object_storage_service

ACTIVE_STATES = (DocumentStatus.QUEUED, DocumentStatus.EXTRACTING, DocumentStatus.ANALYZING)


def is_transient(error: Exception) -> bool:
    return isinstance(error, (StorageConnectionError, OperationalError, InterfaceError)) or (
        isinstance(error, DBAPIError) and error.connection_invalidated
    )


def failure_code(error: Exception) -> str:
    if isinstance(error, SoftTimeLimitExceeded):
        return "processing_timeout"
    code = getattr(error, "code", None)
    if code in {"ocr_required", "invalid_pdf", "invalid_docx", "no_extractable_text"}:
        return code
    if isinstance(error, ValueError) and str(error) in {
        "stored_document_changed",
        "no_extractable_text",
        "missing_document_chunks",
        "missing_algorithm_snapshot",
        "unsupported_algorithm_version",
    }:
        return str(error)
    return "processing_failed"


async def fail_document(document, analysis, session, reason: str) -> None:
    transition_document(document, DocumentStatus.FAILED)
    document.failure_reason = reason
    document.next_attempt_at = None
    if analysis is not None:
        analysis.status = AnalysisStatus.FAILED
        analysis.failure_reason = reason
        analysis.completed_at = datetime.now(UTC)
    await session.commit()


async def run_stage(document_id: str, stage: str, task_id: str | None = None) -> str:
    """Pin one connection so a document lock survives progress commits."""
    settings = get_settings()
    identifier = UUID(document_id)
    lock_key = int.from_bytes(blake2b(identifier.bytes, digest_size=8).digest(), signed=True)
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            locked = await connection.scalar(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key}
            )
            await connection.commit()
            if not locked:
                return "already_running"
            try:
                async with AsyncSession(connection, expire_on_commit=False) as session:
                    document = await session.get(Document, identifier)
                    expected = (
                        {DocumentStatus.QUEUED, DocumentStatus.EXTRACTING}
                        if stage == "extract"
                        else {DocumentStatus.ANALYZING}
                    )
                    if document is None or document.status not in expected:
                        return "skipped"
                    if document.next_attempt_at and document.next_attempt_at > datetime.now(UTC):
                        return "waiting"
                    analysis = await latest_analysis(session, identifier)
                    if analysis is None:
                        await fail_document(document, None, session, "missing_analysis")
                        return "failed"
                    if document.processing_attempts >= settings.task_max_retries + 1:
                        await fail_document(document, analysis, session, "retry_exhausted")
                        return "failed"
                    document.processing_attempts += 1
                    # A killed process leaves a durable due time for recovery by the dispatcher.
                    document.next_attempt_at = datetime.now(UTC) + timedelta(
                        seconds=settings.task_hard_timeout_seconds + 30
                    )
                    await session.commit()
                    analysis_identifier = str(analysis.id)
                    attempt = document.processing_attempts
                    try:
                        if stage == "extract":
                            storage = create_object_storage_service(settings)
                            if storage.bucket_name != document.storage_bucket:
                                raise ValueError("storage bucket mismatch")
                            await extract_document(document, analysis, session, storage)
                        else:
                            await analyze_document(document, analysis, session, settings)
                        return "succeeded"
                    except Exception as error:
                        log_error(
                            error,
                            code=failure_code(error),
                            event="workflow_stage_error",
                            document_id=str(identifier),
                            analysis_id=analysis_identifier,
                            stage=stage,
                            attempt=attempt,
                            task_id=task_id,
                        )
                        await session.rollback()
                        # Rollback expires ORM instances; reload before accessing attributes.
                        document = await session.get(Document, identifier)
                        analysis = await latest_analysis(session, identifier)
                        if document is None:
                            raise
                        if is_transient(error) and (
                            document.processing_attempts < settings.task_max_retries + 1
                        ):
                            delay = get_exponential_backoff_interval(
                                factor=settings.task_retry_backoff_seconds,
                                retries=document.processing_attempts - 1,
                                maximum=settings.task_retry_backoff_max_seconds,
                                full_jitter=True,
                            )
                            document.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
                            await session.commit()
                            return "retry_scheduled"
                        reason = "retry_exhausted" if is_transient(error) else failure_code(error)
                        await fail_document(document, analysis, session, reason)
                        return "failed"
            finally:
                await connection.rollback()
                await connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
                await connection.commit()
    finally:
        await engine.dispose()


async def dispatch_pending(publish: Callable[[str, str], Any]) -> int:
    """Database state is the durable dispatch intent; messages may be delivered again."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            pending = (
                await session.execute(
                    select(Document.id, Document.status)
                    .where(
                        Document.status.in_(ACTIVE_STATES),
                        Document.next_attempt_at <= datetime.now(UTC),
                    )
                    .order_by(Document.next_attempt_at, Document.id)
                    .limit(100)
                )
            ).all()
            for identifier, status in pending:
                name = (
                    "intihal.analysis.run"
                    if status is DocumentStatus.ANALYZING
                    else "intihal.documents.extract"
                )
                publish(name, str(identifier))
            return len(pending)
    finally:
        await engine.dispose()


async def run_retention_cleanup() -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            return await cleanup_expired_documents(session, create_object_storage_service(settings))
    finally:
        await engine.dispose()


def run_async(operation: Coroutine[Any, Any, Any], **context) -> Any:
    try:
        return asyncio.run(operation)
    except Exception as error:
        identifier = log_error(
            error, code="internal_error", event="worker_unhandled_error", **context
        )
        if is_transient(error):
            raise TransientJobError(
                f"Background dependency unavailable; trace_id={identifier}"
            ) from None
        raise RuntimeError(f"Background job failed; trace_id={identifier}") from None
