from __future__ import annotations

import enum
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intihal_api.db.base import Base, BaseModel


class UserStatus(enum.StrEnum):
    """Whether an account may currently use the application."""

    ACTIVE = "active"
    DISABLED = "disabled"


class UserRole(enum.StrEnum):
    """Authorization role assigned to an application account."""

    USER = "user"
    ADMIN = "admin"


class DocumentStatus(enum.StrEnum):
    """Lifecycle state of a document and its analysis."""

    UPLOADED = "uploaded"
    QUEUED = "queued"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
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
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda values: [v.value for v in values]),
        default=UserRole.USER,
        server_default=UserRole.USER.value,
        nullable=False,
    )

    password_hash: Mapped[str | None] = mapped_column(String(255))

    documents: Mapped[list[Document]] = relationship(
        back_populates="owner",
        passive_deletes=True,
    )


class UserSession(BaseModel):
    """Only the digest of a random browser credential is persisted."""

    __tablename__ = "user_sessions"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class Document(BaseModel):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="size_bytes_non_negative"),
        UniqueConstraint("storage_bucket", "storage_key", name="uq_documents_storage_location"),
        Index("ix_documents_owner_id_status", "owner_id", "status"),
        CheckConstraint("retention_days IN (7, 30)", name="retention_days_valid"),
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
    failure_reason: Mapped[str | None] = mapped_column(Text)
    processing_attempts: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_days: Mapped[int] = mapped_column(default=7, server_default="7", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC) + timedelta(days=7),
        nullable=False,
        index=True,
    )
    cleaned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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
        UniqueConstraint("sha256", name="uq_source_documents_sha256"),
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
    license_evidence_reference: Mapped[str] = mapped_column(String(500), nullable=False)
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
        default=Decimal("0.7500"),
        server_default="0.7500",
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    config_snapshot: Mapped[dict[str, str]] = mapped_column(
        JSON, default=dict, server_default="{}", nullable=False
    )

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
    score_components: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    document_match_start: Mapped[int] = mapped_column(nullable=False)
    document_match_end: Mapped[int] = mapped_column(nullable=False)
    source_match_start: Mapped[int] = mapped_column(nullable=False)
    source_match_end: Mapped[int] = mapped_column(nullable=False)
    matched_token_count: Mapped[int] = mapped_column(nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)

    analysis: Mapped[Analysis] = relationship(back_populates="matches")
    document_chunk: Mapped[DocumentChunk] = relationship(back_populates="matches")
    source_chunk: Mapped[SourceChunk] = relationship(back_populates="matches")


class AuthenticationThrottle(Base):
    """Shared fixed-window limits across API processes, without storing raw identities."""

    __tablename__ = "authentication_throttles"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class AuditEvent(Base):
    """Minimal event history: no payload, credentials, filenames or free-form metadata."""

    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("actor_kind IN ('user', 'system', 'operator')", name="actor_kind_valid"),
        CheckConstraint("outcome IN ('started', 'succeeded', 'failed')", name="outcome_valid"),
        CheckConstraint(
            "resource_type IN ('document', 'source', 'user')", name="resource_type_valid"
        ),
        CheckConstraint(
            "action IN ('document.upload', 'document.delete', 'admin.source.create', "
            "'admin.source.list', 'admin.source.disable', 'admin.source.reindex', "
            "'admin.user.provision')",
            name="action_valid",
        ),
        CheckConstraint(
            "(actor_kind = 'user' AND actor_id IS NOT NULL) OR "
            "(actor_kind IN ('system', 'operator') AND actor_id IS NULL)",
            name="actor_identity_valid",
        ),
        Index("ix_audit_events_resource", "resource_type", "resource_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    # Deliberately no FK: deleting a resource/account must not erase its audit history.
    actor_id: Mapped[UUID | None] = mapped_column(index=True)
    actor_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(16), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column()
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
