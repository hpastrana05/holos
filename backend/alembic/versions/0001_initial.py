"""initial schema"""
from alembic import op
import sqlalchemy as sa
revision="0001_initial";down_revision=None;branch_labels=None;depends_on=None
def upgrade():
    op.create_table("households",sa.Column("id",sa.Integer,primary_key=True),sa.Column("name",sa.String(120),nullable=False,unique=True),sa.Column("created_at",sa.DateTime,nullable=False))
    op.create_table("users",sa.Column("id",sa.Integer,primary_key=True),sa.Column("email",sa.String(255),nullable=False,unique=True),sa.Column("password_hash",sa.String(255),nullable=False),sa.Column("role",sa.Enum("admin","member",name="role"),nullable=False),sa.Column("household_id",sa.Integer,sa.ForeignKey("households.id"),nullable=False),sa.Column("is_active",sa.Boolean,nullable=False))
    op.create_table("health_profiles",sa.Column("id",sa.Integer,primary_key=True),sa.Column("user_id",sa.Integer,sa.ForeignKey("users.id"),nullable=False,unique=True),sa.Column("height_cm",sa.Float,nullable=False),sa.Column("birth_date",sa.Date,nullable=False),sa.Column("sex",sa.String(16),nullable=False),sa.Column("activity_level",sa.String(32),nullable=False))
    op.create_table("weight_entries",sa.Column("id",sa.Integer,primary_key=True),sa.Column("user_id",sa.Integer,sa.ForeignKey("users.id"),nullable=False),sa.Column("date",sa.Date,nullable=False),sa.Column("weight_kg",sa.Float,nullable=False),sa.Column("source",sa.String(32),nullable=False),sa.Column("notes",sa.Text))
    op.create_table("weight_goals",sa.Column("id",sa.Integer,primary_key=True),sa.Column("user_id",sa.Integer,sa.ForeignKey("users.id"),nullable=False),sa.Column("start_weight_kg",sa.Float,nullable=False),sa.Column("target_weight_kg",sa.Float,nullable=False),sa.Column("start_date",sa.Date,nullable=False),sa.Column("target_date",sa.Date),sa.Column("weekly_rate_kg",sa.Float,nullable=False),sa.Column("mode",sa.String(32),nullable=False),sa.Column("active",sa.Boolean,nullable=False))
    op.create_table("categories",sa.Column("id",sa.Integer,primary_key=True),sa.Column("household_id",sa.Integer,sa.ForeignKey("households.id"),nullable=False),sa.Column("name",sa.String(100),nullable=False),sa.Column("kind",sa.Enum("income","expense",name="transactiontype"),nullable=False))
    op.create_table("transactions",sa.Column("id",sa.Integer,primary_key=True),sa.Column("user_id",sa.Integer,sa.ForeignKey("users.id"),nullable=False),sa.Column("household_id",sa.Integer,sa.ForeignKey("households.id"),nullable=False),sa.Column("kind",sa.Enum("income","expense",name="transactiontype"),nullable=False),sa.Column("amount",sa.Numeric(12,2),nullable=False),sa.Column("category_id",sa.Integer,sa.ForeignKey("categories.id")),sa.Column("date",sa.Date,nullable=False),sa.Column("note",sa.Text),sa.Column("visibility",sa.Enum("personal","shared",name="visibility"),nullable=False))
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_household_id", "users", ["household_id"])
    op.create_index("ix_health_profiles_user_id", "health_profiles", ["user_id"])
    op.create_index("ix_weight_entries_user_id", "weight_entries", ["user_id"])
    op.create_index("ix_weight_entries_date", "weight_entries", ["date"])
    op.create_index("ix_weight_goals_user_id", "weight_goals", ["user_id"])
    op.create_index("ix_categories_household_id", "categories", ["household_id"])
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
    op.create_index("ix_transactions_household_id", "transactions", ["household_id"])
    op.create_index("ix_transactions_date", "transactions", ["date"])
def downgrade():
    op.drop_table("transactions");op.drop_table("categories");op.drop_table("weight_goals");op.drop_table("weight_entries");op.drop_table("health_profiles");op.drop_table("users");op.drop_table("households")
