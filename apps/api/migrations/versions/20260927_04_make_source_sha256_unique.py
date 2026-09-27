"""Prevent the same source file from entering the licensed corpus twice.

Revision ID: 20260927_04
Revises: 20260927_03
Create Date: 2026-09-27

The checksum is unique only for source documents.  Uploaded user documents may
legitimately contain the same bytes when they belong to different users.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260927_04"
down_revision: str | None = "20260927_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_source_documents_sha256",
        "source_documents",
        ["sha256"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_source_documents_sha256",
        "source_documents",
        type_="unique",
    )
