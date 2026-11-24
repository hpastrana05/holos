"""Store each user's visible Google calendars."""
import sqlalchemy as sa
from alembic import op

revision = "0008_calendar_selections"
down_revision = "0007_google_calendar"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("calendar_credentials", sa.Column("selected_calendar_ids", sa.Text(), nullable=True))

def downgrade():
    op.drop_column("calendar_credentials", "selected_calendar_ids")
