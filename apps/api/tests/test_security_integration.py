"""Real PostgreSQL row locks and real MinIO deletion, using disposable fixtures only."""

import asyncio
import os
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from minio.error import S3Error
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from auth_helpers import session_headers
from intihal_api.core.config import get_settings
from intihal_api.core.security import token_digest
from intihal_api.corpus import SourceDocumentIngestionService, SourceMetadata
from intihal_api.db.models import (
    Analysis,
    AuditEvent,
    DocumentChunk,
    DocumentStatus,
    LicenseStatus,
    Match,
    SourceChunk,
    User,
    UserRole,
    UserSession,
)
from intihal_api.db.session import get_db_session
from intihal_api.jobs import runtime
from intihal_api.jobs.workflow import analyze_document, extract_document
from intihal_api.main import create_app
from intihal_api.storage import StorageConnectionError, create_object_storage_service
from intihal_api.uploads import DocumentUploadService
from test_migrations import run_alembic
from test_security_regressions import protected_operations

CONTENT = b"Synthetic security test document with repeated comparison words."


@dataclass(repr=False)
class Environment:
    settings: object
    storage: object


@pytest.fixture
def isolated_environment(monkeypatch):
    url = os.getenv("INTIHAL_SECURITY_TEST_DATABASE_URL")
    bucket = os.getenv("INTIHAL_SECURITY_TEST_MINIO_BUCKET")
    if not url or not bucket:
        pytest.skip(
            "Run tests/run_security_integration.py for disposable PostgreSQL/MinIO fixtures"
        )
    if not re.fullmatch(
        r"intihal_security_test_[0-9a-f]{32}", make_url(url).database or ""
    ) or not re.fullmatch(r"intihal-security-test-[0-9a-f]{32}", bucket):
        pytest.fail("Refusing security test against resources outside the disposable namespace")
    run_alembic(url, "downgrade", "base")
    run_alembic(url, "upgrade", "head")
    settings = get_settings().model_copy(update={"database_url": url, "minio_bucket": bucket})
    monkeypatch.setattr(runtime, "get_settings", lambda: settings)
    return Environment(settings, create_object_storage_service(settings))


@asynccontextmanager
async def actual_api(environment):
    engine = create_async_engine(environment.settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    storage = environment.storage
    try:
        async with factory() as session:
            owner = User(id=uuid4(), email="owner@security.test", display_name="Synthetic owner")
            other = User(id=uuid4(), email="other@security.test", display_name="Synthetic other")
            session.add_all([owner, other])
            await session.commit()
            doc = await DocumentUploadService(storage).create_document(
                owner_id=owner.id,
                filename="synthetic-test.txt",
                content_type="text/plain",
                stream=BytesIO(CONTENT),
                session=session,
            )
            source = await SourceDocumentIngestionService(storage).create_source(
                metadata=SourceMetadata(
                    title="Synthetic source",
                    license_name="CC0",
                    rights_holder="Test",
                    license_evidence_reference="test-only",
                ),
                filename="synthetic-source.txt",
                content_type="text/plain",
                stream=BytesIO(CONTENT),
                session=session,
            )
            source.license_status = LicenseStatus.APPROVED
            await session.commit()
            headers = await session_headers(session, owner.id)
            other_headers = await session_headers(session, other.id)
            fault = {"commit": False}
            app = create_app(storage_service=storage)

            async def db():
                async with factory() as request_session:
                    real_commit = request_session.commit
                    commits = 0

                    async def commit():
                        nonlocal commits
                        commits += 1
                        if fault["commit"] and commits == 2:
                            raise RuntimeError("Synthetic database failure after blob removal")
                        await real_commit()

                    request_session.commit = commit
                    try:
                        yield request_session
                    except Exception:
                        await request_session.rollback()
                        raise

            app.dependency_overrides[get_db_session] = db
            async with app.router.lifespan_context(app):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    started = await client.post(
                        f"/api/v1/documents/{doc.id}/analysis", headers=headers
                    )
                    assert started.status_code == 202
                    await session.refresh(doc)
                    analysis = await session.get(Analysis, UUID(started.json()["id"]))
                    await extract_document(doc, analysis, session, storage)
                    await analyze_document(doc, analysis, session, environment.settings)
                    assert await session.scalar(select(func.count()).select_from(Match)) == 1
                    yield (
                        client,
                        session,
                        doc,
                        analysis,
                        source,
                        headers,
                        other_headers,
                        other,
                        fault,
                    )
    finally:
        await engine.dispose()


def assert_blob_missing(storage, key):
    with pytest.raises(S3Error) as error:
        storage.client.stat_object(storage.bucket_name, key)
    assert error.value.code == "NoSuchKey"


async def assert_permanent_cleanup(session, storage, doc, analysis, source):
    await session.refresh(doc)
    assert doc.status is DocumentStatus.DELETED and doc.cleaned_at is not None
    assert_blob_missing(storage, doc.storage_key)
    assert storage.download_object(source.storage_key) == CONTENT
    assert await session.scalar(select(func.count()).select_from(DocumentChunk)) == 0
    assert await session.scalar(select(func.count()).select_from(Analysis)) == 0
    assert await session.scalar(select(func.count()).select_from(Match)) == 0
    assert await session.scalar(select(func.count()).select_from(SourceChunk)) == 1
    records = list(
        await session.scalars(
            select(AuditEvent).where(
                AuditEvent.resource_id == doc.id, AuditEvent.action == "document.delete"
            )
        )
    )
    assert sorted(event.outcome for event in records) == ["started", "succeeded"]


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.ADMIN])
def test_real_foreign_access_and_forged_owner_header_are_denied(isolated_environment, role):
    async def scenario():
        async with actual_api(isolated_environment) as context:
            client, session, doc, analysis, _, owner, other_headers, other, _ = context
            other.role = role
            await session.commit()
            attack = {**other_headers, "X-User-ID": str(doc.owner_id)}
            for method, path, payload in protected_operations(doc.id, analysis.id)[2:]:
                assert (
                    await client.request(method, path, headers=attack, json=payload)
                ).status_code == 404
            assert (await client.get("/api/v1/documents", headers=attack)).json() == []
            assert isolated_environment.storage.download_object(doc.storage_key) == CONTENT
            settings = isolated_environment.settings
            scheme = "https" if settings.minio_secure else "http"
            object_url = (
                f"{scheme}://{settings.minio_endpoint}/{settings.minio_bucket}/{doc.storage_key}"
            )
            async with AsyncClient(trust_env=False) as anonymous:
                denied = await anonymous.get(object_url)
            assert denied.status_code == 403 and CONTENT not in denied.content
            assert (
                await client.get(f"/api/v1/analyses/{analysis.id}/matches", headers=owner)
            ).json()["total"] == 1

    asyncio.run(scenario())


def test_real_session_digest_replay_logout_revocation_and_expiry(isolated_environment, caplog):
    async def scenario():
        async with actual_api(isolated_environment) as context:
            client, session, doc, analysis, _, headers, other_headers, _, _ = context
            name = get_settings().session_cookie_name
            raw = headers["Cookie"].split("=", 1)[1]
            credential = await session.scalar(
                select(UserSession).where(UserSession.token_hash == token_digest(raw))
            )
            assert credential is not None and credential.token_hash != raw
            assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 200
            for candidate in (credential.token_hash, ("A" if raw[0] != "A" else "B") + raw[1:]):
                attack = {**headers, "Cookie": f"{name}={candidate}"}
                for method, path, payload in protected_operations(doc.id, analysis.id):
                    assert (
                        await client.request(method, path, headers=attack, json=payload)
                    ).status_code == 401
            assert (await client.post("/api/v1/auth/logout", headers=headers)).status_code == 204
            for method, path, payload in protected_operations(doc.id, analysis.id):
                assert (
                    await client.request(method, path, headers=headers, json=payload)
                ).status_code == 401
            assert (await client.get("/api/v1/auth/me", headers=other_headers)).status_code == 200
            other_raw = other_headers["Cookie"].split("=", 1)[1]
            other_session = await session.scalar(
                select(UserSession).where(UserSession.token_hash == token_digest(other_raw))
            )
            other_session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()
            assert (await client.get("/api/v1/auth/me", headers=other_headers)).status_code == 401
            assert isolated_environment.storage.download_object(doc.storage_key) == CONTENT
            assert await session.scalar(select(func.count()).select_from(Match)) == 1
            assert raw not in caplog.text and other_raw not in caplog.text

    asyncio.run(scenario())


def test_real_concurrent_deletion_is_permanent_and_stale_worker_cannot_recreate_data(
    isolated_environment,
    monkeypatch,
):
    async def scenario():
        async with actual_api(isolated_environment) as context:
            client, session, doc, analysis, source, headers, _, _, _ = context
            storage = isolated_environment.storage
            barrier = Barrier(2)
            remove = storage.remove_object

            def simultaneous_remove(key):
                barrier.wait(timeout=10)
                remove(key)

            monkeypatch.setattr(storage, "remove_object", simultaneous_remove)
            url = f"/api/v1/documents/{doc.id}"
            responses = await asyncio.wait_for(
                asyncio.gather(
                    client.delete(url, headers=headers), client.delete(url, headers=headers)
                ),
                timeout=20,
            )
            assert [response.status_code for response in responses] == [204, 204]
            await assert_permanent_cleanup(session, storage, doc, analysis, source)
            assert (await client.delete(url, headers=headers)).status_code == 204
            assert await runtime.run_stage(str(doc.id), "extract") == "skipped"
            assert await runtime.run_stage(str(doc.id), "analyze") == "skipped"
            assert (
                await runtime.dispatch_pending(
                    lambda *_: pytest.fail("Deleted document dispatched")
                )
                == 0
            )
            await assert_permanent_cleanup(session, storage, doc, analysis, source)
            for method, path, payload in protected_operations(doc.id, analysis.id)[2:-1]:
                assert (
                    await client.request(method, path, headers=headers, json=payload)
                ).status_code == 404

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["storage", "database"])
def test_real_cleanup_recovers_after_storage_or_database_failure(
    isolated_environment, monkeypatch, failure
):
    async def scenario():
        async with actual_api(isolated_environment) as context:
            client, session, doc, analysis, source, headers, other, _, fault = context
            storage = isolated_environment.storage
            remove = storage.remove_object
            if failure == "storage":

                def fail(key):
                    raise StorageConnectionError("Synthetic storage failure")

                monkeypatch.setattr(storage, "remove_object", fail)
            else:
                fault["commit"] = True
            url = f"/api/v1/documents/{doc.id}"
            failed = await client.delete(url, headers=headers)
            assert failed.status_code == (503 if failure == "storage" else 500)
            await session.refresh(doc)
            assert doc.status is DocumentStatus.DELETED and doc.cleaned_at is None
            assert await session.get(Analysis, analysis.id) is not None
            assert await session.scalar(select(func.count()).select_from(Match)) == 1
            if failure == "storage":
                assert storage.download_object(doc.storage_key) == CONTENT
            else:
                assert_blob_missing(storage, doc.storage_key)
            assert (await client.get(url, headers=headers)).status_code == 404
            assert (await client.delete(url, headers=other)).status_code == 404
            fault["commit"] = False
            monkeypatch.setattr(storage, "remove_object", remove)
            assert (await client.delete(url, headers=headers)).status_code == 204
            await assert_permanent_cleanup(session, storage, doc, analysis, source)

    asyncio.run(scenario())
