"""Create licensed source documents and chunks.

Revision ID: 20260927_02
Revises: 20260927_01
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260927_02"
down_revision: str | None = "20260927_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

source_document_status = postgresql.ENUM(
    "pending",
    "processing",
    "ready",
    "failed",
    "disabled",
    name="source_document_status",
    create_type=False,
)
license_status = postgresql.ENUM(
    "pending",
    "approved",
    "rejected",
    "expired",
    name="license_status",
    create_type=False,
)


def upgrade() -> None:
    source_document_status.create(op.get_bind(), checkfirst=True)
    license_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "source_documents",
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("author", sa.String(length=300), nullable=True),
        sa.Column("publisher", sa.String(length=300), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("status", source_document_status, server_default="pending", nullable=False),
        sa.Column("license_status", license_status, server_default="pending", nullable=False),
        sa.Column("license_name", sa.String(length=255), nullable=False),
        sa.Column("rights_holder", sa.String(length=300), nullable=False),
        sa.Column("license_url", sa.String(length=2048), nullable=True),
        sa.Column("attribution_text", sa.Text(), nullable=True),
        sa.Column("license_evidence_reference", sa.String(length=500), nullable=True),
        sa.Column("license_valid_from", sa.Date(), nullable=True),
        sa.Column("license_valid_until", sa.Date(), nullable=True),
        sa.Column("license_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_bucket", sa.String(length=63), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("storage_etag", sa.String(length=255), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "license_valid_until IS NULL OR license_valid_from IS NULL "
            "OR license_valid_until >= license_valid_from",
            name=op.f("ck_source_documents_license_date_range_valid"),
        ),
        sa.CheckConstraint(
            "size_bytes >= 0", name=op.f("ck_source_documents_size_bytes_non_negative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_documents")),
        sa.UniqueConstraint(
            "storage_bucket",
            "storage_key",
            name="uq_source_documents_storage_location",
        ),
    )
    op.create_index(
        "ix_source_documents_status_license_status",
        "source_documents",
        ["status", "license_status"],
        unique=False,
    )

    op.create_table(
        "source_chunks",
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("char_end > char_start", name=op.f("ck_source_chunks_char_range_valid")),
        sa.CheckConstraint(
            "char_start >= 0", name=op.f("ck_source_chunks_char_start_non_negative")
        ),
        sa.CheckConstraint(
            "chunk_index >= 0", name=op.f("ck_source_chunks_chunk_index_non_negative")
        ),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number > 0",
            name=op.f("ck_source_chunks_page_number_positive"),
        ),
        sa.CheckConstraint(
            "token_count >= 0", name=op.f("ck_source_chunks_token_count_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["source_documents.id"],
            name=op.f("fk_source_chunks_source_document_id_source_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_chunks")),
        sa.UniqueConstraint(
            "source_document_id",
            "chunk_index",
            name="uq_source_chunks_document_index",
        ),
    )


def downgrade() -> None:
    op.drop_table("source_chunks")
    op.drop_table("source_documents")
    license_status.drop(op.get_bind(), checkfirst=True)
    source_document_status.drop(op.get_bind(), checkfirst=True)
