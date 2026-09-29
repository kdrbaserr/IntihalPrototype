from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from intihal_api.db.models import SourceChunk, SourceDocument, User, UserRole
from intihal_api.db.session import get_db_session
from intihal_api.main import create_app
from intihal_api.storage import ObjectStorageService

API_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_ENV = "INTIHAL_TEST_DATABASE_URL"
ADMIN_ID = UUID("11111111-1111-1111-1111-111111111111")
USER_ID = UUID("22222222-2222-2222-2222-222222222222")


class FakeWriteResult:
    etag = "source-etag"


class FakeReadResult:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.closed = False
        self.released = False

    def read(self) -> bytes:
        return self.content

    def close(self) -> None:
        self.closed = True

    def release_conn(self) -> None:
        self.released = True


class FakeMinioClient:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def bucket_exists(self, bucket_name: str) -> bool:
        return True

    def make_bucket(self, bucket_name: str) -> None:
        raise AssertionError("Existing test bucket must not be recreated")

    def put_object(
        self,
        bucket_name: str,
        object_name: str,
        data: BinaryIO,
        length: int,
        content_type: str = "application/octet-stream",
    ) -> FakeWriteResult:
        content = data.read()
        assert len(content) == length
        self.objects[object_name] = content
        return FakeWriteResult()

    def get_object(self, bucket_name: str, object_name: str) -> FakeReadResult:
        return FakeReadResult(self.objects[object_name])

    def remove_object(self, bucket_name: str, object_name: str) -> None:
        self.objects.pop(object_name, None)


def require_test_database_url() -> str:
    database_url = os.getenv(TEST_DATABASE_ENV)
    if database_url is None:
        pytest.skip(f"{TEST_DATABASE_ENV} is not configured")
    database_name = make_url(database_url).database or ""
    if "test" not in database_name.lower():
        pytest.fail(f"Refusing admin API test against non-test database: {database_name!r}")
    return database_url


def run_alembic(database_url: str, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["INTIHAL_DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=API_DIR,
        env=environment,
        check=True,
    )


@pytest.fixture
def migrated_admin_database_url() -> Iterator[str]:
    database_url = require_test_database_url()
    run_alembic(database_url, "downgrade", "base")
    run_alembic(database_url, "upgrade", "head")
    try:
        yield database_url
    finally:
        run_alembic(database_url, "downgrade", "base")


@pytest.mark.anyio
async def test_admin_can_add_list_reindex_and_disable_source(
    migrated_admin_database_url: str,
) -> None:
    engine = create_async_engine(migrated_admin_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    minio_client = FakeMinioClient()
    storage = ObjectStorageService(minio_client, "intihal-documents")
    application = create_app(storage_service=storage)

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_db_session] = override_db_session

    try:
        async with session_factory() as session:
            session.add_all(
                [
                    User(
                        id=ADMIN_ID,
                        email="admin@example.com",
                        display_name="Admin",
                        role=UserRole.ADMIN,
                    ),
                    User(
                        id=USER_ID,
                        email="user@example.com",
                        display_name="User",
                    ),
                ]
            )
            await session.commit()

        async with application.router.lifespan_context(application):
            transport = ASGITransport(app=application)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                forbidden = await client.get(
                    "/api/v1/admin/sources",
                    headers={"X-User-ID": str(USER_ID)},
                )
                assert forbidden.status_code == 403
                assert forbidden.json()["detail"]["code"] == "admin_required"

                missing_permission = await client.post(
                    "/api/v1/admin/sources",
                    headers={"X-User-ID": str(ADMIN_ID)},
                    data={
                        "title": "Eksik İzinli Kaynak",
                        "license_name": "CC BY 4.0",
                        "rights_holder": "Örnek Yayınevi",
                    },
                    files={"file": ("eksik.txt", b"Kaynak metni.", "text/plain")},
                )
                assert missing_permission.status_code == 422
                assert minio_client.objects == {}

                created = await client.post(
                    "/api/v1/admin/sources",
                    headers={"X-User-ID": str(ADMIN_ID)},
                    data={
                        "title": "Akademik Kaynak",
                        "license_name": "CC BY 4.0",
                        "rights_holder": "Örnek Yayınevi",
                        "license_evidence_reference": "SOZLESME-2026-001",
                    },
                    files={
                        "file": (
                            "kaynak.txt",
                            "Birinci kaynak cümlesi. İkinci cümle.".encode(),
                            "text/plain",
                        )
                    },
                )
                assert created.status_code == 201, created.text
                source = created.json()
                source_id = source["id"]
                assert source["status"] == "ready"
                assert source["license_status"] == "pending"
                assert len(source["sha256"]) == 64

                listed = await client.get(
                    "/api/v1/admin/sources?status=ready&license_status=pending",
                    headers={"X-User-ID": str(ADMIN_ID)},
                )
                assert listed.status_code == 200
                assert [item["id"] for item in listed.json()] == [source_id]

                reindexed = await client.post(
                    f"/api/v1/admin/sources/{source_id}/reindex",
                    headers={"X-User-ID": str(ADMIN_ID)},
                )
                assert reindexed.status_code == 200, reindexed.text
                assert reindexed.json()["status"] == "ready"

                storage_key = next(iter(minio_client.objects))
                minio_client.objects[storage_key] = b"Sonradan degistirilmis kaynak."
                checksum_conflict = await client.post(
                    f"/api/v1/admin/sources/{source_id}/reindex",
                    headers={"X-User-ID": str(ADMIN_ID)},
                )
                assert checksum_conflict.status_code == 409
                assert checksum_conflict.json()["detail"]["code"] == "source_checksum_mismatch"

                disabled = await client.post(
                    f"/api/v1/admin/sources/{source_id}/disable",
                    headers={"X-User-ID": str(ADMIN_ID)},
                )
                assert disabled.status_code == 200
                assert disabled.json()["status"] == "disabled"

                disabled_reindex = await client.post(
                    f"/api/v1/admin/sources/{source_id}/reindex",
                    headers={"X-User-ID": str(ADMIN_ID)},
                )
                assert disabled_reindex.status_code == 409
                assert disabled_reindex.json()["detail"]["code"] == "source_disabled"

        async with session_factory() as session:
            source_count = await session.scalar(select(func.count()).select_from(SourceDocument))
            chunk_count = await session.scalar(select(func.count()).select_from(SourceChunk))
            assert source_count == 1
            assert chunk_count == 2
    finally:
        application.dependency_overrides.clear()
        await engine.dispose()
