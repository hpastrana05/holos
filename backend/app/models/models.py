import enum
from typing import Optional
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class Role(str, enum.Enum): admin = "admin"; member = "member"
class Visibility(str, enum.Enum): personal = "personal"; shared = "shared"
class TransactionType(str, enum.Enum): income = "income"; expense = "expense"
class MealType(str, enum.Enum): breakfast = "breakfast"; lunch = "lunch"; dinner = "dinner"; snack = "snack"
class MealSource(str, enum.Enum): photo = "photo"; text = "text"; manual = "manual"

class Household(Base):
    __tablename__ = "households"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    weather_name: Mapped[str] = mapped_column(String(120), default="Toledo")
    weather_latitude: Mapped[float] = mapped_column(Float, default=39.8628)
    weather_longitude: Mapped[float] = mapped_column(Float, default=-4.0273)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    color: Mapped[str] = mapped_column(String(7), default="#b7a7ff")
    avatar: Mapped[str] = mapped_column(String(16), default="initial")
    screen_pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    screen_version: Mapped[int] = mapped_column(Integer, default=0)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.member)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class HealthProfile(Base):
    __tablename__ = "health_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    height_cm: Mapped[float] = mapped_column(Float)
    birth_date: Mapped[date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(String(16))
    activity_level: Mapped[str] = mapped_column(String(32))

class WeightEntry(Base):
    __tablename__ = "weight_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    weight_kg: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

class WeightGoal(Base):
    __tablename__ = "weight_goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    start_weight_kg: Mapped[float] = mapped_column(Float)
    target_weight_kg: Mapped[float] = mapped_column(Float)
    start_date: Mapped[date] = mapped_column(Date)
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    weekly_rate_kg: Mapped[float] = mapped_column(Float, default=0.5)
    mode: Mapped[str] = mapped_column(String(32), default="lose")
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[TransactionType] = mapped_column(Enum(TransactionType))

class CategoryBudget(Base):
    __tablename__ = "category_budgets"
    __table_args__ = (UniqueConstraint("household_id", "category_id", "year", "month", name="uq_category_budget_period"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))

class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    kind: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visibility: Mapped[Visibility] = mapped_column(Enum(Visibility), default=Visibility.personal)

class AgentAction(Base):
    __tablename__ = "agent_actions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    tool: Mapped[str] = mapped_column(String(80))
    arguments: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

class NutritionGoal(Base):
    __tablename__ = "nutrition_goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    protein_g: Mapped[float] = mapped_column(Float, default=100)
    carbs_g: Mapped[float] = mapped_column(Float, default=225)
    fat_g: Mapped[float] = mapped_column(Float, default=67)

class Meal(Base):
    __tablename__ = "meals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    eaten_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    meal_type: Mapped[MealType] = mapped_column(Enum(MealType))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    kcal: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float] = mapped_column(Float, default=0)
    carbs_g: Mapped[float] = mapped_column(Float, default=0)
    fat_g: Mapped[float] = mapped_column(Float, default=0)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[MealSource] = mapped_column(Enum(MealSource), default=MealSource.manual)

class HomeEntity(Base):
    __tablename__ = "home_entities"
    __table_args__ = (UniqueConstraint("household_id", "entity_id", name="uq_home_entity_household_entity"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    entity_id: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(160))
    room: Mapped[str] = mapped_column(String(100), default="Sin estancia")
    domain: Mapped[str] = mapped_column(String(64))
    sensitive: Mapped[bool] = mapped_column(Boolean, default=False)

class CalendarCredential(Base):
    __tablename__ = "calendar_credentials"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    connected: Mapped[bool] = mapped_column(Boolean, default=False)
    calendar_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    selected_calendar_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
