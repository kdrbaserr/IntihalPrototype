from __future__ import annotations

import enum
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
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
