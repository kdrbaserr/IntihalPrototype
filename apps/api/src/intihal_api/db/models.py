from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intihal_api.db.base import BaseModel


class UserStatus(enum.StrEnum):
    """Whether an account may currently use the application."""

    ACTIVE = "active"
    DISABLED = "disabled"


class DocumentStatus(enum.StrEnum):
    """Lifecycle state of a document and its analysis."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class SourceDocumentStatus(enum.StrEnum):
    """Preparation state of a document in the comparison corpus."""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DISABLED = "disabled"


class LicenseStatus(enum.StrEnum):
    """Review state of the permission to use a source document."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AnalysisStatus(enum.StrEnum):
    """Execution state of a document comparison."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MatchMethod(enum.StrEnum):
    """Technique that produced a similarity match."""

    EXACT = "exact"
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class User(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus, name="user_status", values_callable=lambda values: [v.value for v in values]
        ),
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
        index=True,
        nullable=False,
    )

    documents: Mapped[list[Document]] = relationship(
        back_populates="owner",
        passive_deletes=True,
    )


class Document(BaseModel):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="size_bytes_non_negative"),
        UniqueConstraint("storage_bucket", "storage_key", name="uq_documents_storage_location"),
        Index("ix_documents_owner_id_status", "owner_id", "status"),
    )

    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus,
            name="document_status",
            values_callable=lambda values: [v.value for v in values],
        ),
        default=DocumentStatus.UPLOADED,
        server_default=DocumentStatus.UPLOADED.value,
        index=True,
        nullable=False,
    )
    storage_bucket: Mapped[str] = mapped_column(String(63), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    storage_etag: Mapped[str | None] = mapped_column(String(255))

    owner: Mapped[User] = relationship(back_populates="documents")
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    analyses: Mapped[list[Analysis]] = relationship(
        back_populates="document",
        passive_deletes=True,
    )


class SourceDocument(BaseModel):
    __tablename__ = "source_documents"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="size_bytes_non_negative"),
        CheckConstraint(
            "license_valid_until IS NULL OR license_valid_from IS NULL "
            "OR license_valid_until >= license_valid_from",
            name="license_date_range_valid",
        ),
        UniqueConstraint(
            "storage_bucket",
            "storage_key",
            name="uq_source_documents_storage_location",
        ),
        Index("ix_source_documents_status_license_status", "status", "license_status"),
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[str | None] = mapped_column(String(300))
    publisher: Mapped[str | None] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[SourceDocumentStatus] = mapped_column(
        Enum(
            SourceDocumentStatus,
            name="source_document_status",
            values_callable=lambda values: [v.value for v in values],
        ),
        default=SourceDocumentStatus.PENDING,
        server_default=SourceDocumentStatus.PENDING.value,
        nullable=False,
    )

    license_status: Mapped[LicenseStatus] = mapped_column(
        Enum(
            LicenseStatus,
            name="license_status",
            values_callable=lambda values: [v.value for v in values],
        ),
        default=LicenseStatus.PENDING,
        server_default=LicenseStatus.PENDING.value,
        nullable=False,
    )
    license_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rights_holder: Mapped[str] = mapped_column(String(300), nullable=False)
    license_url: Mapped[str | None] = mapped_column(String(2048))
    attribution_text: Mapped[str | None] = mapped_column(Text)
    license_evidence_reference: Mapped[str | None] = mapped_column(String(500))
    license_valid_from: Mapped[date | None] = mapped_column(Date)
    license_valid_until: Mapped[date | None] = mapped_column(Date)
    license_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_bucket: Mapped[str] = mapped_column(String(63), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    storage_etag: Mapped[str | None] = mapped_column(String(255))

    chunks: Mapped[list[SourceChunk]] = relationship(
        back_populates="source_document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SourceChunk(BaseModel):
    __tablename__ = "source_chunks"
    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="chunk_index_non_negative"),
        CheckConstraint("char_start >= 0", name="char_start_non_negative"),
        CheckConstraint("char_end > char_start", name="char_range_valid"),
        CheckConstraint("token_count >= 0", name="token_count_non_negative"),
        CheckConstraint("page_number IS NULL OR page_number > 0", name="page_number_positive"),
        UniqueConstraint(
            "source_document_id",
            "chunk_index",
            name="uq_source_chunks_document_index",
        ),
    )

    source_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(nullable=False)
    char_end: Mapped[int] = mapped_column(nullable=False)
    token_count: Mapped[int] = mapped_column(nullable=False)
    page_number: Mapped[int | None] = mapped_column()
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    source_document: Mapped[SourceDocument] = relationship(back_populates="chunks")
    matches: Mapped[list[Match]] = relationship(
        back_populates="source_chunk",
        passive_deletes=True,
    )


class DocumentChunk(BaseModel):
    __tablename__ = "document_chunks"
    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="chunk_index_non_negative"),
        CheckConstraint("char_start >= 0", name="char_start_non_negative"),
        CheckConstraint("char_end > char_start", name="char_range_valid"),
        CheckConstraint("token_count >= 0", name="token_count_non_negative"),
        CheckConstraint("page_number IS NULL OR page_number > 0", name="page_number_positive"),
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_document_index",
        ),
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(nullable=False)
    char_end: Mapped[int] = mapped_column(nullable=False)
    token_count: Mapped[int] = mapped_column(nullable=False)
    page_number: Mapped[int | None] = mapped_column()
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    document: Mapped[Document] = relationship(back_populates="chunks")
    matches: Mapped[list[Match]] = relationship(
        back_populates="document_chunk",
        passive_deletes=True,
    )


class Analysis(BaseModel):
    __tablename__ = "analyses"
    __table_args__ = (
        CheckConstraint(
            "similarity_threshold >= 0 AND similarity_threshold <= 1",
            name="similarity_threshold_range",
        ),
        CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
            name="execution_date_range_valid",
        ),
        Index("ix_analyses_document_id_status", "document_id", "status"),
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(
            AnalysisStatus,
            name="analysis_status",
            values_callable=lambda values: [v.value for v in values],
        ),
        default=AnalysisStatus.QUEUED,
        server_default=AnalysisStatus.QUEUED.value,
        nullable=False,
    )
    algorithm_version: Mapped[str] = mapped_column(String(100), nullable=False)
    similarity_threshold: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.8000"),
        server_default="0.8000",
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)

    document: Mapped[Document] = relationship(back_populates="analyses")
    matches: Mapped[list[Match]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Match(BaseModel):
    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint(
            "similarity_score >= 0 AND similarity_score <= 1",
            name="similarity_score_range",
        ),
        CheckConstraint(
            "document_match_start >= 0 AND document_match_end > document_match_start",
            name="document_match_range_valid",
        ),
        CheckConstraint(
            "source_match_start >= 0 AND source_match_end > source_match_start",
            name="source_match_range_valid",
        ),
        CheckConstraint("matched_token_count > 0", name="matched_token_count_positive"),
        UniqueConstraint(
            "analysis_id",
            "document_chunk_id",
            "source_chunk_id",
            "document_match_start",
            "source_match_start",
            name="uq_matches_evidence_location",
        ),
        Index("ix_matches_analysis_id_similarity_score", "analysis_id", "similarity_score"),
        Index("ix_matches_source_chunk_id", "source_chunk_id"),
    )

    analysis_id: Mapped[UUID] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_chunks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    method: Mapped[MatchMethod] = mapped_column(
        Enum(
            MatchMethod,
            name="match_method",
            values_callable=lambda values: [v.value for v in values],
        ),
        nullable=False,
    )
    similarity_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    document_match_start: Mapped[int] = mapped_column(nullable=False)
    document_match_end: Mapped[int] = mapped_column(nullable=False)
    source_match_start: Mapped[int] = mapped_column(nullable=False)
    source_match_end: Mapped[int] = mapped_column(nullable=False)
    matched_token_count: Mapped[int] = mapped_column(nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)

    analysis: Mapped[Analysis] = relationship(back_populates="matches")
    document_chunk: Mapped[DocumentChunk] = relationship(back_populates="matches")
    source_chunk: Mapped[SourceChunk] = relationship(back_populates="matches")
