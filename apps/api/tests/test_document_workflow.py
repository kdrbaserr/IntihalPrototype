import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from intihal_api.core.config import Settings
from intihal_api.db.base import Base
from intihal_api.db.models import (
    Analysis,
    AnalysisStatus,
    Document,
    DocumentChunk,
    DocumentStatus,
    LicenseStatus,
    Match,
    SourceChunk,
    SourceDocument,
    SourceDocumentStatus,
    User,
)
from intihal_api.db.session import get_db_session
from intihal_api.jobs.runtime import fail_document, failure_code, is_transient
from intihal_api.jobs.states import InvalidDocumentTransition, transition_document
from intihal_api.jobs.workflow import (
    AnalysisRetryError,
    analyze_document,
    extract_document,
    queue_document,
    retry_document,
)
from intihal_api.main import create_app
from intihal_api.storage import StorageAuthenticationError, StorageConnectionError

CONTENT = "Bu cümle özgün araştırma sonuçlarını açıklar."


class StoredContent:
    def __init__(self, content=None, document=None):
        self.content = CONTENT.encode() if content is None else content
        self.document = document

    def download_object(self, key):
        if self.document is not None:
            assert self.document.status is DocumentStatus.EXTRACTING
        return self.content


@asynccontextmanager
async def database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            owner = User(id=uuid4(), email="owner@test.example", display_name="Owner")
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
            yield session, document, factory
    finally:
        await engine.dispose()


async def seed_source(session, *, license_status=LicenseStatus.APPROVED, expired=False):
    identifier = uuid4()
    source = SourceDocument(
        id=identifier,
        title="Kaynak",
        status=SourceDocumentStatus.READY,
        license_status=license_status,
        license_name="CC0",
        rights_holder="Test",
        license_evidence_reference="test-evidence",
        original_filename="source.txt",
        content_type="text/plain",
        size_bytes=len(CONTENT.encode()),
        sha256=sha256(identifier.bytes).hexdigest(),
        storage_bucket="sources",
        storage_key=str(identifier),
        license_valid_until=datetime.now(UTC).date() - timedelta(days=1) if expired else None,
    )
    session.add(source)
    await session.flush()
    session.add(
        SourceChunk(
            source_document_id=identifier,
            chunk_index=0,
            content=CONTENT,
            char_start=0,
            char_end=len(CONTENT),
            token_count=7,
            content_sha256=sha256(CONTENT.encode()).hexdigest(),
        )
    )
    await session.commit()
    return identifier


def test_workflow_persists_states_evidence_and_is_idempotent():
    async def scenario():
        async with database() as (session, document, _):
            settings = Settings(_env_file=None)
            approved = await seed_source(session)
            await seed_source(session, license_status=LicenseStatus.REJECTED)
            await seed_source(session, expired=True)
            analysis = await queue_document(document, session, settings)
            assert document.status is DocumentStatus.QUEUED
            assert (await queue_document(document, session, settings)).id == analysis.id
            await extract_document(document, analysis, session, StoredContent(document=document))
            assert document.status is DocumentStatus.ANALYZING
            assert analysis.status is AnalysisStatus.PROCESSING
            assert list(await session.scalars(select(DocumentChunk)))
            await analyze_document(document, analysis, session, settings)
            assert document.status is DocumentStatus.COMPLETED
            assert analysis.status is AnalysisStatus.COMPLETED
            matches = list(await session.scalars(select(Match)))
            assert len(matches) == 1
            match = matches[0]
            source_chunk = await session.get(SourceChunk, match.source_chunk_id)
            assert source_chunk.source_document_id == approved
            assert match.similarity_score == Decimal("1.0000")
            assert CONTENT[match.document_match_start : match.document_match_end] == CONTENT[:-1]
            assert document.next_attempt_at is None
            assert (await queue_document(document, session, settings)).id == analysis.id
            assert len(list(await session.scalars(select(Analysis)))) == 1

    asyncio.run(scenario())


def test_failed_workflow_can_start_a_new_run_without_faking_completion():
    async def scenario():
        async with database() as (session, document, _):
            settings = Settings(_env_file=None)
            original = await queue_document(document, session, settings)
            with pytest.raises(ValueError, match="stored_document_changed"):
                await extract_document(document, original, session, StoredContent(b"changed"))
            assert document.status is DocumentStatus.EXTRACTING
            await fail_document(document, original, session, "stored_document_changed")
            assert document.status is DocumentStatus.FAILED
            assert original.status is AnalysisStatus.FAILED
            assert (await queue_document(document, session, settings)).id == original.id
            with pytest.raises(AnalysisRetryError, match="analysis_retry_not_allowed"):
                await retry_document(document, original, session, settings)
            document.failure_reason = original.failure_reason = "processing_failed"
            await session.commit()
            new = await retry_document(document, original, session, settings)
            assert new.id != original.id
            assert document.failure_reason is None
            await extract_document(document, new, session, StoredContent())
            await analyze_document(document, new, session, settings)
            assert document.status is DocumentStatus.COMPLETED  # no eligible corpus is valid
            assert list(await session.scalars(select(Match))) == []

    asyncio.run(scenario())


def test_completion_and_matches_roll_back_together():
    class BrokenCommitSession(AsyncSession):
        async def commit(self):
            await self.flush()
            raise RuntimeError("commit interrupted")

    async def scenario():
        async with database() as (session, document, factory):
            settings = Settings(_env_file=None)
            await seed_source(session)
            analysis = await queue_document(document, session, settings)
            await extract_document(document, analysis, session, StoredContent())
            async with BrokenCommitSession(factory.kw["bind"], expire_on_commit=False) as broken:
                loaded_document = await broken.get(Document, document.id)
                loaded_analysis = await broken.get(Analysis, analysis.id)
                with pytest.raises(RuntimeError, match="commit interrupted"):
                    await analyze_document(loaded_document, loaded_analysis, broken, settings)
                await broken.rollback()
            await session.refresh(document)
            await session.refresh(analysis)
            assert document.status is DocumentStatus.ANALYZING
            assert analysis.status is AnalysisStatus.PROCESSING
            assert list(await session.scalars(select(Match))) == []

    asyncio.run(scenario())


def test_status_and_start_endpoints_enforce_ownership_and_repeat_safety():
    async def scenario():
        async with database() as (session, document, factory):
            other = User(id=uuid4(), email="other@test.example", display_name="Other")
            session.add(other)
            await session.commit()
            application = create_app()

            async def override_session():
                async with factory() as request_session:
                    yield request_session

            application.dependency_overrides[get_db_session] = override_session
            async with AsyncClient(
                transport=ASGITransport(app=application), base_url="http://test"
            ) as client:
                url = f"/api/v1/documents/{document.id}"
                owner_headers = {"X-User-ID": str(document.owner_id)}
                other_headers = {"X-User-ID": str(other.id)}
                assert (await client.get(url, headers=other_headers)).status_code == 404
                assert (
                    await client.post(url + "/analysis", headers=other_headers)
                ).status_code == 404
                assert (await client.post(url + "/analysis")).status_code == 401
                first = await client.post(url + "/analysis", headers=owner_headers)
                second = await client.post(url + "/analysis", headers=owner_headers)
                assert first.status_code == second.status_code == 202
                assert first.json()["id"] == second.json()["id"]
                assert (await client.get(url, headers=owner_headers)).json()["status"] == "queued"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "current,target",
    [
        (DocumentStatus.UPLOADED, DocumentStatus.COMPLETED),
        (DocumentStatus.QUEUED, DocumentStatus.ANALYZING),
        (DocumentStatus.EXTRACTING, DocumentStatus.COMPLETED),
        (DocumentStatus.COMPLETED, DocumentStatus.QUEUED),
    ],
)
def test_invalid_transitions_are_rejected(current, target):
    document = Document(status=current)
    with pytest.raises(InvalidDocumentTransition):
        transition_document(document, target)
    assert document.status is current


def test_error_classification_does_not_leak_credentials():
    assert is_transient(StorageConnectionError("network"))
    assert not is_transient(StorageAuthenticationError("secret credential"))
    assert failure_code(RuntimeError("secret credential")) == "processing_failed"
