import json
import re
from collections.abc import Callable
from urllib.parse import quote
from calendar import monthrange
from datetime import date, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.session import get_db
from app.models.models import AgentAction, CalendarCredential, Category, CategoryBudget, HomeEntity, Household, Meal, MealSource, MealType, Transaction, TransactionType, User, WeightEntry, WeightGoal
from app.services.nutrition import kcal_target, macro_targets
from app.schemas import AgentActionOut, AgentChatIn, AgentChatOut
from app.services.llm import Attachment, GeminiProvider, LLMProvider, LLMQuotaExceeded, LLMUnavailable, ToolCall
from app.services.weather import WeatherUnavailable, fetch_forecast
from app.settings_routes import WeatherLocation
from app.home_routes import CONTROLLABLE_DOMAINS, serialize
from app.services.home_assistant import HomeAssistantClient, HomeAssistantUnavailable, cached_states, invalidate_cache
from app.services.calendar import CalendarDisconnected, CalendarUnavailable, MADRID, cached_events, calendars as google_calendars, clear_events, request

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
        {"name": "get_home_status", "description": "Consulta el estado de los dispositivos de Casa permitidos en el hogar.", "parameters": {"type": "object", "properties": {}}},
        {"name": "get_energy_usage", "description": "Consulta el consumo de los sensores de energía permitidos.", "parameters": {"type": "object", "properties": {}}},
        {"name": "control_device", "description": "Controla una entidad permitida por entity_id. Para entidades sensibles, úsala solo después de una confirmación explícita del usuario en este chat.", "parameters": {"type": "object", "properties": {"entity_id": {"type": "string"}, "action": {"type": "string", "enum": ["turn_on", "turn_off", "toggle"]}, "confirmed": {"type": "boolean"}}, "required": ["entity_id", "action"]}},
        {"name": "get_calendar_events", "description": "Consulta los próximos eventos del calendario personal del usuario.", "parameters": {"type": "object", "properties": {"days": {"type": "integer"}}}},
        {"name": "add_calendar_event", "description": "Crea un evento personal solo después de confirmación explícita del usuario.", "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}, "description": {"type": "string"}, "calendar_id": {"type": "string"}, "confirmed": {"type": "boolean"}}, "required": ["title", "start", "end"]}},
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

class HomeControlInput(BaseModel):
    entity_id: str = Field(pattern=r"^[a-z_]+\.[A-Za-z0-9_]+$")
    action: str = Field(pattern=r"^(turn_on|turn_off|toggle)$")
    confirmed: bool = False

class CalendarEventInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    start: datetime
    end: datetime
    description: str | None = Field(default=None, max_length=2000)
    calendar_id: str | None = Field(default=None, max_length=1024)
    confirmed: bool = False

def calendar_credential(user: User, db: Session) -> CalendarCredential | None:
    return db.query(CalendarCredential).filter_by(user_id=user.id, connected=True).first()


def provider() -> LLMProvider:
    return GeminiProvider()


def category_for(name: str, kind: TransactionType, user: User, db: Session) -> Category | None:
    matches = [item for item in db.query(Category).filter_by(household_id=user.household_id, kind=kind) if item.name.casefold() == name.strip().casefold()]
    return matches[0] if len(matches) == 1 else None


def action_log(user: User, tool: str, arguments: dict, result: str, db: Session):
    db.add(AgentAction(user_id=user.id, tool=tool, arguments=json.dumps(arguments, ensure_ascii=False), result=result))
    db.commit()


def execute(call: ToolCall, user: User, db: Session, *, sensitive_confirmed: bool = False) -> str:
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
    if call.name in {"get_home_status", "get_energy_usage"}:
        items = db.query(HomeEntity).filter_by(household_id=user.household_id).order_by(HomeEntity.room, HomeEntity.display_name).all()
        try:
            states = cached_states(user.household_id, HomeAssistantClient())
        except HomeAssistantUnavailable:
            return "No puedo conectar con Home Assistant ahora mismo."
        rows = [serialize(item, states.get(item.entity_id)) for item in items]
        if call.name == "get_energy_usage":
            rows = [item for item in rows if item["consumption"] is not None]
            if not rows: return "No hay sensores de consumo permitidos o disponibles."
            return "; ".join(f"{item['display_name']}: {item['consumption']:g} {item['consumption_unit']}" for item in rows) + "."
        if not rows: return "No hay dispositivos de Casa permitidos todavía."
        return "; ".join(f"{item['display_name']} ({item['room']}): {item['state'] or 'sin estado'}" for item in rows) + "."
    if call.name == "control_device":
        data = HomeControlInput.model_validate(call.arguments)
        item = db.query(HomeEntity).filter_by(household_id=user.household_id, entity_id=data.entity_id).first()
        if not item: return "No he hecho ningún cambio: esa entidad no está permitida en este hogar."
        if item.domain not in CONTROLLABLE_DOMAINS:
            return "No he hecho ningún cambio: esa entidad no admite control."
        if item.sensitive and not (data.confirmed and sensitive_confirmed):
            return f"{item.display_name} es una acción sensible. Pide confirmación explícita antes de cambiarla."
        try:
            HomeAssistantClient().call_service(item.domain, data.action, item.entity_id)
            invalidate_cache(user.household_id)
        except HomeAssistantUnavailable:
            return "Home Assistant no pudo ejecutar la acción; no la he reintentado."
        return f"Acción enviada: {data.action} en {item.display_name}."
    if call.name == "get_calendar_events":
        days = max(1, min(31, int(call.arguments.get("days", 7))))
        item = calendar_credential(user, db)
        if not item: return "Google Calendar no está conectado para este usuario."
        try:
            now = datetime.now(MADRID); rows = cached_events(db, item, now, now + timedelta(days=days), f"agent-{days}")
        except (CalendarDisconnected, CalendarUnavailable) as error: return str(error)
        if not rows: return "No tienes eventos próximos."
        return "; ".join(f"{item['title']}: {item['start']}" for item in rows) + "."
    if call.name == "add_calendar_event":
        data = CalendarEventInput.model_validate(call.arguments)
        if not (data.confirmed and sensitive_confirmed): return "Muestra primero el evento y pide una confirmación explícita antes de crearlo."
        item = calendar_credential(user, db)
        if not item: return "Google Calendar no está conectado para este usuario."
        start = data.start.replace(tzinfo=MADRID) if data.start.tzinfo is None else data.start.astimezone(MADRID)
        end = data.end.replace(tzinfo=MADRID) if data.end.tzinfo is None else data.end.astimezone(MADRID)
        if end <= start: raise ValueError("El fin debe ser posterior al inicio")
        try:
            sources = google_calendars(db, item); active = {source["id"] for source in sources if source["selected"]}
            calendar_id = data.calendar_id or next((source["id"] for source in sources if source["id"] == "primary" and source["selected"]), next(iter(active), None))
            if not calendar_id or calendar_id not in active: return "No he creado el evento: el calendario elegido no está activo."
            request(db, item, "POST", f"/calendars/{quote(calendar_id, safe='')}/events", json={"summary": data.title, "description": data.description, "start": {"dateTime": start.isoformat(), "timeZone": "Europe/Madrid"}, "end": {"dateTime": end.isoformat(), "timeZone": "Europe/Madrid"}}); clear_events(user.id)
        except (CalendarDisconnected, CalendarUnavailable) as error: return str(error)
        return f"Evento creado: {data.title}, el {start:%d/%m a las %H:%M}."
    raise ValueError("Herramienta no permitida")


@router.post("/chat", response_model=AgentChatOut)
def chat(data: AgentChatIn, user: User = Depends(current_user), db: Session = Depends(get_db), llm: LLMProvider = Depends(provider)):
    return run_chat(data, user, db, llm)


def run_tool(call: ToolCall, user: User, db: Session, *, confirmed: bool = False, private: bool = False) -> str:
    result = execute(call, user, db, sensitive_confirmed=confirmed)
    audit_result = result
    if private:
        # Tool responses can interpolate titles, names and other message content.
        audit_result = "La herramienta devolvió una respuesta."
        if call.name in {"add_expense", "add_income", "add_weight", "add_meal", "add_calendar_event", "control_device"}:
            succeeded = result.startswith(("Registrado:", "Evento creado:", "Acción enviada:"))
            audit_result = "Acción completada." if succeeded else "La herramienta no completó la acción."
    action_log(user, call.name, {} if private else call.arguments, audit_result, db)
    return result


def run_chat(
    data: AgentChatIn, user: User, db: Session, llm: LLMProvider, *,
    gate: Callable[[ToolCall], str | None] | None = None,
    attachment: Attachment | None = None,
) -> AgentChatOut:
    categories = [f"{item.name} ({item.kind.value})" for item in db.query(Category).filter_by(household_id=user.household_id)]
    home_entities = db.query(HomeEntity).filter_by(household_id=user.household_id).all()
    system = (f"Eres Holos, asistente doméstico. Hoy es {date.today():%d/%m/%Y}. Responde en español, breve y directo. "
              f"Categorías del hogar: {', '.join(categories) or 'ninguna'}. Antes de crear un dato exige importe/peso, fecha y categoría inequívoca; si falta algo, pregunta y no llames herramientas. "
              f"Entidades de Casa permitidas: {', '.join(f'{item.display_name}={item.entity_id}' for item in home_entities) or 'ninguna'}. "
              "Solo usa las herramientas disponibles y no inventes resultados.")
    if gate is None:
        system += (" Para add_meal, presenta siempre la estimación y pide una confirmación explícita antes de llamar la herramienta. "
                   "Para control_device, pide confirmación explícita antes de actuar en una entidad marcada como sensible. "
                   "Para add_calendar_event, muestra título, fecha, inicio y fin y pide confirmación explícita antes de crear.")
    else:
        system += (" En Telegram, llama a la herramienta cuando tengas todos los datos. El servidor "
                   "pedirá y comprobará la confirmación para comidas, eventos y controles sensibles. "
                   "En este canal solo la confirmación del servidor habilita la acción. "
                   "Deja el texto vacío cuando llames a una herramienta y nunca anticipes su resultado.")
    messages = [{"role": message.role, "content": message.content} for message in data.history[-12:]] + [{"role": "user", "content": data.message}]
    sensitive_confirmed = bool(re.search(r"\b(s[ií]|confirmo|confirmado|adelante|autoriza(?:do)?|procede)\b", data.message, re.IGNORECASE))
    try:
        options = {"attachment": attachment} if attachment is not None else {}
        reply = llm.complete(system=system, messages=messages, tools=TOOLS, **options)
    except LLMQuotaExceeded as error:
        return AgentChatOut(response=str(error) + " El chat sigue disponible; vuelve a intentarlo más tarde.", actions=[])
    except LLMUnavailable as error:
        return AgentChatOut(response=str(error), actions=[])
    actions = []
    confirmations = []
    calls = reply.tool_calls
    if gate is not None and calls:
        for call in calls:
            prompt = gate(call)
            if prompt is not None:
                return AgentChatOut(response=prompt, actions=[])
    for call in calls:
        try:
            result = run_tool(call, user, db, confirmed=sensitive_confirmed and gate is None,
                              private=gate is not None)
            actions.append(AgentActionOut(tool=call.name, result=result)); confirmations.append(result)
        except (ValidationError, ValueError, TypeError):
            confirmations.append("Necesito datos válidos antes de registrarlo.")
    response = "" if gate is not None and calls else reply.text.strip()
    if confirmations:
        response = (response + "\n\n" if response else "") + "\n".join(confirmations)
    return AgentChatOut(response=response or "¿En qué te ayudo?", actions=actions)
