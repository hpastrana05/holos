"""Add the audit log for agent tool actions."""

import sqlalchemy as sa
from alembic import op

revision = "0004_agent_actions"
down_revision = "0003_users_weather"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tool", sa.String(80), nullable=False),
        sa.Column("arguments", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_agent_actions_user_id", "agent_actions", ["user_id"])
    op.create_index("ix_agent_actions_created_at", "agent_actions", ["created_at"])


def downgrade():
    op.drop_index("ix_agent_actions_created_at", table_name="agent_actions")
    op.drop_index("ix_agent_actions_user_id", table_name="agent_actions")
    op.drop_table("agent_actions")
