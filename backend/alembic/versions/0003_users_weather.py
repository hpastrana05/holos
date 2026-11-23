"""Add user presentation, screen PINs and household weather location."""

import sqlalchemy as sa
from alembic import op

revision = "0003_users_weather"
down_revision = "0002_category_budgets"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("display_name", sa.String(80), nullable=True))
    op.add_column(
        "users",
        sa.Column("color", sa.String(7), nullable=False, server_default="#b7a7ff"),
    )
    op.add_column(
        "users",
        sa.Column("avatar", sa.String(16), nullable=False, server_default="initial"),
    )
    op.add_column("users", sa.Column("screen_pin_hash", sa.String(255), nullable=True))
    op.add_column(
        "users",
        sa.Column("screen_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "households",
        sa.Column(
            "weather_name", sa.String(120), nullable=False, server_default="Toledo"
        ),
    )
    op.add_column(
        "households",
        sa.Column(
            "weather_latitude", sa.Float(), nullable=False, server_default="39.8628"
        ),
    )
    op.add_column(
        "households",
        sa.Column(
            "weather_longitude", sa.Float(), nullable=False, server_default="-4.0273"
        ),
    )


def downgrade():
    with op.batch_alter_table("users") as batch:
        for column in (
            "display_name",
            "color",
            "avatar",
            "screen_pin_hash",
            "screen_version",
        ):
            batch.drop_column(column)
    with op.batch_alter_table("households") as batch:
        for column in ("weather_name", "weather_latitude", "weather_longitude"):
            batch.drop_column(column)
