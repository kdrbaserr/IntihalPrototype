"""Minimal operation history without content or credentials."""

import sqlalchemy as sa
from alembic import op

revision = "20261007_10"
down_revision = "20261007_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("actor_id", sa.Uuid()),
        sa.Column("actor_kind", sa.String(16), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("resource_type", sa.String(16), nullable=False),
        sa.Column("resource_id", sa.Uuid()),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.CheckConstraint("actor_kind IN ('user', 'system', 'operator')", name="actor_kind_valid"),
        sa.CheckConstraint("outcome IN ('started', 'succeeded', 'failed')", name="outcome_valid"),
        sa.CheckConstraint(
            "resource_type IN ('document', 'source', 'user')", name="resource_type_valid"
        ),
        sa.CheckConstraint(
            "action IN ('document.upload', 'document.delete', 'admin.source.create', "
            "'admin.source.list', 'admin.source.disable', 'admin.source.reindex', "
            "'admin.user.provision')",
            name="action_valid",
        ),
        sa.CheckConstraint(
            "(actor_kind = 'user' AND actor_id IS NOT NULL) OR "
            "(actor_kind IN ('system', 'operator') AND actor_id IS NULL)",
            name="actor_identity_valid",
        ),
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])
    op.create_index(
        "ix_audit_events_resource", "audit_events", ["resource_type", "resource_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("audit_events")
