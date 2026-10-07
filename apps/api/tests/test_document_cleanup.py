import asyncio
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from auth_helpers import session_headers
from intihal_api.api.dependencies import get_object_storage
from intihal_api.core.config import Settings
from intihal_api.db.models import (
    Analysis,
    Document,
    DocumentChunk,
    DocumentStatus,
    Match,
    SourceChunk,
    SourceDocument,
    User,
    UserRole,
)
from intihal_api.db.session import get_db_session
from intihal_api.jobs.workflow import analyze_document, extract_document
from intihal_api.main import create_app
from intihal_api.storage import StorageConnectionError, build_document_storage_key
from test_document_workflow import StoredContent, database, seed_source


class CleanupStorage:
    bucket_name = "intihal-documents"

    def __init__(self, key):
        self.objects = {key: b"document", "sources/keep": b"corpus"}
        self.removed = []
        self.fail = False

    def remove_object(self, key):
        if self.fail:
            raise StorageConnectionError("unavailable")
        self.removed.append(key)
        self.objects.pop(key, None)  # S3 deletion of a missing key is idempotent.


@asynccontextmanager
async def cleanup_api():
    async with database() as (session, document, factory):
        document.storage_key = build_document_storage_key(document.owner_id, document.id)
        other = User(id=uuid4(), email="other@cleanup.test", display_name="Other")
        session.add(other)
        await session.commit()
        headers = await session_headers(session, document.owner_id)
        other_headers = await session_headers(session, other.id)
        storage = CleanupStorage(document.storage_key)
        fault = {"fail_commit": False}
        application = create_app()

        async def override_session():
            async with factory() as request_session:
                real_commit = request_session.commit
                commits = 0

                async def commit():
                    nonlocal commits
                    commits += 1
                    if fault["fail_commit"] and commits == 2:
                        raise RuntimeError("database commit interrupted")
                    await real_commit()

                request_session.commit = commit
                try:
                    yield request_session
                except Exception:
                    await request_session.rollback()
                    raise

        application.dependency_overrides[get_db_session] = override_session
        application.dependency_overrides[get_object_storage] = lambda: storage
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            yield client, session, document, headers, other_headers, storage, fault


async def completed_document(client, session, document, headers):
    await seed_source(session)
    created = await client.post(
        "/api/v1/analyses", headers=headers, json={"document_id": str(document.id)}
    )
    analysis = await session.get(Analysis, UUID(created.json()["id"]))
    await session.refresh(document)
    await extract_document(document, analysis, session, StoredContent())
    await analyze_document(document, analysis, session, Settings(_env_file=None))
    return analysis


async def counts(session):
    return tuple(
        [
            await session.scalar(select(func.count()).select_from(model))
            for model in (DocumentChunk, Analysis, Match, SourceDocument, SourceChunk)
        ]
    )


def test_cleanup_removes_only_document_data_and_is_repeatable():
    async def scenario():
        async with cleanup_api() as (client, session, document, headers, _, storage, _):
            analysis = await completed_document(client, session, document, headers)
            before = await counts(session)
            assert before[:3] == (1, 1, 1)
            url = f"/api/v1/documents/{document.id}"
            result = await client.delete(url, headers=headers)
            assert result.status_code == 204 and result.text == ""
            await session.refresh(document)
            assert document.status is DocumentStatus.DELETED
            assert await counts(session) == (0, 0, 0, *before[3:])
            assert storage.objects == {"sources/keep": b"corpus"}
            assert (await client.get(url, headers=headers)).status_code == 404
            assert (
                await client.get(f"/api/v1/analyses/{analysis.id}", headers=headers)
            ).status_code == 404
            assert (await client.get("/api/v1/documents", headers=headers)).json() == []
            assert (await client.delete(url, headers=headers)).status_code == 204

    asyncio.run(scenario())


def test_storage_failure_hides_data_but_preserves_cleanup_for_retry():
    async def scenario():
        async with cleanup_api() as (client, session, document, headers, _, storage, _):
            analysis = await completed_document(client, session, document, headers)
            before = await counts(session)
            storage.fail = True
            url = f"/api/v1/documents/{document.id}"
            failed = await client.delete(url, headers=headers)
            assert failed.status_code == 503
            assert failed.json()["detail"]["code"] == "document_cleanup_pending"
            await session.refresh(document)
            assert document.status is DocumentStatus.DELETED
            assert await counts(session) == before
            assert document.storage_key in storage.objects
            assert (
                await client.get(f"/api/v1/analyses/{analysis.id}/matches", headers=headers)
            ).status_code == 404
            storage.fail = False
            assert (await client.delete(url, headers=headers)).status_code == 204
            assert (await counts(session))[:3] == (0, 0, 0)

    asyncio.run(scenario())


def test_database_failure_after_object_removal_rolls_back_rows_and_can_resume():
    async def scenario():
        async with cleanup_api() as (client, session, document, headers, _, storage, fault):
            await completed_document(client, session, document, headers)
            before = await counts(session)
            fault["fail_commit"] = True
            url = f"/api/v1/documents/{document.id}"
            assert (await client.delete(url, headers=headers)).status_code == 500
            await session.refresh(document)
            assert document.status is DocumentStatus.DELETED
            assert document.storage_key not in storage.objects
            assert await counts(session) == before
            fault["fail_commit"] = False
            assert (await client.delete(url, headers=headers)).status_code == 204
            assert (await counts(session))[:3] == (0, 0, 0)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "status", [DocumentStatus.QUEUED, DocumentStatus.EXTRACTING, DocumentStatus.ANALYZING]
)
def test_active_work_cannot_be_deleted(status):
    async def scenario():
        async with cleanup_api() as (client, session, document, headers, _, storage, _):
            document.status = status
            await session.commit()
            denied = await client.delete(f"/api/v1/documents/{document.id}", headers=headers)
            assert denied.status_code == 409
            assert denied.json()["detail"]["code"] == "document_processing"
            await session.refresh(document)
            assert document.status is status and storage.removed == []

    asyncio.run(scenario())


def test_deletion_requires_owner_csrf_and_a_verified_storage_location():
    async def scenario():
        async with cleanup_api() as (client, session, document, headers, other, storage, _):
            url = f"/api/v1/documents/{document.id}"
            assert (await client.delete(url)).status_code == 401
            assert (await client.delete(url, headers=other)).status_code == 404
            other_user = await session.scalar(
                select(User).where(User.email == "other@cleanup.test")
            )
            other_user.role = UserRole.ADMIN
            await session.commit()
            assert (await client.delete(url, headers=other)).status_code == 404
            assert (
                await client.delete(url, headers={"Cookie": headers["Cookie"]})
            ).status_code == 403
            assert storage.removed == []
            document.storage_key = "sources/keep"
            await session.commit()
            denied = await client.delete(url, headers=headers)
            assert denied.status_code == 409
            assert denied.json()["detail"]["code"] == "document_storage_mismatch"
            await session.refresh(document)
            assert document.status is DocumentStatus.UPLOADED
            assert storage.removed == [] and "sources/keep" in storage.objects

    asyncio.run(scenario())


@pytest.mark.parametrize("status", [DocumentStatus.UPLOADED, DocumentStatus.FAILED])
def test_unprocessed_or_failed_documents_can_be_cleaned(status):
    async def scenario():
        async with cleanup_api() as (client, session, document, headers, _, storage, _):
            document.status = status
            await session.commit()
            assert (
                await client.delete(f"/api/v1/documents/{document.id}", headers=headers)
            ).status_code == 204
            await session.refresh(document)
            assert document.status is DocumentStatus.DELETED
            assert document.storage_key not in storage.objects

    asyncio.run(scenario())


def test_inconsistent_foreign_reference_blocks_database_cleanup_without_deleting_foreign_data():
    async def scenario():
        async with cleanup_api() as (client, session, document, headers, _, storage, _):
            await completed_document(client, session, document, headers)
            other = await session.scalar(select(User).where(User.email == "other@cleanup.test"))
            other_document = Document(
                owner_id=other.id,
                original_filename="other.txt",
                content_type="text/plain",
                size_bytes=5,
                sha256="c" * 64,
                storage_bucket="intihal-documents",
                storage_key=f"documents/{uuid4()}",
                status=DocumentStatus.COMPLETED,
            )
            session.add(other_document)
            await session.flush()
            other_analysis = Analysis(document_id=other_document.id, algorithm_version="test")
            session.add(other_analysis)
            await session.flush()
            match = await session.scalar(select(Match))
            session.add(
                Match(
                    analysis_id=other_analysis.id,
                    document_chunk_id=match.document_chunk_id,
                    source_chunk_id=match.source_chunk_id,
                    method=match.method,
                    similarity_score=match.similarity_score,
                    matched_token_count=match.matched_token_count,
                    document_match_start=match.document_match_start,
                    document_match_end=match.document_match_end,
                    source_match_start=match.source_match_start,
                    source_match_end=match.source_match_end,
                )
            )
            await session.commit()
            before = await counts(session)
            result = await client.delete(f"/api/v1/documents/{document.id}", headers=headers)
            assert result.status_code == 409
            assert result.json()["detail"]["code"] == "document_cleanup_conflict"
            assert await counts(session) == before
            await session.refresh(document)
            assert document.status is DocumentStatus.DELETED
            assert document.storage_key not in storage.objects
            assert await session.get(Analysis, other_analysis.id) is not None

    asyncio.run(scenario())
