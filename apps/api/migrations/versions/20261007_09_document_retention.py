"""Bound document retention and track retryable cleanup completion."""

import sqlalchemy as sa
from alembic import op

revision = "20261007_09"
down_revision = "20261007_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents", sa.Column("retention_days", sa.Integer(), nullable=False, server_default="7")
    )
    op.add_column("documents", sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.add_column("documents", sa.Column("cleaned_at", sa.DateTime(timezone=True)))
    # Give existing documents a full grace period from rollout, not their original upload.
    op.execute(
        "UPDATE documents SET retention_days = 30, "
        "expires_at = CURRENT_TIMESTAMP + INTERVAL '30 days'"
    )
    op.alter_column("documents", "expires_at", nullable=False)
    op.create_check_constraint("retention_days_valid", "documents", "retention_days IN (7, 30)")
    op.create_index("ix_documents_expires_at", "documents", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_documents_expires_at", table_name="documents")
    op.drop_constraint(op.f("ck_documents_retention_days_valid"), "documents", type_="check")
    op.drop_column("documents", "cleaned_at")
    op.drop_column("documents", "expires_at")
    op.drop_column("documents", "retention_days")
