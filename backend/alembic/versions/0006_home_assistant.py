"""Add household Home Assistant whitelist."""

import sqlalchemy as sa
from alembic import op

revision = "0006_home_assistant"
down_revision = "0005_nutrition"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "home_entities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id"), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("room", sa.String(100), nullable=False),
        sa.Column("domain", sa.String(64), nullable=False),
        sa.Column("sensitive", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("household_id", "entity_id", name="uq_home_entity_household_entity"),
    )
    op.create_index("ix_home_entities_household_id", "home_entities", ["household_id"])


def downgrade():
    op.drop_index("ix_home_entities_household_id", table_name="home_entities")
    op.drop_table("home_entities")
