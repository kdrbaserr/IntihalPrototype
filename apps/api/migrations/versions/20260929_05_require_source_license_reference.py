"""Require a license evidence reference for every source document.

Revision ID: 20260929_05
Revises: 20260927_04
Create Date: 2026-09-29

Source title, license name and SHA-256 checksum were already required by the
initial schema. This revision closes the remaining gap by making the license
evidence reference non-nullable as well.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_05"
down_revision: str | None = "20260927_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "source_documents",
        "license_evidence_reference",
        existing_type=sa.String(length=500),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "source_documents",
        "license_evidence_reference",
        existing_type=sa.String(length=500),
        nullable=True,
    )
