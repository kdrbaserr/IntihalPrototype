from sqlalchemy import Enum, inspect
from sqlalchemy.ext.asyncio import AsyncSession

from intihal_api.db.base import BaseModel
from intihal_api.db.models import (
    Analysis,
    AnalysisStatus,
    Document,
    DocumentChunk,
    DocumentStatus,
    LicenseStatus,
    Match,
    MatchMethod,
    SourceChunk,
    SourceDocument,
    SourceDocumentStatus,
    User,
    UserRole,
    UserStatus,
)
from intihal_api.db.session import AsyncSessionFactory, engine


class ExampleModel(BaseModel):
    __tablename__ = "example_models"


def test_database_uses_async_driver_and_sessions() -> None:
    assert engine.dialect.is_async is True
    assert engine.url.drivername == "postgresql+asyncpg"
    assert AsyncSessionFactory.class_ is AsyncSession
    assert AsyncSessionFactory.kw["expire_on_commit"] is False


def test_shared_model_fields_are_defined_once() -> None:
    mapper = inspect(ExampleModel)

    assert set(mapper.columns.keys()) == {"id", "created_at", "updated_at"}
    assert mapper.columns.id.primary_key is True
    assert mapper.columns.id.default.is_callable is True
    assert mapper.columns.created_at.nullable is False
    assert mapper.columns.created_at.server_default is not None
    assert mapper.columns.updated_at.nullable is False
    assert mapper.columns.updated_at.server_default is not None
    assert mapper.columns.updated_at.onupdate is not None


def test_user_model_has_identity_and_status_fields() -> None:
    mapper = inspect(User)

    assert set(mapper.columns.keys()) == {
        "id",
        "email",
        "display_name",
        "status",
        "role",
        "created_at",
        "updated_at",
    }
    assert mapper.columns.email.unique is True
    assert mapper.columns.email.index is True
    assert mapper.columns.status.server_default.arg == UserStatus.ACTIVE.value
    assert isinstance(mapper.columns.status.type, Enum)
    assert mapper.columns.status.type.enums == ["active", "disabled"]
    assert mapper.columns.role.server_default.arg == UserRole.USER.value
    assert isinstance(mapper.columns.role.type, Enum)
    assert mapper.columns.role.type.enums == ["user", "admin"]


def test_document_model_tracks_owner_lifecycle_and_storage() -> None:
    mapper = inspect(Document)

    assert set(mapper.columns.keys()) == {
        "id",
        "owner_id",
        "original_filename",
        "content_type",
        "size_bytes",
        "sha256",
        "status",
        "storage_bucket",
        "storage_key",
        "storage_etag",
        "created_at",
        "updated_at",
    }
    assert mapper.columns.owner_id.nullable is False
    owner_foreign_key = next(iter(mapper.columns.owner_id.foreign_keys))
    assert owner_foreign_key.target_fullname == "users.id"
    assert mapper.columns.status.server_default.arg == DocumentStatus.UPLOADED.value
    assert mapper.relationships.owner.back_populates == "documents"
    assert {status.value for status in DocumentStatus} == {
        "uploaded",
        "processing",
        "ready",
        "failed",
        "deleted",
    }

    constraint_names = {constraint.name for constraint in Document.__table__.constraints}
    assert "ck_documents_size_bytes_non_negative" in constraint_names
    assert "uq_documents_storage_location" in constraint_names


def test_source_document_tracks_license_review_and_storage() -> None:
    mapper = inspect(SourceDocument)

    assert set(mapper.columns.keys()) == {
        "id",
        "title",
        "author",
        "publisher",
        "source_url",
        "status",
        "license_status",
        "license_name",
        "rights_holder",
        "license_url",
        "attribution_text",
        "license_evidence_reference",
        "license_valid_from",
        "license_valid_until",
        "license_verified_at",
        "original_filename",
        "content_type",
        "size_bytes",
        "sha256",
        "storage_bucket",
        "storage_key",
        "storage_etag",
        "created_at",
        "updated_at",
    }
    assert mapper.columns.status.server_default.arg == SourceDocumentStatus.PENDING.value
    assert mapper.columns.license_status.server_default.arg == LicenseStatus.PENDING.value
    for required_column in (
        "title",
        "license_name",
        "license_evidence_reference",
        "sha256",
    ):
        assert mapper.columns[required_column].nullable is False
    assert mapper.relationships.chunks.back_populates == "source_document"
    assert mapper.relationships.chunks.cascade.delete_orphan is True

    constraint_names = {constraint.name for constraint in SourceDocument.__table__.constraints}
    assert "ck_source_documents_license_date_range_valid" in constraint_names
    assert "ck_source_documents_size_bytes_non_negative" in constraint_names
    assert "uq_source_documents_sha256" in constraint_names
    assert "uq_source_documents_storage_location" in constraint_names


def test_source_chunk_keeps_traceable_text_location() -> None:
    mapper = inspect(SourceChunk)

    assert set(mapper.columns.keys()) == {
        "id",
        "source_document_id",
        "chunk_index",
        "content",
        "char_start",
        "char_end",
        "token_count",
        "page_number",
        "content_sha256",
        "created_at",
        "updated_at",
    }
    source_foreign_key = next(iter(mapper.columns.source_document_id.foreign_keys))
    assert source_foreign_key.target_fullname == "source_documents.id"
    assert source_foreign_key.ondelete == "CASCADE"
    assert mapper.relationships.source_document.back_populates == "chunks"

    constraint_names = {constraint.name for constraint in SourceChunk.__table__.constraints}
    assert {
        "ck_source_chunks_chunk_index_non_negative",
        "ck_source_chunks_char_start_non_negative",
        "ck_source_chunks_char_range_valid",
        "ck_source_chunks_token_count_non_negative",
        "ck_source_chunks_page_number_positive",
        "uq_source_chunks_document_index",
    }.issubset(constraint_names)


def test_document_chunk_keeps_uploaded_text_location() -> None:
    mapper = inspect(DocumentChunk)

    assert set(mapper.columns.keys()) == {
        "id",
        "document_id",
        "chunk_index",
        "content",
        "char_start",
        "char_end",
        "token_count",
        "page_number",
        "content_sha256",
        "created_at",
        "updated_at",
    }
    document_foreign_key = next(iter(mapper.columns.document_id.foreign_keys))
    assert document_foreign_key.target_fullname == "documents.id"
    assert document_foreign_key.ondelete == "CASCADE"
    assert mapper.relationships.document.back_populates == "chunks"

    constraint_names = {constraint.name for constraint in DocumentChunk.__table__.constraints}
    assert {
        "ck_document_chunks_chunk_index_non_negative",
        "ck_document_chunks_char_start_non_negative",
        "ck_document_chunks_char_range_valid",
        "ck_document_chunks_token_count_non_negative",
        "ck_document_chunks_page_number_positive",
        "uq_document_chunks_document_index",
    }.issubset(constraint_names)


def test_analysis_tracks_execution_and_algorithm_version() -> None:
    mapper = inspect(Analysis)

    assert set(mapper.columns.keys()) == {
        "id",
        "document_id",
        "status",
        "algorithm_version",
        "similarity_threshold",
        "started_at",
        "completed_at",
        "failure_reason",
        "created_at",
        "updated_at",
    }
    document_foreign_key = next(iter(mapper.columns.document_id.foreign_keys))
    assert document_foreign_key.target_fullname == "documents.id"
    assert document_foreign_key.ondelete == "RESTRICT"
    assert mapper.columns.status.server_default.arg == AnalysisStatus.QUEUED.value
    assert mapper.columns.similarity_threshold.server_default.arg == "0.8000"
    assert mapper.relationships.matches.cascade.delete_orphan is True

    constraint_names = {constraint.name for constraint in Analysis.__table__.constraints}
    assert "ck_analyses_similarity_threshold_range" in constraint_names
    assert "ck_analyses_execution_date_range_valid" in constraint_names


def test_match_links_analysis_and_both_evidence_chunks() -> None:
    mapper = inspect(Match)

    assert set(mapper.columns.keys()) == {
        "id",
        "analysis_id",
        "document_chunk_id",
        "source_chunk_id",
        "method",
        "similarity_score",
        "document_match_start",
        "document_match_end",
        "source_match_start",
        "source_match_end",
        "matched_token_count",
        "explanation",
        "created_at",
        "updated_at",
    }
    foreign_keys = {
        foreign_key.target_fullname: foreign_key.ondelete
        for column in mapper.columns
        for foreign_key in column.foreign_keys
    }
    assert foreign_keys == {
        "analyses.id": "CASCADE",
        "document_chunks.id": "RESTRICT",
        "source_chunks.id": "RESTRICT",
    }
    assert mapper.columns.method.type.enums == [method.value for method in MatchMethod]

    constraint_names = {constraint.name for constraint in Match.__table__.constraints}
    assert {
        "ck_matches_similarity_score_range",
        "ck_matches_document_match_range_valid",
        "ck_matches_source_match_range_valid",
        "ck_matches_matched_token_count_positive",
        "uq_matches_evidence_location",
    }.issubset(constraint_names)
