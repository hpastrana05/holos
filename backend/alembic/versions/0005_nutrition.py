"""Add meals and per-user nutrition macro goals."""

import sqlalchemy as sa
from alembic import op

revision = "0005_nutrition"
down_revision = "0004_agent_actions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("nutrition_goals", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("protein_g", sa.Float(), nullable=False), sa.Column("carbs_g", sa.Float(), nullable=False), sa.Column("fat_g", sa.Float(), nullable=False), sa.UniqueConstraint("user_id"))
    op.create_index("ix_nutrition_goals_user_id", "nutrition_goals", ["user_id"])
    op.create_table("meals", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("eaten_at", sa.DateTime(), nullable=False), sa.Column("meal_type", sa.Enum("breakfast", "lunch", "dinner", "snack", name="mealtype"), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("description", sa.Text(), nullable=True), sa.Column("kcal", sa.Float(), nullable=False), sa.Column("protein_g", sa.Float(), nullable=False), sa.Column("carbs_g", sa.Float(), nullable=False), sa.Column("fat_g", sa.Float(), nullable=False), sa.Column("confidence", sa.Float(), nullable=True), sa.Column("source", sa.Enum("photo", "text", "manual", name="mealsource"), nullable=False))
    op.create_index("ix_meals_user_id", "meals", ["user_id"])
    op.create_index("ix_meals_eaten_at", "meals", ["eaten_at"])


def downgrade():
    op.drop_index("ix_meals_eaten_at", table_name="meals"); op.drop_index("ix_meals_user_id", table_name="meals"); op.drop_table("meals")
    op.drop_index("ix_nutrition_goals_user_id", table_name="nutrition_goals"); op.drop_table("nutrition_goals")
