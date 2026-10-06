import asyncio
from datetime import UTC, datetime, timedelta
from hashlib import blake2b, sha256
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from intihal_api.core.config import Settings
from intihal_api.db.models import Analysis, Document, DocumentStatus, Match, User
from intihal_api.db.session import get_db_session
from intihal_api.jobs import runtime
from intihal_api.jobs.workflow import queue_document
from intihal_api.main import create_app
from intihal_api.storage import StorageConnectionError
from test_document_workflow import CONTENT, StoredContent, seed_source
from test_migrations import require_test_database_url, run_alembic


@pytest.fixture
def workflow_database(monkeypatch):
    url = require_test_database_url()
    run_alembic(url, "downgrade", "base")
    run_alembic(url, "upgrade", "head")
    settings = Settings(_env_file=None, database_url=url)
    monkeypatch.setattr(runtime, "get_settings", lambda: settings)
    try:
        yield settings
    finally:
        run_alembic(url, "downgrade", "base")


async def seed_document(session):
    owner = User(id=uuid4(), email=f"{uuid4()}@test.example", display_name="Test")
    session.add(owner)
    await session.flush()
    content = CONTENT.encode()
    document = Document(
        id=uuid4(),
        owner_id=owner.id,
        original_filename="test.txt",
        content_type="text/plain",
        size_bytes=len(content),
        sha256=sha256(content).hexdigest(),
        storage_bucket="intihal-documents",
        storage_key="documents/test",
        status=DocumentStatus.UPLOADED,
    )
    session.add(document)
    await session.commit()
    return document


def test_postgres_worker_lock_dispatch_and_completion(workflow_database, monkeypatch):
    storage = StoredContent()
    storage.bucket_name = "intihal-documents"
    monkeypatch.setattr(runtime, "create_object_storage_service", lambda _: storage)

    async def scenario():
        engine = create_async_engine(workflow_database.database_url)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                document = await seed_document(session)
                await seed_source(session)
                await queue_document(document, session, workflow_database)
                key = int.from_bytes(
                    blake2b(document.id.bytes, digest_size=8).digest(), signed=True
                )
                async with engine.connect() as blocker:
                    await blocker.execute(text("SELECT pg_advisory_lock(:key)"), {"key": key})
                    assert await runtime.run_stage(str(document.id), "extract") == "already_running"
                    await blocker.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
                published = []
                assert await runtime.dispatch_pending(lambda *job: published.append(job)) == 1
                assert published == [("intihal.documents.extract", str(document.id))]
                assert await runtime.run_stage(str(document.id), "extract") == "succeeded"
                assert await runtime.run_stage(str(document.id), "extract") == "skipped"
                published.clear()
                await runtime.dispatch_pending(lambda *job: published.append(job))
                assert published == [("intihal.analysis.run", str(document.id))]
                assert await runtime.run_stage(str(document.id), "analyze") == "succeeded"
                assert await runtime.run_stage(str(document.id), "analyze") == "skipped"
                await session.refresh(document)
                assert document.status is DocumentStatus.COMPLETED
                assert len(list(await session.scalars(select(Match)))) == 1
                assert await runtime.dispatch_pending(lambda *job: published.append(job)) == 0
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_concurrent_start_and_retry_create_one_run(workflow_database):
    async def scenario():
        engine = create_async_engine(workflow_database.database_url)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                document = await seed_document(session)
                application = create_app()

                async def request_session():
                    async with AsyncSession(engine, expire_on_commit=False) as current:
                        yield current

                application.dependency_overrides[get_db_session] = request_session
                async with AsyncClient(
                    transport=ASGITransport(app=application), base_url="http://test"
                ) as client:
                    headers = {"X-User-ID": str(document.owner_id)}
                    starts = await asyncio.gather(
                        client.post(
                            "/api/v1/analyses",
                            json={"document_id": str(document.id)},
                            headers=headers,
                        ),
                        client.post(f"/api/v1/documents/{document.id}/analysis", headers=headers),
                    )
                    assert all(r.status_code == 202 for r in starts)
                    assert starts[0].json()["id"] == starts[1].json()["id"]
                    original = await session.scalar(select(Analysis))
                    await session.refresh(document)
                    await runtime.fail_document(document, original, session, "retry_exhausted")
                    path = f"/api/v1/analyses/{original.id}/retry"
                    retried = await asyncio.gather(
                        client.post(path, headers=headers), client.post(path, headers=headers)
                    )
                    assert all(r.status_code == 202 for r in retried)
                    assert retried[0].json()["id"] == retried[1].json()["id"]
                    assert retried[0].json()["id"] != str(original.id)
                    assert len(list(await session.scalars(select(Analysis)))) == 2
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_durable_retries_are_bounded(workflow_database, monkeypatch):
    class OfflineStorage:
        bucket_name = "intihal-documents"

        def download_object(self, key):
            raise StorageConnectionError("offline")

    monkeypatch.setattr(runtime, "create_object_storage_service", lambda _: OfflineStorage())

    async def scenario():
        engine = create_async_engine(workflow_database.database_url)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                document = await seed_document(session)
                await queue_document(document, session, workflow_database)
                for attempt in range(4):
                    result = await runtime.run_stage(str(document.id), "extract")
                    assert result == ("retry_scheduled" if attempt < 3 else "failed")
                    await session.refresh(document)
                    assert document.processing_attempts == attempt + 1
                    if attempt < 3:
                        document.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
                        await session.commit()
                assert document.status is DocumentStatus.FAILED
                assert document.failure_reason == "retry_exhausted"
                assert await runtime.run_stage(str(document.id), "extract") == "skipped"
        finally:
            await engine.dispose()

    asyncio.run(scenario())
