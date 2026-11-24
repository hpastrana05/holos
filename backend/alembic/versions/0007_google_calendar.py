"""Add encrypted per-user Google Calendar credentials."""
import sqlalchemy as sa
from alembic import op

revision = "0007_google_calendar"
down_revision = "0006_home_assistant"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("calendar_credentials", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("refresh_token_encrypted", sa.Text(), nullable=True), sa.Column("connected", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("calendar_email", sa.String(255), nullable=True), sa.Column("updated_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("user_id"))
    op.create_index("ix_calendar_credentials_user_id", "calendar_credentials", ["user_id"])

def downgrade():
    op.drop_index("ix_calendar_credentials_user_id", table_name="calendar_credentials")
    op.drop_table("calendar_credentials")
