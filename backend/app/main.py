from calendar import monthrange
from datetime import date, datetime
from secrets import compare_digest
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_token, current_user, verify_password
from app.db.session import get_db
from app.models.models import (
    Category,
    CategoryBudget,
    HealthProfile,
    Transaction,
    TransactionType,
    User,
    WeightEntry,
    WeightGoal,
)
from app.schemas import (
    CategoryBudgetIn,
    CategoryBudgetOut,
    CategoryIn,
    CategoryOut,
    HealthProfileIn,
    HealthProfileOut,
    LoginIn,
    ScreenSummary,
    Token,
    TransactionIn,
    TransactionOut,
    WeightEntryIn,
    WeightEntryOut,
    WeightGoalIn,
    WeightGoalOut,
)
from app.services.health import estimate_arrival, target_kcal

app = FastAPI(title="Holos API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8080"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def owned(model, item_id, user, db):
    item = db.query(model).filter(model.id == item_id, model.user_id == user.id).first()
    if not item: raise HTTPException(404, "No encontrado")
    return item
def household_item(model, item_id, user, db):
    item = db.query(model).filter(model.id == item_id, model.household_id == user.household_id).first()
    if not item: raise HTTPException(404, "No encontrado")
    return item
def visible_transactions(user): return or_(Transaction.user_id == user.id, and_(Transaction.household_id == user.household_id, Transaction.visibility == "shared"))
def period(year, month): return date(year, month, 1), date(year, month, monthrange(year, month)[1])
def health_data(user, db):
    entries = db.query(WeightEntry).filter_by(user_id=user.id).order_by(WeightEntry.date).all(); profile = db.query(HealthProfile).filter_by(user_id=user.id).first(); goal = db.query(WeightGoal).filter_by(user_id=user.id, active=True).first()
    current = entries[-1].weight_kg if entries else None
    kcal = daily_kcal(profile, current, goal)
    remaining = max(0, abs(goal.target_weight_kg - current)) if goal and current is not None else None
    initial = goal.start_weight_kg if goal else (entries[0].weight_kg if entries else None)
    progress = (abs(initial - current) / abs(initial - goal.target_weight_kg) * 100) if goal and current is not None and initial != goal.target_weight_kg else None
    return {"current_weight_kg": current, "target_weight_kg": goal.target_weight_kg if goal else None, "remaining_kg": remaining, "progress_pct": min(100, round(progress, 1)) if progress is not None else None, "trend_kg": current - entries[0].weight_kg if len(entries) > 1 else None, "estimated_goal_date": estimate_arrival(current, goal.target_weight_kg, goal.weekly_rate_kg).isoformat() if current is not None and goal else None, "target_kcal": kcal, "entries": [{"date": entry.date.isoformat(), "weight_kg": entry.weight_kg} for entry in entries]}

def daily_kcal(profile, weight, goal):
    if profile and weight:
        return target_kcal(
            profile.height_cm, profile.birth_date, profile.sex,
            profile.activity_level, weight, goal.target_weight_kg if goal else None,
        )
    return None


@app.get("/screen/summary", response_model=ScreenSummary)
def screen_summary(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    x_screen_token: Annotated[str, Header()] = "",
):
    if not settings.screen_token or not compare_digest(
        x_screen_token.encode(), settings.screen_token.encode()
    ):
        raise HTTPException(401, "Token de pantalla inválido")
    user = db.query(User).filter_by(email=settings.screen_user_email, is_active=True).first()
    if not user:
        raise HTTPException(401, "Pantalla sin usuario autorizado")

    today = datetime.now(ZoneInfo("Europe/Madrid")).date()
    latest = (
        db.query(WeightEntry).filter_by(user_id=user.id)
        .order_by(WeightEntry.date.desc(), WeightEntry.id.desc()).first()
    )
    weight = latest.weight_kg if latest else None
    profile = db.query(HealthProfile).filter_by(user_id=user.id).first()
    goal = db.query(WeightGoal).filter_by(user_id=user.id, active=True).first()
    recent = (
        db.query(Transaction).filter(visible_transactions(user), Transaction.date <= today)
        .order_by(Transaction.date.desc(), Transaction.id.desc()).limit(3).all()
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "current_weight_kg": weight,
        "target_kcal": daily_kcal(profile, weight, goal),
        "monthly_balance": summary_for_range(*period(today.year, today.month), user, db)["balance"],
        "recent_transactions": recent,
    }


@app.get("/health")
def health(): return {"status": "ok"}
@app.post("/auth/login", response_model=Token)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash): raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales incorrectas")
    return Token(access_token=create_token(user))

@app.get("/health/profile", response_model=HealthProfileOut | None)
def get_profile(user: User = Depends(current_user), db: Session = Depends(get_db)): return db.query(HealthProfile).filter_by(user_id=user.id).first()
@app.put("/health/profile", response_model=HealthProfileOut)
def put_profile(data: HealthProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.query(HealthProfile).filter_by(user_id=user.id).first()
    if profile:
        for key, value in data.model_dump().items(): setattr(profile, key, value)
    else: profile = HealthProfile(user_id=user.id, **data.model_dump()); db.add(profile)
    db.commit(); db.refresh(profile); return profile
@app.get("/health/weights", response_model=list[WeightEntryOut])
def list_weights(user: User = Depends(current_user), db: Session = Depends(get_db)): return db.query(WeightEntry).filter_by(user_id=user.id).order_by(WeightEntry.date).all()
@app.post("/health/weights", response_model=WeightEntryOut, status_code=201)
def add_weight(data: WeightEntryIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = WeightEntry(user_id=user.id, **data.model_dump()); db.add(item); db.commit(); db.refresh(item); return item
@app.put("/health/weights/{item_id}", response_model=WeightEntryOut)
def edit_weight(item_id: int, data: WeightEntryIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = owned(WeightEntry, item_id, user, db)
    for key, value in data.model_dump().items(): setattr(item, key, value)
    db.commit(); db.refresh(item); return item
@app.delete("/health/weights/{item_id}", status_code=204)
def delete_weight(item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)): db.delete(owned(WeightEntry, item_id, user, db)); db.commit()
@app.get("/health/goals", response_model=list[WeightGoalOut])
def list_goals(user: User = Depends(current_user), db: Session = Depends(get_db)): return db.query(WeightGoal).filter_by(user_id=user.id).order_by(WeightGoal.start_date.desc()).all()
@app.post("/health/goals", response_model=WeightGoalOut, status_code=201)
def add_goal(data: WeightGoalIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if data.active: db.query(WeightGoal).filter_by(user_id=user.id, active=True).update({"active": False})
    item = WeightGoal(user_id=user.id, **data.model_dump()); db.add(item); db.commit(); db.refresh(item); return item
@app.put("/health/goals/{item_id}", response_model=WeightGoalOut)
def edit_goal(item_id: int, data: WeightGoalIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = owned(WeightGoal, item_id, user, db)
    if data.active: db.query(WeightGoal).filter(WeightGoal.user_id == user.id, WeightGoal.id != item.id).update({"active": False})
    for key, value in data.model_dump().items(): setattr(item, key, value)
    db.commit(); db.refresh(item); return item
@app.delete("/health/goals/{item_id}", status_code=204)
def delete_goal(item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)): db.delete(owned(WeightGoal, item_id, user, db)); db.commit()
@app.get("/health/summary")
def health_summary(user: User = Depends(current_user), db: Session = Depends(get_db)): return health_data(user, db)

@app.get("/finance/categories", response_model=list[CategoryOut])
def list_categories(user: User = Depends(current_user), db: Session = Depends(get_db)): return db.query(Category).filter_by(household_id=user.household_id).order_by(Category.name).all()
@app.post("/finance/categories", response_model=CategoryOut, status_code=201)
def add_category(data: CategoryIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = Category(household_id=user.household_id, **data.model_dump()); db.add(item); db.commit(); db.refresh(item); return item
@app.put("/finance/categories/{item_id}", response_model=CategoryOut)
def edit_category(item_id: int, data: CategoryIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = household_item(Category, item_id, user, db)
    for key, value in data.model_dump().items(): setattr(item, key, value)
    db.commit(); db.refresh(item); return item
@app.delete("/finance/categories/{item_id}", status_code=204)
def delete_category(item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)): db.delete(household_item(Category, item_id, user, db)); db.commit()

@app.get("/finance/transactions", response_model=list[TransactionOut])
def list_transactions(start: date | None = None, end: date | None = None, kind: TransactionType | None = None, category_id: int | None = None, limit: int | None = Query(None, ge=1, le=100), user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = db.query(Transaction).filter(visible_transactions(user))
    if start: query = query.filter(Transaction.date >= start)
    if end: query = query.filter(Transaction.date <= end)
    if kind: query = query.filter(Transaction.kind == kind)
    if category_id: query = query.filter(Transaction.category_id == category_id)
    query = query.order_by(Transaction.date.desc(), Transaction.id.desc())
    return query.limit(limit).all() if limit else query.all()
@app.post("/finance/transactions", response_model=TransactionOut, status_code=201)
def add_transaction(data: TransactionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if data.category_id: household_item(Category, data.category_id, user, db)
    item = Transaction(user_id=user.id, household_id=user.household_id, **data.model_dump()); db.add(item); db.commit(); db.refresh(item); return item
@app.put("/finance/transactions/{item_id}", response_model=TransactionOut)
def edit_transaction(item_id: int, data: TransactionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if data.category_id: household_item(Category, data.category_id, user, db)
    item = owned(Transaction, item_id, user, db)
    for key, value in data.model_dump().items(): setattr(item, key, value)
    db.commit(); db.refresh(item); return item
@app.delete("/finance/transactions/{item_id}", status_code=204)
def delete_transaction(item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)): db.delete(owned(Transaction, item_id, user, db)); db.commit()

def summary_for_range(start, end, user, db):
    rows = db.query(Transaction.kind, func.sum(Transaction.amount)).filter(visible_transactions(user), Transaction.date.between(start, end)).group_by(Transaction.kind).all(); totals = {kind.value: float(amount) for kind, amount in rows}; income, expense = totals.get("income", 0), totals.get("expense", 0); return {"income": income, "expense": expense, "balance": income - expense}
@app.get("/finance/summary/monthly")
def monthly_summary(year: int = Query(...), month: int = Query(..., ge=1, le=12), user: User = Depends(current_user), db: Session = Depends(get_db)): return summary_for_range(*period(year, month), user, db)
@app.get("/finance/summary/monthly-series")
def monthly_series(year: int | None = None, month: int | None = Query(None, ge=1, le=12), months: int = Query(6, ge=1, le=24), user: User = Depends(current_user), db: Session = Depends(get_db)):
    cursor = date(year or date.today().year, month or date.today().month, 1); result = []
    for _ in range(months):
        result.append({"year": cursor.year, "month": cursor.month, "label": f"{cursor.month:02d}/{cursor.year}", **summary_for_range(*period(cursor.year, cursor.month), user, db)})
        cursor = date(cursor.year - 1, 12, 1) if cursor.month == 1 else date(cursor.year, cursor.month - 1, 1)
    return list(reversed(result))
@app.get("/finance/summary/categories")
def category_summary(start: date, end: date, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Category.id, Category.name, Transaction.kind, func.sum(Transaction.amount)).outerjoin(Category, Transaction.category_id == Category.id).filter(visible_transactions(user), Transaction.date.between(start, end)).group_by(Category.id, Category.name, Transaction.kind).all()
    return [{"category_id": category_id, "category": name or "Sin categoría", "kind": kind.value, "amount": float(amount)} for category_id, name, kind, amount in rows]

@app.get("/finance/budgets", response_model=list[CategoryBudgetOut])
def list_budgets(year: int, month: int = Query(..., ge=1, le=12), user: User = Depends(current_user), db: Session = Depends(get_db)): return db.query(CategoryBudget).filter_by(household_id=user.household_id, year=year, month=month).all()
@app.put("/finance/budgets", response_model=CategoryBudgetOut)
def put_budget(data: CategoryBudgetIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    household_item(Category, data.category_id, user, db); item = db.query(CategoryBudget).filter_by(household_id=user.household_id, category_id=data.category_id, year=data.year, month=data.month).first()
    if item: item.amount = data.amount
    else: item = CategoryBudget(household_id=user.household_id, **data.model_dump()); db.add(item)
    db.commit(); db.refresh(item); return item
@app.delete("/finance/budgets/{item_id}", status_code=204)
def delete_budget(item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)): db.delete(household_item(CategoryBudget, item_id, user, db)); db.commit()
@app.get("/finance/budgets/progress")
def budget_progress(year: int, month: int = Query(..., ge=1, le=12), user: User = Depends(current_user), db: Session = Depends(get_db)):
    start, end = period(year, month); budgets = db.query(CategoryBudget).filter_by(household_id=user.household_id, year=year, month=month).all(); spent = dict(db.query(Transaction.category_id, func.sum(Transaction.amount)).filter(visible_transactions(user), Transaction.kind == TransactionType.expense, Transaction.date.between(start, end)).group_by(Transaction.category_id).all())
    categories = {category.id: category.name for category in db.query(Category).filter_by(household_id=user.household_id)}
    return [{"id": budget.id, "category_id": budget.category_id, "category": categories.get(budget.category_id, "Sin categoría"), "amount": float(budget.amount), "spent": float(spent.get(budget.category_id, 0)), "progress_pct": round(float(spent.get(budget.category_id, 0)) / float(budget.amount) * 100, 1)} for budget in budgets]
