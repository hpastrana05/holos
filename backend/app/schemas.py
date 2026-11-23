from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.models import MealSource, MealType, TransactionType, Visibility


class ORM(BaseModel): model_config = ConfigDict(from_attributes=True)
class LoginIn(BaseModel): email: str; password: str
class Token(BaseModel): access_token: str; token_type: str = "bearer"
class HealthProfileIn(BaseModel): height_cm: float = Field(gt=50, lt=300); birth_date: date; sex: str; activity_level: str
class HealthProfileOut(HealthProfileIn, ORM): id: int; user_id: int
class WeightEntryIn(BaseModel): date: date; weight_kg: float = Field(gt=20, lt=500); source: str = "manual"; notes: str | None = None
class WeightEntryOut(WeightEntryIn, ORM): id: int; user_id: int
class WeightGoalIn(BaseModel): start_weight_kg: float; target_weight_kg: float; start_date: date; target_date: date | None = None; weekly_rate_kg: float = Field(default=0.5, gt=0, le=1); mode: str = "lose"; active: bool = True
class WeightGoalOut(WeightGoalIn, ORM): id: int; user_id: int
class CategoryIn(BaseModel): name: str = Field(min_length=1, max_length=100); kind: TransactionType
class CategoryOut(CategoryIn, ORM): id: int; household_id: int
class CategoryBudgetIn(BaseModel): category_id: int; year: int = Field(ge=2000, le=2100); month: int = Field(ge=1, le=12); amount: float = Field(gt=0)
class CategoryBudgetOut(CategoryBudgetIn, ORM): id: int; household_id: int
class TransactionIn(BaseModel): kind: TransactionType; amount: float = Field(gt=0); category_id: int | None = None; date: date; note: str | None = None; visibility: Visibility = Visibility.personal
class TransactionOut(TransactionIn, ORM): id: int; user_id: int; household_id: int


class ScreenTransaction(ORM):
    id: int
    date: date
    kind: TransactionType
    amount: float


class ScreenSummary(BaseModel):
    user_name: str
    current_weight_kg: float | None
    target_kcal: int | None
    monthly_balance: float
    recent_transactions: list[ScreenTransaction]

class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)

class AgentChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)

class AgentActionOut(BaseModel):
    tool: str
    result: str

class AgentChatOut(BaseModel):
    response: str
    actions: list[AgentActionOut]

class NutritionGoalIn(BaseModel):
    protein_g: float = Field(gt=0, le=500)
    carbs_g: float = Field(gt=0, le=1000)
    fat_g: float = Field(gt=0, le=500)
class NutritionGoalOut(NutritionGoalIn, ORM): id: int; user_id: int; kcal: int
class MealIn(BaseModel):
    eaten_at: datetime
    meal_type: MealType
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    kcal: float = Field(ge=0, le=10000)
    protein_g: float = Field(ge=0, le=1000)
    carbs_g: float = Field(ge=0, le=1000)
    fat_g: float = Field(ge=0, le=1000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    source: MealSource = MealSource.manual
class MealOut(MealIn, ORM): id: int; user_id: int
class MealEstimate(MealIn): pass
class NutritionAnalysisOut(BaseModel): meals: list[MealEstimate]; note: str = "Estimación orientativa; revisa antes de guardar."
