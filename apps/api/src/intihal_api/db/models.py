from __future__ import annotations

import enum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    String,
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
