"""Persist explainable score components for each match."""

import sqlalchemy as sa
from alembic import op

revision = "20261006_08"
down_revision = "20261006_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("score_components", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("matches", "score_components")
