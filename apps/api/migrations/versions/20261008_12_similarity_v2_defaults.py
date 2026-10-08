"""Update the default threshold for new analyses without rewriting snapshots."""

from alembic import op

revision = "20261008_12"
down_revision = "20261008_11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("analyses", "similarity_threshold", server_default="0.7500")


def downgrade() -> None:
    op.alter_column("analyses", "similarity_threshold", server_default="0.8000")
