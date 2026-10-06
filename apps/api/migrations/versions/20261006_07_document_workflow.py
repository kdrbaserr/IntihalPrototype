"""Introduce the document processing state machine and durable retry metadata."""

import sqlalchemy as sa
from alembic import op

revision = "20261006_07"
down_revision = "20260929_06"
branch_labels = None
depends_on = None


def _replace_status(values: str, mapping: str) -> None:
    op.execute("ALTER TABLE documents ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE document_status RENAME TO document_status_old")
    op.execute(f"CREATE TYPE document_status AS ENUM ({values})")
    op.execute(
        "ALTER TABLE documents ALTER COLUMN status TYPE document_status "
        f"USING ({mapping})::document_status"
    )
    op.execute("ALTER TABLE documents ALTER COLUMN status SET DEFAULT 'uploaded'")
    op.execute("DROP TYPE document_status_old")


def upgrade() -> None:
    _replace_status(
        "'uploaded', 'queued', 'extracting', 'analyzing', 'completed', 'failed', 'deleted'",
        "CASE status::text WHEN 'ready' THEN 'uploaded' "
        "WHEN 'processing' THEN 'failed' ELSE status::text END",
    )
    op.add_column("documents", sa.Column("failure_reason", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("processing_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("documents", sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
    op.add_column(
        "analyses", sa.Column("config_snapshot", sa.JSON(), server_default="{}", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("analyses", "config_snapshot")
    op.drop_column("documents", "next_attempt_at")
    op.drop_column("documents", "processing_attempts")
    op.drop_column("documents", "failure_reason")
    _replace_status(
        "'uploaded', 'processing', 'ready', 'failed', 'deleted'",
        "CASE status::text WHEN 'queued' THEN 'uploaded' "
        "WHEN 'extracting' THEN 'processing' WHEN 'analyzing' THEN 'processing' "
        "WHEN 'completed' THEN 'ready' ELSE status::text END",
    )
