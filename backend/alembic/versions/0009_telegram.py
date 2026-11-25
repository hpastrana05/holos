"""Store Telegram links and expiring link code hashes."""
import sqlalchemy as sa
from alembic import op

revision = "0009_telegram"
down_revision = "0008_calendar_selections"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("telegram_id", sa.BigInteger()))
    op.add_column("users", sa.Column("telegram_code_hash", sa.String(64)))
    op.add_column("users", sa.Column("telegram_code_expires", sa.Integer()))
    op.add_column("users", sa.Column("telegram_last_message", sa.BigInteger()))
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)
    op.create_index("ix_users_telegram_code_hash", "users", ["telegram_code_hash"], unique=True)


def downgrade():
    op.drop_index("ix_users_telegram_code_hash", table_name="users")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_column("users", "telegram_last_message")
    op.drop_column("users", "telegram_code_expires")
    op.drop_column("users", "telegram_code_hash")
    op.drop_column("users", "telegram_id")
