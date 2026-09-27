"""Create the initial application schema.

Revision ID: 20260927_03
Revises:
Create Date: 2026-09-27

This is the baseline migration for the B02 data model.  It deliberately keeps
schema creation in one revision because no released installation predates this
schema yet.  The revision identifier matches the former development-chain head,
so existing developer databases remain recognizable after consolidation.  Future
model changes must be added as new revisions instead of editing this baseline.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260927_03"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# PostgreSQL enum types are schema objects of their own.  ``create_type=False``
# prevents table creation from trying to create the same type more than once;
# upgrade() and downgrade() manage their lifecycle explicitly instead.
user_status = postgresql.ENUM("active", "disabled", name="user_status", create_type=False)
document_status = postgresql.ENUM(
    "uploaded",
    "processing",
    "ready",
    "failed",
    "deleted",
    name="document_status",
    create_type=False,
)
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
analysis_status = postgresql.ENUM(
    "queued",
    "processing",
    "completed",
    "failed",
    "cancelled",
    name="analysis_status",
    create_type=False,
)
match_method = postgresql.ENUM(
    "exact",
    "lexical",
    "semantic",
    "hybrid",
    name="match_method",
    create_type=False,
)

enum_types = (
    user_status,
    document_status,
    source_document_status,
    license_status,
    analysis_status,
    match_method,
)


def upgrade() -> None:
    """Create enum types, parent tables, child tables, and lookup indexes."""

    bind = op.get_bind()
    for enum_type in enum_types:
        enum_type.create(bind, checkfirst=True)

    # Parent tables come first so every foreign key can be created immediately.
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("status", user_status, server_default="active", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_status"), "users", ["status"], unique=False)

    op.create_table(
        "documents",
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", document_status, server_default="uploaded", nullable=False),
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
        sa.CheckConstraint("size_bytes >= 0", name=op.f("ck_documents_size_bytes_non_negative")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_documents_owner_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("storage_bucket", "storage_key", name="uq_documents_storage_location"),
    )
    op.create_index("ix_documents_owner_id_status", "documents", ["owner_id", "status"])
    op.create_index(op.f("ix_documents_status"), "documents", ["status"], unique=False)

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
            "storage_bucket", "storage_key", name="uq_source_documents_storage_location"
        ),
    )
    op.create_index(
        "ix_source_documents_status_license_status",
        "source_documents",
        ["status", "license_status"],
        unique=False,
    )

    # Chunk tables retain source locations so a match can be traced to both texts.
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
            "source_document_id", "chunk_index", name="uq_source_chunks_document_index"
        ),
    )

    op.create_table(
        "document_chunks",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.CheckConstraint(
            "char_end > char_start", name=op.f("ck_document_chunks_char_range_valid")
        ),
        sa.CheckConstraint(
            "char_start >= 0", name=op.f("ck_document_chunks_char_start_non_negative")
        ),
        sa.CheckConstraint(
            "chunk_index >= 0", name=op.f("ck_document_chunks_chunk_index_non_negative")
        ),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number > 0",
            name=op.f("ck_document_chunks_page_number_positive"),
        ),
        sa.CheckConstraint(
            "token_count >= 0", name=op.f("ck_document_chunks_token_count_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_chunks_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunks")),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_document_index"),
    )

    op.create_table(
        "analyses",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", analysis_status, server_default="queued", nullable=False),
        sa.Column("algorithm_version", sa.String(length=100), nullable=False),
        sa.Column(
            "similarity_threshold",
            sa.Numeric(precision=5, scale=4),
            server_default="0.8000",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
            name=op.f("ck_analyses_execution_date_range_valid"),
        ),
        sa.CheckConstraint(
            "similarity_threshold >= 0 AND similarity_threshold <= 1",
            name=op.f("ck_analyses_similarity_threshold_range"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_analyses_document_id_documents"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analyses")),
    )
    op.create_index(
        "ix_analyses_document_id_status", "analyses", ["document_id", "status"], unique=False
    )

    # Matches are created last because they reference three previously-created tables.
    op.create_table(
        "matches",
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("method", match_method, nullable=False),
        sa.Column("similarity_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("document_match_start", sa.Integer(), nullable=False),
        sa.Column("document_match_end", sa.Integer(), nullable=False),
        sa.Column("source_match_start", sa.Integer(), nullable=False),
        sa.Column("source_match_end", sa.Integer(), nullable=False),
        sa.Column("matched_token_count", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "document_match_start >= 0 AND document_match_end > document_match_start",
            name=op.f("ck_matches_document_match_range_valid"),
        ),
        sa.CheckConstraint(
            "matched_token_count > 0", name=op.f("ck_matches_matched_token_count_positive")
        ),
        sa.CheckConstraint(
            "similarity_score >= 0 AND similarity_score <= 1",
            name=op.f("ck_matches_similarity_score_range"),
        ),
        sa.CheckConstraint(
            "source_match_start >= 0 AND source_match_end > source_match_start",
            name=op.f("ck_matches_source_match_range_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analyses.id"],
            name=op.f("fk_matches_analysis_id_analyses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_chunk_id"],
            ["document_chunks.id"],
            name=op.f("fk_matches_document_chunk_id_document_chunks"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_chunk_id"],
            ["source_chunks.id"],
            name=op.f("fk_matches_source_chunk_id_source_chunks"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matches")),
        sa.UniqueConstraint(
            "analysis_id",
            "document_chunk_id",
            "source_chunk_id",
            "document_match_start",
            "source_match_start",
            name="uq_matches_evidence_location",
        ),
    )
    op.create_index(
        "ix_matches_analysis_id_similarity_score",
        "matches",
        ["analysis_id", "similarity_score"],
        unique=False,
    )
    op.create_index("ix_matches_source_chunk_id", "matches", ["source_chunk_id"], unique=False)


def downgrade() -> None:
    """Remove the complete initial schema in reverse dependency order."""

    # Dropping children before parents avoids foreign-key dependency failures.
    op.drop_table("matches")
    op.drop_table("analyses")
    op.drop_table("document_chunks")
    op.drop_table("source_chunks")
    op.drop_table("source_documents")
    op.drop_table("documents")
    op.drop_table("users")

    # Enum types can only be removed after every column using them is gone.
    bind = op.get_bind()
    for enum_type in reversed(enum_types):
        enum_type.drop(bind, checkfirst=True)
