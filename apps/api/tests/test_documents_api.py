import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from auth_helpers import session_headers
from file_samples import make_pdf_bytes
from intihal_api.db.models import Document, User, UserStatus
from intihal_api.db.session import get_db_session
from intihal_api.main import create_app
from intihal_api.storage import ObjectStorageService

API_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_ENV = "INTIHAL_TEST_DATABASE_URL"
ACTIVE_USER_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_USER_ID = UUID("22222222-2222-2222-2222-222222222222")
DISABLED_USER_ID = UUID("33333333-3333-3333-3333-333333333333")


class FakeWriteResult:
    etag = "api-test-etag"


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

    def remove_object(self, bucket_name: str, object_name: str) -> None:
        self.objects.pop(object_name, None)


def require_test_database_url() -> str:
    database_url = os.getenv(TEST_DATABASE_ENV)
    if database_url is None:
        pytest.skip(f"{TEST_DATABASE_ENV} is not configured")
    database_name = make_url(database_url).database or ""
    if "test" not in database_name.lower():
        pytest.fail(f"Refusing API test against non-test database: {database_name!r}")
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
def migrated_api_database_url() -> Iterator[str]:
    database_url = require_test_database_url()
    run_alembic(database_url, "downgrade", "base")
    run_alembic(database_url, "upgrade", "head")
    try:
        yield database_url
    finally:
        run_alembic(database_url, "downgrade", "base")


async def seed_users(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        session.add_all(
            [
                User(
                    id=ACTIVE_USER_ID,
                    email="active@example.com",
                    display_name="Active User",
                ),
                User(
                    id=OTHER_USER_ID,
                    email="other@example.com",
                    display_name="Other User",
                ),
                User(
                    id=DISABLED_USER_ID,
                    email="disabled@example.com",
                    display_name="Disabled User",
                    status=UserStatus.DISABLED,
                ),
            ]
        )
        await session.commit()


@pytest.mark.anyio
async def test_document_endpoints_enforce_ownership(
    migrated_api_database_url: str,
) -> None:
    engine = create_async_engine(migrated_api_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    minio_client = FakeMinioClient()
    storage = ObjectStorageService(minio_client, "intihal-documents")
    application = create_app(storage_service=storage)

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_db_session] = override_db_session

    try:
        await seed_users(session_factory)
        async with session_factory() as session:
            identities = {user_id: await session_headers(session, user_id) for user_id in
                          [ACTIVE_USER_ID, OTHER_USER_ID, DISABLED_USER_ID]}
        async with application.router.lifespan_context(application):
            transport = ASGITransport(app=application)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                missing_identity = await client.get("/api/v1/documents")
                assert missing_identity.status_code == 401

                unknown_identity = await client.get(
                    "/api/v1/documents",
                    headers={"X-User-ID": "44444444-4444-4444-4444-444444444444"},
                )
                assert unknown_identity.status_code == 401

                disabled_identity = await client.get(
                    "/api/v1/documents",
                    headers=identities[DISABLED_USER_ID],
                )
                assert disabled_identity.status_code == 403

                pdf_content = make_pdf_bytes()
                upload = await client.post(
                    "/api/v1/documents",
                    headers=identities[ACTIVE_USER_ID],
                    files={"file": ("Tez.pdf", pdf_content, "application/pdf")},
                )
                assert upload.status_code == 201
                uploaded_document = upload.json()
                assert uploaded_document["original_filename"] == "Tez.pdf"
                assert uploaded_document["content_type"] == "application/pdf"
                assert uploaded_document["size_bytes"] == len(pdf_content)
                assert uploaded_document["status"] == "uploaded"
                assert len(uploaded_document["sha256"]) == 64

                owner_list = await client.get(
                    "/api/v1/documents",
                    headers=identities[ACTIVE_USER_ID],
                )
                assert owner_list.status_code == 200
                assert [item["id"] for item in owner_list.json()] == [uploaded_document["id"]]

                other_user_list = await client.get(
                    "/api/v1/documents",
                    headers=identities[OTHER_USER_ID],
                )
                assert other_user_list.status_code == 200
                assert other_user_list.json() == []

                invalid_upload = await client.post(
                    "/api/v1/documents",
                    headers=identities[ACTIVE_USER_ID],
                    files={"file": ("fake.pdf", b"not a pdf", "application/pdf")},
                )
                assert invalid_upload.status_code == 400
                assert invalid_upload.json()["detail"]["code"] == "file_signature_mismatch"

        async with session_factory() as session:
            persisted = await session.scalar(
                select(Document).where(Document.id == UUID(uploaded_document["id"]))
            )
            assert persisted is not None
            assert persisted.owner_id == ACTIVE_USER_ID
            assert persisted.storage_key in minio_client.objects
    finally:
        application.dependency_overrides.clear()
        await engine.dispose()
