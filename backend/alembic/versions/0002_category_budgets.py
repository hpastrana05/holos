"""add monthly category budgets"""
from alembic import op
import sqlalchemy as sa

revision = "0002_category_budgets"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("category_budgets", sa.Column("id", sa.Integer, primary_key=True), sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id"), nullable=False), sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.id"), nullable=False), sa.Column("year", sa.Integer, nullable=False), sa.Column("month", sa.Integer, nullable=False), sa.Column("amount", sa.Numeric(12, 2), nullable=False), sa.UniqueConstraint("household_id", "category_id", "year", "month", name="uq_category_budget_period"))
    op.create_index("ix_category_budgets_household_id", "category_budgets", ["household_id"])
    op.create_index("ix_category_budgets_category_id", "category_budgets", ["category_id"])

def downgrade():
    op.drop_table("category_budgets")
