import json
from calendar import monthrange
from datetime import date, datetime

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.session import get_db
from app.models.models import AgentAction, Category, CategoryBudget, Household, Meal, MealSource, MealType, Transaction, TransactionType, User, WeightEntry, WeightGoal
from app.services.nutrition import kcal_target, macro_targets
from app.schemas import AgentActionOut, AgentChatIn, AgentChatOut
from app.services.llm import GeminiProvider, LLMProvider, LLMQuotaExceeded, LLMUnavailable, ToolCall
from app.services.weather import WeatherUnavailable, fetch_forecast
from app.settings_routes import WeatherLocation

router = APIRouter(prefix="/agent", tags=["agent"])

TOOLS = [
    {"function_declarations": [
        {"name": "add_expense", "description": "Registra un gasto solo con importe, categoría y fecha claros.", "parameters": {"type": "object", "properties": {"amount": {"type": "number"}, "category": {"type": "string"}, "date": {"type": "string"}, "note": {"type": "string"}}, "required": ["amount", "category", "date"]}},
        {"name": "add_income", "description": "Registra un ingreso solo con importe, categoría y fecha claros.", "parameters": {"type": "object", "properties": {"amount": {"type": "number"}, "category": {"type": "string"}, "date": {"type": "string"}, "note": {"type": "string"}}, "required": ["amount", "category", "date"]}},
        {"name": "add_weight", "description": "Registra un peso solo con el peso y fecha claros.", "parameters": {"type": "object", "properties": {"weight_kg": {"type": "number"}, "date": {"type": "string"}, "notes": {"type": "string"}}, "required": ["weight_kg", "date"]}},
        {"name": "get_finance_summary", "description": "Consulta resumen financiero de un mes o rango.", "parameters": {"type": "object", "properties": {"year": {"type": "integer"}, "month": {"type": "integer"}, "start": {"type": "string"}, "end": {"type": "string"}}}},
        {"name": "get_budget_status", "description": "Consulta presupuesto de una categoría o todas.", "parameters": {"type": "object", "properties": {"category": {"type": "string"}, "year": {"type": "integer"}, "month": {"type": "integer"}}}},
        {"name": "get_weight_status", "description": "Consulta peso, objetivo y tendencia.", "parameters": {"type": "object", "properties": {}}},
        {"name": "get_today_weather", "description": "Consulta el tiempo de hoy del hogar.", "parameters": {"type": "object", "properties": {}}},
        {"name": "add_meal", "description": "Registra una comida solo después de que el usuario confirme explícitamente la estimación.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "kcal": {"type": "number"}, "protein_g": {"type": "number"}, "carbs_g": {"type": "number"}, "fat_g": {"type": "number"}, "meal_type": {"type": "string"}, "eaten_at": {"type": "string"}}, "required": ["name", "kcal", "protein_g", "carbs_g", "fat_g", "meal_type", "eaten_at"]}},
        {"name": "get_nutrition_status", "description": "Consulta las kcal y macros de hoy frente al objetivo.", "parameters": {"type": "object", "properties": {}}},
    ]}
]


class MoneyInput(BaseModel):
    amount: float = Field(gt=0, le=1_000_000)
    category: str = Field(min_length=1, max_length=100)
    date: date
    note: str | None = Field(default=None, max_length=1000)


class WeightInput(BaseModel):
    weight_kg: float = Field(gt=20, lt=500)
    date: date
    notes: str | None = Field(default=None, max_length=1000)

class MealInput(BaseModel):
    name: str = Field(min_length=1, max_length=160); kcal: float = Field(ge=0, le=10000)
    protein_g: float = Field(ge=0, le=1000); carbs_g: float = Field(ge=0, le=1000); fat_g: float = Field(ge=0, le=1000)
    meal_type: MealType; eaten_at: datetime


def provider() -> LLMProvider:
    return GeminiProvider()


def category_for(name: str, kind: TransactionType, user: User, db: Session) -> Category | None:
    matches = [item for item in db.query(Category).filter_by(household_id=user.household_id, kind=kind) if item.name.casefold() == name.strip().casefold()]
    return matches[0] if len(matches) == 1 else None


def action_log(user: User, tool: str, arguments: dict, result: str, db: Session):
    db.add(AgentAction(user_id=user.id, tool=tool, arguments=json.dumps(arguments, ensure_ascii=False), result=result))
    db.commit()


def execute(call: ToolCall, user: User, db: Session) -> str:
    if call.name in ("add_expense", "add_income"):
        data = MoneyInput.model_validate(call.arguments)
        kind = TransactionType.expense if call.name == "add_expense" else TransactionType.income
        category = category_for(data.category, kind, user, db)
        if not category:
            available = [c.name for c in db.query(Category).filter_by(household_id=user.household_id, kind=kind)]
            return f"No he registrado nada: la categoría «{data.category}» no es inequívoca. Categorías disponibles: {', '.join(available) or 'ninguna'}."
        item = Transaction(user_id=user.id, household_id=user.household_id, kind=kind, amount=data.amount, category_id=category.id, date=data.date, note=data.note)
        db.add(item); db.commit()
        label = "gasto" if kind == TransactionType.expense else "ingreso"
        return f"Registrado: {label} de {data.amount:.2f} € en {category.name}."
    if call.name == "add_weight":
        data = WeightInput.model_validate(call.arguments)
        db.add(WeightEntry(user_id=user.id, date=data.date, weight_kg=data.weight_kg, notes=data.notes)); db.commit()
        return f"Registrado: peso de {data.weight_kg:.1f} kg."
    if call.name == "get_finance_summary":
        if "month" in call.arguments:
            year, month = int(call.arguments.get("year", date.today().year)), int(call.arguments["month"])
            start, end = date(year, month, 1), date(year, month, monthrange(year, month)[1])
        else:
            start = date.fromisoformat(call.arguments.get("start", date.today().replace(day=1).isoformat()))
            end = date.fromisoformat(call.arguments.get("end", date.today().isoformat()))
        if start > end:
            raise ValueError("Rango de fechas no válido")
        rows = db.query(Transaction.kind, func.sum(Transaction.amount)).filter(Transaction.user_id == user.id, Transaction.date.between(start, end)).group_by(Transaction.kind).all()
        values = {kind.value: float(amount) for kind, amount in rows}; income, expense = values.get("income", 0), values.get("expense", 0)
        return f"Del {start:%d/%m/%Y} al {end:%d/%m/%Y}: ingresos {income:.2f} €, gastos {expense:.2f} €, balance {income - expense:.2f} €."
    if call.name == "get_budget_status":
        now = date.today(); year = int(call.arguments.get("year", now.year)); month = int(call.arguments.get("month", now.month))
        query = db.query(CategoryBudget, Category).join(Category, Category.id == CategoryBudget.category_id).filter(CategoryBudget.household_id == user.household_id, CategoryBudget.year == year, CategoryBudget.month == month)
        if call.arguments.get("category"):
            query = query.filter(func.lower(Category.name) == str(call.arguments["category"]).lower())
        items = query.all()
        if not items: return "No hay presupuestos configurados para ese periodo o categoría."
        parts = []
        for budget, category in items:
            spent = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(Transaction.user_id == user.id, Transaction.kind == TransactionType.expense, Transaction.category_id == category.id, Transaction.date.between(date(year, month, 1), date(year, month, monthrange(year, month)[1]))).scalar()
            parts.append(f"{category.name}: {float(spent):.2f} € de {float(budget.amount):.2f} €")
        return "; ".join(parts) + "."
    if call.name == "get_weight_status":
        entries = db.query(WeightEntry).filter_by(user_id=user.id).order_by(WeightEntry.date).all(); goal = db.query(WeightGoal).filter_by(user_id=user.id, active=True).first()
        if not entries: return "No hay pesos registrados todavía."
        trend = entries[-1].weight_kg - entries[0].weight_kg if len(entries) > 1 else 0
        goal_text = f" Objetivo: {goal.target_weight_kg:.1f} kg." if goal else " Sin objetivo activo."
        return f"Peso actual: {entries[-1].weight_kg:.1f} kg. Tendencia: {trend:+.1f} kg.{goal_text}"
    if call.name == "get_today_weather":
        home = db.get(Household, user.household_id)
        try:
            with httpx.Client(timeout=8) as client:
                weather = fetch_forecast(client, WeatherLocation.from_household(home))
            return f"{weather.location}: {weather.temperature:.0f} °C. {weather.summary}"
        except (WeatherUnavailable, httpx.HTTPError, KeyError, TypeError, ValueError):
            return "No puedo consultar el tiempo ahora mismo."
    if call.name == "add_meal":
        data = MealInput.model_validate(call.arguments)
        db.add(Meal(user_id=user.id, source=MealSource.text, confidence=None, **data.model_dump())); db.commit()
        return f"Registrado: {data.name}, {data.kcal:.0f} kcal."
    if call.name == "get_nutrition_status":
        today = date.today(); start = datetime.combine(today, datetime.min.time()); end = datetime.combine(today, datetime.max.time())
        rows = db.query(func.coalesce(func.sum(Meal.kcal), 0), func.coalesce(func.sum(Meal.protein_g), 0), func.coalesce(func.sum(Meal.carbs_g), 0), func.coalesce(func.sum(Meal.fat_g), 0)).filter(Meal.user_id == user.id, Meal.eaten_at.between(start, end)).one()
        target = kcal_target(user, db); macros = macro_targets(user, db, target)
        goal = f" de {target:.0f}" if target else ""
        return f"Hoy: {float(rows[0]):.0f}{goal} kcal; proteínas {float(rows[1]):.0f}/{macros['protein_g']:.0f} g, carbohidratos {float(rows[2]):.0f}/{macros['carbs_g']:.0f} g, grasas {float(rows[3]):.0f}/{macros['fat_g']:.0f} g."
    raise ValueError("Herramienta no permitida")


@router.post("/chat", response_model=AgentChatOut)
def chat(data: AgentChatIn, user: User = Depends(current_user), db: Session = Depends(get_db), llm: LLMProvider = Depends(provider)):
    categories = [f"{item.name} ({item.kind.value})" for item in db.query(Category).filter_by(household_id=user.household_id)]
    system = (f"Eres Holos, asistente doméstico. Hoy es {date.today():%d/%m/%Y}. Responde en español, breve y directo. "
              f"Categorías del hogar: {', '.join(categories) or 'ninguna'}. Antes de crear un dato exige importe/peso, fecha y categoría inequívoca; si falta algo, pregunta y no llames herramientas. "
              "Para add_meal, presenta siempre la estimación y pide una confirmación explícita antes de llamar la herramienta. Solo usa las herramientas disponibles y no inventes resultados.")
    messages = [{"role": message.role, "content": message.content} for message in data.history[-12:]] + [{"role": "user", "content": data.message}]
    try:
        reply = llm.complete(system=system, messages=messages, tools=TOOLS)
    except LLMQuotaExceeded as error:
        return AgentChatOut(response=str(error) + " El chat sigue disponible; vuelve a intentarlo más tarde.", actions=[])
    except LLMUnavailable as error:
        return AgentChatOut(response=str(error), actions=[])
    actions = []
    confirmations = []
    for call in reply.tool_calls:
        try:
            result = execute(call, user, db)
            action_log(user, call.name, call.arguments, result, db)
            actions.append(AgentActionOut(tool=call.name, result=result)); confirmations.append(result)
        except (ValidationError, ValueError, TypeError) as error:
            confirmations.append("Necesito datos válidos antes de registrarlo.")
    response = reply.text.strip() or ""
    if confirmations:
        response = (response + "\n\n" if response else "") + "\n".join(confirmations)
    return AgentChatOut(response=response or "¿En qué te ayudo?", actions=actions)
