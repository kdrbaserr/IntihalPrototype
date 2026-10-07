"""Add password hashes and revocable browser sessions."""

import sqlalchemy as sa
from alembic import op

revision = "20261007_08"
down_revision = "20261006_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing users keep their ownership/history but cannot log in until provisioned.
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])

    op.create_table(
        "authentication_throttles",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_authentication_throttles_expires_at", "authentication_throttles", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_table("authentication_throttles")
    op.drop_table("user_sessions")
    op.drop_column("users", "password_hash")
