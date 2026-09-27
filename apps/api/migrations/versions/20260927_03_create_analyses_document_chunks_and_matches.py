"""Create analyses, uploaded document chunks, and matches.

Revision ID: 20260927_03
Revises: 20260927_02
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260927_03"
down_revision: str | None = "20260927_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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


def upgrade() -> None:
    analysis_status.create(op.get_bind(), checkfirst=True)
    match_method.create(op.get_bind(), checkfirst=True)

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
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_document_index",
        ),
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
        "ix_analyses_document_id_status",
        "analyses",
        ["document_id", "status"],
        unique=False,
    )

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
    op.create_index(
        "ix_matches_source_chunk_id",
        "matches",
        ["source_chunk_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("matches")
    op.drop_table("analyses")
    op.drop_table("document_chunks")
    match_method.drop(op.get_bind(), checkfirst=True)
    analysis_status.drop(op.get_bind(), checkfirst=True)
