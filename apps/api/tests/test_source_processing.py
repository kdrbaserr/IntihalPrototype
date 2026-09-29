from __future__ import annotations

from io import BytesIO
from uuid import UUID

import pytest

from intihal_api.corpus import SourceDocumentProcessingService
from intihal_api.db.models import SourceChunk, SourceDocument, SourceDocumentStatus
from intihal_api.extraction import EmptyTextFileError

SOURCE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


class FakeSession:
    def __init__(self, commit_error_at: int | None = None) -> None:
        self.added: list[object] = []
        self.commit_calls = 0
        self.rollback_calls = 0
        self.commit_error_at = commit_error_at

    def add_all(self, instances: list[object]) -> None:
        self.added.extend(instances)

    async def commit(self) -> None:
        self.commit_calls += 1
        if self.commit_calls == self.commit_error_at:
            raise RuntimeError("database unavailable")

    async def rollback(self) -> None:
        self.rollback_calls += 1


def make_source() -> SourceDocument:
    return SourceDocument(
        id=SOURCE_ID,
        title="Örnek kaynak",
        license_name="CC BY 4.0",
        rights_holder="Örnek Hak Sahibi",
        license_evidence_reference="KANIT-001",
        original_filename="kaynak.txt",
        content_type="text/plain",
        size_bytes=1,
        sha256="a" * 64,
        storage_bucket="sources",
        storage_key="sources/example",
    )


@pytest.mark.anyio
async def test_source_document_uses_canonical_normalization_and_chunk_contract() -> None:
    source = make_source()
    session = FakeSession()
    content = "  Türkçe\x00 kaynak.  \r\n İkinci   cümle. ".encode()

    result = await SourceDocumentProcessingService().process(
        source_document=source,
        stream=BytesIO(content),
        session=session,
    )

    chunks = [item for item in session.added if isinstance(item, SourceChunk)]
    assert result.text == "Türkçe kaynak.\nİkinci cümle."
    assert [chunk.content for chunk in chunks] == ["Türkçe kaynak.", "İkinci cümle."]
    for persisted_chunk, contract_chunk in zip(chunks, result.chunks, strict=True):
        assert persisted_chunk.chunk_index == contract_chunk.chunk_index
        assert persisted_chunk.content == contract_chunk.content
        assert persisted_chunk.char_start == contract_chunk.char_start
        assert persisted_chunk.char_end == contract_chunk.char_end
        assert persisted_chunk.token_count == contract_chunk.token_count
        assert persisted_chunk.page_number == contract_chunk.page_number
        assert persisted_chunk.content_sha256 == contract_chunk.content_sha256
    assert source.status is SourceDocumentStatus.READY
    assert session.commit_calls == 2
    assert session.rollback_calls == 0


@pytest.mark.anyio
async def test_source_document_is_marked_failed_when_extraction_fails() -> None:
    source = make_source()
    session = FakeSession()

    with pytest.raises(EmptyTextFileError):
        await SourceDocumentProcessingService().process(
            source_document=source,
            stream=BytesIO(b""),
            session=session,
        )

    assert source.status is SourceDocumentStatus.FAILED
    assert session.added == []
    assert session.commit_calls == 2


@pytest.mark.anyio
async def test_source_chunk_transaction_rolls_back_when_persistence_fails() -> None:
    source = make_source()
    session = FakeSession(commit_error_at=2)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await SourceDocumentProcessingService().process(
            source_document=source,
            stream=BytesIO(b"Kaynak metni."),
            session=session,
        )

    assert session.rollback_calls == 1
