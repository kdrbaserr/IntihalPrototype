import hashlib
import os
import subprocess
import sys
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from file_samples import make_pdf_bytes
from intihal_api.db.models import Document, DocumentStatus, User
from intihal_api.storage import StorageConnectionError, StoredObject
from intihal_api.uploads import (
    DocumentUploadService,
    calculate_sha256,
    sanitize_original_filename,
)

API_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_ENV = "INTIHAL_TEST_DATABASE_URL"


def require_test_database_url() -> str:
    database_url = os.getenv(TEST_DATABASE_ENV)
    if database_url is None:
        pytest.skip(f"{TEST_DATABASE_ENV} is not configured")
    database_name = make_url(database_url).database or ""
    if "test" not in database_name.lower():
        pytest.fail(f"Refusing persistence test against non-test database: {database_name!r}")
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
def migrated_upload_database_url() -> Iterator[str]:
    database_url = require_test_database_url()
    run_alembic(database_url, "downgrade", "base")
    run_alembic(database_url, "upgrade", "head")
    try:
        yield database_url
    finally:
        run_alembic(database_url, "downgrade", "base")


class FakeStorage:
    def __init__(self, upload_error: Exception | None = None) -> None:
        self.upload_error = upload_error
        self.uploaded_content: bytes | None = None
        self.uploaded_key: str | None = None
        self.uploaded_size: int | None = None
        self.uploaded_content_type: str | None = None
        self.removed_keys: list[str] = []

    def upload_object(
        self,
        *,
        key: str,
        stream: BytesIO,
        size_bytes: int,
        content_type: str,
    ) -> StoredObject:
        if self.upload_error is not None:
            raise self.upload_error
        self.uploaded_key = key
        self.uploaded_content = stream.read()
        self.uploaded_size = size_bytes
        self.uploaded_content_type = content_type
        stream.seek(0)
        return StoredObject(
            bucket="intihal-documents",
            key=key,
            etag="stored-etag",
        )

    def remove_object(self, key: str) -> None:
        self.removed_keys.append(key)


class FakeSession:
    def __init__(self, commit_error: Exception | None = None) -> None:
        self.commit_error = commit_error
        self.added: list[object] = []
        self.commit_calls = 0
        self.rollback_calls = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def commit(self) -> None:
        self.commit_calls += 1
        if self.commit_error is not None:
            raise self.commit_error

    async def rollback(self) -> None:
        self.rollback_calls += 1


@pytest.mark.anyio
async def test_upload_saves_hash_size_mime_and_original_filename() -> None:
    owner_id = UUID("11111111-1111-1111-1111-111111111111")
    content = make_pdf_bytes()
    stream = BytesIO(content)
    storage = FakeStorage()
    session = FakeSession()
    service = DocumentUploadService(storage)

    document = await service.create_document(
        owner_id=owner_id,
        filename="C:\\fakepath\\Bitirme Tezi.pdf",
        content_type="Application/PDF; charset=binary",
        stream=stream,
        session=session,
    )

    assert isinstance(document, Document)
    assert document.owner_id == owner_id
    assert document.original_filename == "Bitirme Tezi.pdf"
    assert document.content_type == "application/pdf"
    assert document.size_bytes == len(content)
    assert document.sha256 == hashlib.sha256(content).hexdigest()
    assert document.status is DocumentStatus.UPLOADED
    assert document.storage_bucket == "intihal-documents"
    assert document.storage_key.startswith(f"documents/{owner_id.hex}/")
    assert "Bitirme Tezi.pdf" not in document.storage_key
    assert document.storage_etag == "stored-etag"
    assert storage.uploaded_content == content
    assert storage.uploaded_size == len(content)
    assert storage.uploaded_content_type == "application/pdf"
    assert session.added == [document]
    assert session.commit_calls == 1
    assert session.rollback_calls == 0
    assert stream.tell() == 0


@pytest.mark.anyio
async def test_upload_metadata_is_persisted_in_postgresql(
    migrated_upload_database_url: str,
) -> None:
    engine = create_async_engine(migrated_upload_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    owner_id = UUID("11111111-1111-1111-1111-111111111111")
    content = make_pdf_bytes()
    storage = FakeStorage()

    try:
        async with session_factory() as session:
            session.add(
                User(
                    id=owner_id,
                    email="upload-test@example.com",
                    display_name="Upload Test",
                )
            )
            await session.commit()

            service = DocumentUploadService(storage)
            created = await service.create_document(
                owner_id=owner_id,
                filename="Tez.pdf",
                content_type="application/pdf",
                stream=BytesIO(content),
                session=session,
            )

        async with session_factory() as session:
            persisted = await session.scalar(select(Document).where(Document.id == created.id))

        assert persisted is not None
        assert persisted.original_filename == "Tez.pdf"
        assert persisted.content_type == "application/pdf"
        assert persisted.size_bytes == len(content)
        assert persisted.sha256 == hashlib.sha256(content).hexdigest()
        assert persisted.storage_bucket == "intihal-documents"
        assert persisted.storage_key == storage.uploaded_key
        assert persisted.storage_etag == "stored-etag"
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_database_failure_rolls_back_and_removes_uploaded_object() -> None:
    storage = FakeStorage()
    session = FakeSession(commit_error=RuntimeError("database unavailable"))
    service = DocumentUploadService(storage)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await service.create_document(
            owner_id=UUID("11111111-1111-1111-1111-111111111111"),
            filename="tez.pdf",
            content_type="application/pdf",
            stream=BytesIO(make_pdf_bytes()),
            session=session,
        )

    assert session.rollback_calls == 1
    assert storage.removed_keys == [storage.uploaded_key]


@pytest.mark.anyio
async def test_storage_failure_does_not_create_database_record() -> None:
    storage = FakeStorage(StorageConnectionError("storage unavailable"))
    session = FakeSession()
    service = DocumentUploadService(storage)

    with pytest.raises(StorageConnectionError, match="storage unavailable"):
        await service.create_document(
            owner_id=UUID("11111111-1111-1111-1111-111111111111"),
            filename="tez.pdf",
            content_type="application/pdf",
            stream=BytesIO(make_pdf_bytes()),
            session=session,
        )

    assert session.added == []
    assert session.commit_calls == 0
    assert session.rollback_calls == 0


def test_sha256_is_calculated_incrementally_and_stream_is_rewound() -> None:
    content = b"a" * (2 * 1024 * 1024 + 25)
    stream = BytesIO(content)

    checksum, size_bytes = calculate_sha256(stream)

    assert checksum == hashlib.sha256(content).hexdigest()
    assert size_bytes == len(content)
    assert stream.tell() == 0


def test_original_filename_is_cleaned_and_keeps_extension_when_truncated() -> None:
    unsafe_name = "../folder\\" + ("a" * 300) + "\x00.pdf"

    cleaned_name = sanitize_original_filename(unsafe_name)

    assert len(cleaned_name) == 255
    assert cleaned_name.endswith(".pdf")
    assert "/" not in cleaned_name
    assert "\\" not in cleaned_name
    assert "\x00" not in cleaned_name


@pytest.mark.parametrize(
    "unsafe_name",
    [
        "../../../../etc/passwd.pdf",
        "..\\..\\Windows\\system32\\config.pdf",
        "/tmp/../secret/tez.pdf",
        "C:\\Users\\victim\\Documents\\tez.pdf",
    ],
)
@pytest.mark.anyio
async def test_path_traversal_filename_cannot_control_storage_key(unsafe_name: str) -> None:
    owner_id = UUID("11111111-1111-1111-1111-111111111111")
    storage = FakeStorage()
    session = FakeSession()

    document = await DocumentUploadService(storage).create_document(
        owner_id=owner_id,
        filename=unsafe_name,
        content_type="application/pdf",
        stream=BytesIO(make_pdf_bytes()),
        session=session,
    )

    assert document.original_filename.endswith(".pdf")
    assert "/" not in document.original_filename
    assert "\\" not in document.original_filename
    assert document.storage_key.startswith(f"documents/{owner_id.hex}/")
    assert ".." not in document.storage_key
    assert document.original_filename not in document.storage_key
