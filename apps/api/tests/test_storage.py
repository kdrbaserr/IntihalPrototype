import asyncio
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from minio.error import S3Error

from intihal_api.main import create_app
from intihal_api.storage import (
    ObjectStorageService,
    StorageAuthenticationError,
    StorageConnectionError,
    StoredObject,
    build_document_storage_key,
)


class FakeWriteResult:
    etag = "fake-etag"


class FakeBucketClient:
    def __init__(
        self,
        *,
        exists: bool = False,
        bucket_error: Exception | None = None,
        make_error: Exception | None = None,
    ) -> None:
        self.exists = exists
        self.bucket_error = bucket_error
        self.make_error = make_error
        self.bucket_exists_calls: list[str] = []
        self.make_bucket_calls: list[str] = []
        self.put_object_calls: list[tuple[str, str, bytes, int, str]] = []
        self.remove_object_calls: list[tuple[str, str]] = []

    def bucket_exists(self, bucket_name: str) -> bool:
        self.bucket_exists_calls.append(bucket_name)
        if self.bucket_error is not None:
            raise self.bucket_error
        return self.exists

    def make_bucket(self, bucket_name: str) -> None:
        self.make_bucket_calls.append(bucket_name)
        if self.make_error is not None:
            raise self.make_error
        self.exists = True

    def put_object(
        self,
        bucket_name: str,
        object_name: str,
        data: BytesIO,
        length: int,
        content_type: str = "application/octet-stream",
    ) -> FakeWriteResult:
        self.put_object_calls.append((bucket_name, object_name, data.read(), length, content_type))
        return FakeWriteResult()

    def remove_object(self, bucket_name: str, object_name: str) -> None:
        self.remove_object_calls.append((bucket_name, object_name))


def s3_error(code: str) -> S3Error:
    return S3Error(
        code=code,
        message="SDK detail that must not become the public error",
        resource="/intihal-documents",
        request_id="request-id",
        host_id="host-id",
        response=None,
    )


def test_existing_bucket_is_reused() -> None:
    client = FakeBucketClient(exists=True)
    service = ObjectStorageService(client, "intihal-documents")

    service.ensure_bucket()

    assert client.bucket_exists_calls == ["intihal-documents"]
    assert client.make_bucket_calls == []


def test_missing_bucket_is_created_once() -> None:
    client = FakeBucketClient()
    service = ObjectStorageService(client, "intihal-documents")

    service.ensure_bucket()
    service.ensure_bucket()

    assert client.make_bucket_calls == ["intihal-documents"]


def test_connection_failure_becomes_safe_storage_error() -> None:
    client = FakeBucketClient(bucket_error=OSError("connection refused at internal host"))
    service = ObjectStorageService(client, "intihal-documents")

    with pytest.raises(StorageConnectionError) as captured_error:
        service.ensure_bucket()

    assert str(captured_error.value) == "Dosya depolama servisine şu anda ulaşılamıyor."
    assert "internal host" not in str(captured_error.value)


def test_invalid_credentials_become_authentication_error() -> None:
    client = FakeBucketClient(bucket_error=s3_error("InvalidAccessKeyId"))
    service = ObjectStorageService(client, "intihal-documents")

    with pytest.raises(StorageAuthenticationError) as captured_error:
        service.ensure_bucket()

    assert "kimlik bilgilerini" in str(captured_error.value)
    assert "SDK detail" not in str(captured_error.value)


def test_document_storage_key_is_stable_unique_and_filename_free() -> None:
    owner_id = UUID("11111111-1111-1111-1111-111111111111")
    first_document_id = UUID("22222222-2222-2222-2222-222222222222")
    second_document_id = uuid4()

    first_key = build_document_storage_key(owner_id, first_document_id)
    repeated_key = build_document_storage_key(owner_id, first_document_id)
    second_key = build_document_storage_key(owner_id, second_document_id)

    assert first_key == repeated_key
    assert first_key != second_key
    assert first_key == (
        "documents/11111111111111111111111111111111/22222222222222222222222222222222"
    )
    assert ".." not in first_key


def test_object_upload_returns_storage_identity_and_rewinds_stream() -> None:
    client = FakeBucketClient(exists=True)
    service = ObjectStorageService(client, "intihal-documents")
    stream = BytesIO(b"document bytes")

    stored = service.upload_object(
        key="documents/owner/document",
        stream=stream,
        size_bytes=len(stream.getvalue()),
        content_type="application/pdf",
    )

    assert stored == StoredObject(
        bucket="intihal-documents",
        key="documents/owner/document",
        etag="fake-etag",
    )
    assert client.put_object_calls == [
        (
            "intihal-documents",
            "documents/owner/document",
            b"document bytes",
            14,
            "application/pdf",
        )
    ]
    assert stream.tell() == 0


def test_object_removal_uses_configured_bucket() -> None:
    client = FakeBucketClient(exists=True)
    service = ObjectStorageService(client, "intihal-documents")

    service.remove_object("documents/owner/document")

    assert client.remove_object_calls == [("intihal-documents", "documents/owner/document")]


def test_application_lifespan_initializes_storage() -> None:
    client = FakeBucketClient()
    storage = ObjectStorageService(client, "intihal-documents")
    application = create_app(storage_service=storage)

    async def run_lifespan() -> None:
        async with application.router.lifespan_context(application):
            assert application.state.storage is storage

    asyncio.run(run_lifespan())

    assert client.make_bucket_calls == ["intihal-documents"]
