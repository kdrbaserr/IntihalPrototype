from io import BytesIO
from typing import BinaryIO

import pytest

from intihal_api.corpus.sample_seed import (
    SYNTHETIC_CORPUS_VERSION,
    SYNTHETIC_LICENSE,
    build_sample_sources,
    seed_sample_corpus,
)
from intihal_api.db.models import LicenseStatus, SourceDocument
from intihal_api.extraction import extract_and_chunk_document
from intihal_api.storage import StoredObject
from intihal_api.uploads import validate_document_upload
from intihal_api.uploads.validation import DocumentFormat


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload_object(
        self,
        *,
        key: str,
        stream: BinaryIO,
        size_bytes: int,
        content_type: str,
    ) -> StoredObject:
        self.objects[key] = stream.read()
        stream.seek(0)
        return StoredObject(bucket="samples", key=key, etag="sample-etag")

    def remove_object(self, key: str) -> None:
        self.objects.pop(key, None)


class FakeSession:
    def __init__(self) -> None:
        self.references: dict[str, object] = {}
        self.sources: list[SourceDocument] = []

    async def scalar(self, statement: object) -> object | None:
        parameters = statement.compile().params  # type: ignore[attr-defined]
        reference = next(iter(parameters.values()))
        return self.references.get(reference)

    def add(self, instance: object) -> None:
        if isinstance(instance, SourceDocument):
            self.sources.append(instance)
            self.references[instance.license_evidence_reference] = instance.id

    def add_all(self, instances: list[object]) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def execute(self, statement: object) -> object:
        return object()


def test_sample_corpus_is_small_synthetic_and_covers_every_supported_format() -> None:
    samples = build_sample_sources()

    assert len(samples) == 3
    assert {sample.filename.rsplit(".", maxsplit=1)[-1] for sample in samples} == {
        "pdf",
        "docx",
        "txt",
    }
    assert all(sample.metadata.license_name == SYNTHETIC_LICENSE for sample in samples)
    assert all(
        sample.metadata.license_evidence_reference.startswith(
            f"SYNTHETIC-CORPUS-{SYNTHETIC_CORPUS_VERSION}/"
        )
        for sample in samples
    )
    assert len({sample.metadata.license_evidence_reference for sample in samples}) == 3
    assert sum(len(sample.content) for sample in samples) < 100_000


def test_every_sample_passes_real_validation_extraction_and_chunking() -> None:
    for sample in build_sample_sources():
        validation_stream = BytesIO(sample.content)
        validated = validate_document_upload(
            filename=sample.filename,
            content_type=sample.content_type,
            stream=validation_stream,
        )

        result = extract_and_chunk_document(BytesIO(sample.content), validated.document_format)

        assert result.text
        assert result.chunks
        assert all(
            result.text[chunk.char_start : chunk.char_end] == chunk.content
            for chunk in result.chunks
        )


def test_pdf_sample_preserves_two_page_boundaries() -> None:
    pdf_sample = next(
        sample
        for sample in build_sample_sources()
        if sample.filename.endswith(DocumentFormat.PDF.value)
    )

    result = extract_and_chunk_document(BytesIO(pdf_sample.content), DocumentFormat.PDF)

    assert {chunk.page_number for chunk in result.chunks} == {1, 2}


def test_docx_sample_includes_paragraph_and_table_content() -> None:
    docx_sample = next(
        sample
        for sample in build_sample_sources()
        if sample.filename.endswith(DocumentFormat.DOCX.value)
    )

    result = extract_and_chunk_document(BytesIO(docx_sample.content), DocumentFormat.DOCX)

    assert "Tekrarlanabilir Araştırma" in result.text
    assert "Checksum İçerik bütünlüğü" in result.text


@pytest.mark.anyio
async def test_sample_seed_is_idempotent_and_approves_created_sources() -> None:
    session = FakeSession()
    storage = FakeStorage()

    first = await seed_sample_corpus(session=session, storage=storage)  # type: ignore[arg-type]
    second = await seed_sample_corpus(session=session, storage=storage)  # type: ignore[arg-type]

    assert (first.created, first.skipped) == (3, 0)
    assert (second.created, second.skipped) == (0, 3)
    assert len(storage.objects) == 3
    assert len(session.sources) == 3
    assert all(source.license_status is LicenseStatus.APPROVED for source in session.sources)
    assert all(source.license_verified_at is not None for source in session.sources)
