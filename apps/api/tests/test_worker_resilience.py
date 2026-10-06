"""Run the real workflow against SQLite and optional migrated PostgreSQL.

Only advisory SQL and SQLite's missing timezone round-trip are adapted. Errors
are injected at stage boundaries, without a broker or an actual process kill.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from billiard.exceptions import SoftTimeLimitExceeded
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from intihal_api.core.config import Settings
from intihal_api.db.base import Base
from intihal_api.db.models import Analysis, AnalysisStatus, Document, DocumentStatus, Match
from intihal_api.jobs import runtime
from intihal_api.jobs.states import transition_document
from intihal_api.storage import StorageConnectionError
from test_document_workflow import StoredContent, seed_source
from test_workflow_postgres import seed_document
from test_workflow_postgres import workflow_database as workflow_database


class WorkerStopped(BaseException):
    """Model process loss: bypass the ordinary Exception/failure handler."""


@pytest.fixture(params=["sqlite", "postgres"])
def workflow_settings(request, tmp_path, monkeypatch):
    storage = StoredContent()
    storage.bucket_name = "intihal-documents"
    monkeypatch.setattr(runtime, "create_object_storage_service", lambda _: storage)
    if request.param == "postgres":
        yield request.getfixturevalue("workflow_database")
        return
    settings = Settings(_env_file=None, database_url=f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}")

    def engine_factory(*args, **kwargs):
        engine = create_async_engine(*args, **kwargs)

        @event.listens_for(engine.sync_engine, "connect")
        def advisory_sql(connection, _):
            # Sequential tests only: these are SQL compatibility stubs, not lock tests.
            connection.create_function("pg_try_advisory_lock", 1, lambda _: True)
            connection.create_function("pg_advisory_unlock", 1, lambda _: True)
            connection.execute("PRAGMA foreign_keys=ON")

        return engine

    def restore_timezone(document, *args):
        value = document.next_attempt_at
        if value is not None and value.tzinfo is None:
            document.next_attempt_at = value.replace(tzinfo=UTC)

    event.listen(Document, "load", restore_timezone)
    event.listen(Document, "refresh", restore_timezone)
    monkeypatch.setattr(runtime, "get_settings", lambda: settings)
    monkeypatch.setattr(runtime, "create_async_engine", engine_factory)
    try:
        yield settings
    finally:
        event.remove(Document, "load", restore_timezone)
        event.remove(Document, "refresh", restore_timezone)


async def prepare(settings, stage, session):
    async with session.bind.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    document = await seed_document(session)
    await seed_source(session)
    analysis = await runtime.latest_analysis(session, document.id)
    assert analysis is None
    from intihal_api.jobs.workflow import queue_document

    analysis = await queue_document(document, session, settings)
    if stage == "analyze":
        assert await runtime.run_stage(str(document.id), "extract") == "succeeded"
        await session.refresh(document)
        await session.refresh(analysis)
    return document, analysis


async def make_due(session, document):
    await session.refresh(document)
    document.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()


def test_success_persists_results_and_duplicate_delivery_does_not_repeat(workflow_settings):
    async def scenario():
        engine = create_async_engine(workflow_settings.database_url)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                document, analysis = await prepare(workflow_settings, "extract", session)
                for stage in ("extract", "analyze"):
                    assert await runtime.run_stage(str(document.id), stage) == "succeeded"
                    assert await runtime.run_stage(str(document.id), stage) == "skipped"
                await session.refresh(document)
                await session.refresh(analysis)
                assert document.status is DocumentStatus.COMPLETED
                assert analysis.status is AnalysisStatus.COMPLETED
                assert analysis.started_at is not None and analysis.completed_at is not None
                assert document.next_attempt_at is None
                assert len(list(await session.scalars(select(Match)))) == 1
                assert await runtime.dispatch_pending(lambda *_: pytest.fail("terminal job")) == 0
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["extract", "analyze"])
def test_repeated_worker_loss_cannot_reset_the_retry_budget(workflow_settings, monkeypatch, stage):
    attempts = []

    async def stopped(*_):
        attempts.append(1)
        raise WorkerStopped()

    async def scenario():
        engine = create_async_engine(workflow_settings.database_url)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                document, analysis = await prepare(workflow_settings, stage, session)
                operation_name = "extract_document" if stage == "extract" else "analyze_document"
                monkeypatch.setattr(runtime, operation_name, stopped)
                for attempt in range(workflow_settings.task_max_retries + 1):
                    with pytest.raises(WorkerStopped):
                        await runtime.run_stage(str(document.id), stage)
                    await session.refresh(document)
                    assert document.processing_attempts == attempt + 1
                    assert await runtime.run_stage(str(document.id), stage) == "waiting"
                    await make_due(session, document)
                assert await runtime.run_stage(str(document.id), stage) == "failed"
                await session.refresh(document)
                await session.refresh(analysis)
                assert len(attempts) == workflow_settings.task_max_retries + 1
                assert document.status is DocumentStatus.FAILED
                assert analysis.status is AnalysisStatus.FAILED
                assert document.failure_reason == analysis.failure_reason == "retry_exhausted"
                assert document.next_attempt_at is None
                assert (
                    await runtime.dispatch_pending(lambda *_: pytest.fail("budget exhausted")) == 0
                )
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["extract", "analyze"])
def test_soft_timeout_fails_safely_and_manual_retry_recovers(workflow_settings, monkeypatch, stage):
    from intihal_api.jobs.workflow import retry_document

    operation_name = "extract_document" if stage == "extract" else "analyze_document"
    original = getattr(runtime, operation_name)

    async def timeout(*_):
        raise SoftTimeLimitExceeded()

    async def scenario():
        engine = create_async_engine(workflow_settings.database_url)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                document, analysis = await prepare(workflow_settings, stage, session)
                monkeypatch.setattr(runtime, operation_name, timeout)
                assert await runtime.run_stage(str(document.id), stage) == "failed"
                await session.refresh(document)
                await session.refresh(analysis)
                assert document.status is DocumentStatus.FAILED
                assert analysis.status is AnalysisStatus.FAILED
                assert document.failure_reason == analysis.failure_reason == "processing_timeout"
                assert document.processing_attempts == 1
                assert document.next_attempt_at is None
                assert analysis.completed_at is not None
                assert await runtime.dispatch_pending(lambda *_: pytest.fail("timed out job")) == 0
                new = await retry_document(document, analysis, session, workflow_settings)
                assert new.id != analysis.id
                assert await runtime.run_stage(str(document.id), "extract") == "waiting"
                await make_due(session, document)
                monkeypatch.setattr(runtime, operation_name, original)
                assert await runtime.run_stage(str(document.id), "extract") == "succeeded"
                assert await runtime.run_stage(str(document.id), "analyze") == "succeeded"
                await session.refresh(new)
                await session.refresh(analysis)
                assert new.status is AnalysisStatus.COMPLETED
                assert analysis.failure_reason == "processing_timeout"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["extract", "analyze"])
def test_worker_interruption_recovers_from_durable_state(workflow_settings, monkeypatch, stage):
    operation_name = "extract_document" if stage == "extract" else "analyze_document"
    original = getattr(runtime, operation_name)

    async def interrupted(document, analysis, session, *_):
        if stage == "extract":
            transition_document(document, DocumentStatus.EXTRACTING)
            analysis.status = AnalysisStatus.PROCESSING
            analysis.started_at = datetime.now(UTC)
            await session.commit()  # worker disappears after durable progress
        raise WorkerStopped()

    async def scenario():
        engine = create_async_engine(workflow_settings.database_url)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                document, analysis = await prepare(workflow_settings, stage, session)
                monkeypatch.setattr(runtime, operation_name, interrupted)
                with pytest.raises(WorkerStopped):
                    await runtime.run_stage(str(document.id), stage)
                await session.refresh(document)
                assert document.status is (
                    DocumentStatus.EXTRACTING if stage == "extract" else DocumentStatus.ANALYZING
                )
                assert document.processing_attempts == 1
                assert document.next_attempt_at > datetime.now(UTC)
                assert await runtime.run_stage(str(document.id), stage) == "waiting"
                assert await runtime.dispatch_pending(lambda *_: pytest.fail("too early")) == 0
                await make_due(session, document)
                published = []
                assert await runtime.dispatch_pending(lambda *job: published.append(job)) == 1
                expected_task = (
                    "intihal.documents.extract" if stage == "extract" else "intihal.analysis.run"
                )
                assert published == [(expected_task, str(document.id))]
                monkeypatch.setattr(runtime, operation_name, original)
                assert await runtime.run_stage(str(document.id), stage) == "succeeded"
                if stage == "extract":
                    assert await runtime.run_stage(str(document.id), "analyze") == "succeeded"
                await session.refresh(analysis)
                assert analysis.status is AnalysisStatus.COMPLETED
                assert len(list(await session.scalars(select(Analysis)))) == 1
                assert len(list(await session.scalars(select(Match)))) == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("recover", [False, True])
def test_transient_retry_respects_due_time_and_budget(workflow_settings, monkeypatch, recover):
    original = runtime.extract_document
    attempts = []

    async def offline(*args):
        attempts.append(1)
        raise StorageConnectionError("simulated service interruption")

    monkeypatch.setattr(runtime, "get_exponential_backoff_interval", lambda **_: 10)

    async def scenario():
        engine = create_async_engine(workflow_settings.database_url)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                document, analysis = await prepare(workflow_settings, "extract", session)
                monkeypatch.setattr(runtime, "extract_document", offline)
                count = 1 if recover else workflow_settings.task_max_retries + 1
                for attempt in range(count):
                    before = datetime.now(UTC)
                    result = await runtime.run_stage(str(document.id), "extract")
                    await session.refresh(document)
                    assert document.processing_attempts == attempt + 1
                    if attempt < workflow_settings.task_max_retries:
                        assert result == "retry_scheduled"
                        assert document.next_attempt_at >= before + timedelta(seconds=10)
                        assert await runtime.run_stage(str(document.id), "extract") == "waiting"
                        assert len(attempts) == attempt + 1
                        await make_due(session, document)
                    else:
                        assert result == "failed"
                if recover:
                    monkeypatch.setattr(runtime, "extract_document", original)
                    assert await runtime.run_stage(str(document.id), "extract") == "succeeded"
                    assert await runtime.run_stage(str(document.id), "analyze") == "succeeded"
                    await session.refresh(analysis)
                    assert analysis.status is AnalysisStatus.COMPLETED
                else:
                    await session.refresh(analysis)
                    assert document.failure_reason == analysis.failure_reason == "retry_exhausted"
                    assert document.status is DocumentStatus.FAILED
                    assert analysis.status is AnalysisStatus.FAILED
                    assert document.next_attempt_at is None
                    assert await runtime.run_stage(str(document.id), "extract") == "skipped"
                    assert len(attempts) == 4
        finally:
            await engine.dispose()

    asyncio.run(scenario())
