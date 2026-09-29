from __future__ import annotations

import hashlib
from io import BytesIO

import pytest

from intihal_api.corpus import SourceDocumentIngestionService, SourceMetadata
from intihal_api.db.models import SourceChunk, SourceDocument, SourceDocumentStatus
from intihal_api.storage import StoredObject


class FakeStorage:
    def __init__(self) -> None:
        self.uploaded_content: bytes | None = None
        self.uploaded_key: str | None = None
        self.removed_keys: list[str] = []

    def upload_object(
        self,
        *,
        key: str,
        stream: BytesIO,
        size_bytes: int,
        content_type: str,
    ) -> StoredObject:
        self.uploaded_content = stream.read()
        self.uploaded_key = key
        stream.seek(0)
        return StoredObject(bucket="intihal-documents", key=key, etag="source-etag")

    def remove_object(self, key: str) -> None:
        self.removed_keys.append(key)


class FakeSession:
    def __init__(self, commit_error_at: int | None = None) -> None:
        self.added: list[object] = []
        self.commit_calls = 0
        self.rollback_calls = 0
        self.execute_calls = 0
        self.commit_error_at = commit_error_at

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def add_all(self, instances: list[object]) -> None:
        self.added.extend(instances)

    async def commit(self) -> None:
        self.commit_calls += 1
        if self.commit_calls == self.commit_error_at:
            raise RuntimeError("database unavailable")

    async def rollback(self) -> None:
        self.rollback_calls += 1

    async def execute(self, statement: object) -> object:
        self.execute_calls += 1
        return object()


def metadata(**changes: str) -> SourceMetadata:
    values = {
        "title": "Kaynak başlığı",
        "license_name": "CC BY 4.0",
        "rights_holder": "Hak sahibi",
        "license_evidence_reference": "KANIT-001",
    }
    values.update(changes)
    return SourceMetadata(**values)


@pytest.mark.anyio
async def test_source_ingestion_validates_uploads_processes_and_persists_chunks() -> None:
    content = "Türkçe kaynak. İkinci cümle.".encode()
    storage = FakeStorage()
    session = FakeSession()

    source = await SourceDocumentIngestionService(storage).create_source(
        metadata=metadata(),
        filename="kaynak.txt",
        content_type="text/plain",
        stream=BytesIO(content),
        session=session,
    )

    chunks = [item for item in session.added if isinstance(item, SourceChunk)]
    assert isinstance(session.added[0], SourceDocument)
    assert source.status is SourceDocumentStatus.READY
    assert source.sha256 == hashlib.sha256(content).hexdigest()
    assert source.storage_key.startswith("sources/")
    assert storage.uploaded_content == content
    assert [chunk.content for chunk in chunks] == ["Türkçe kaynak.", "İkinci cümle."]
    assert session.commit_calls == 3
    assert session.execute_calls == 1


@pytest.mark.anyio
async def test_invalid_metadata_is_rejected_before_object_upload() -> None:
    storage = FakeStorage()
    session = FakeSession()

    with pytest.raises(ValueError, match="Kaynak başlığı"):
        await SourceDocumentIngestionService(storage).create_source(
            metadata=metadata(title="   "),
            filename="kaynak.txt",
            content_type="text/plain",
            stream=BytesIO(b"Kaynak metni."),
            session=session,
        )

    assert storage.uploaded_content is None
    assert session.added == []


@pytest.mark.anyio
async def test_metadata_persistence_failure_removes_orphaned_source_object() -> None:
    storage = FakeStorage()
    session = FakeSession(commit_error_at=1)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await SourceDocumentIngestionService(storage).create_source(
            metadata=metadata(),
            filename="kaynak.txt",
            content_type="text/plain",
            stream=BytesIO(b"Kaynak metni."),
            session=session,
        )

    assert session.rollback_calls == 1
    assert storage.removed_keys == [storage.uploaded_key]
