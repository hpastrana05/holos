from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.session import get_db
from app.models.models import HomeEntity, Role, User
from app.schemas import HomeControlIn, HomeEntityEdit, HomeEntityIn, HomeEntityOut, HomeStatusOut
from app.services.home_assistant import HomeAssistantClient, HomeAssistantUnavailable, cached_states, invalidate_cache

router = APIRouter(prefix="/home", tags=["home"])
Db = Annotated[Session, Depends(get_db)]
Account = Annotated[User, Depends(current_user)]
CONTROLLABLE_DOMAINS = {"light", "switch", "fan", "input_boolean", "cover", "lock", "alarm_control_panel"}


def require_admin(user: Account) -> User:
    if user.role != Role.admin:
        raise HTTPException(403, "Solo los administradores del hogar pueden cambiar Casa")
    return user


Admin = Annotated[User, Depends(require_admin)]


def default_sensitive(entity_id: str, attributes: dict | None = None) -> bool:
    domain, _, _ = entity_id.partition(".")
    return domain in {"lock", "alarm_control_panel"} or (domain == "cover" and str((attributes or {}).get("device_class", "")).lower() == "garage")


def serialize(item: HomeEntity, state: dict | None = None) -> dict:
    state = state or {}
    attributes = state.get("attributes") or {}
    raw = state.get("state")
    unit = attributes.get("unit_of_measurement")
    consumption = None
    if item.domain == "sensor" and unit in {"W", "kW", "Wh", "kWh"}:
        try: consumption = float(raw)
        except (TypeError, ValueError): pass
    return {"id": item.id, "household_id": item.household_id, "entity_id": item.entity_id, "display_name": item.display_name, "room": item.room, "domain": item.domain, "sensitive": item.sensitive, "state": raw, "attributes": attributes, "available": bool(state) and raw not in {"unavailable", "unknown"}, "consumption": consumption, "consumption_unit": unit if consumption is not None else None}


def allowed(item_id: int, user: User, db: Session) -> HomeEntity:
    item = db.query(HomeEntity).filter_by(id=item_id, household_id=user.household_id).first()
    if not item: raise HTTPException(404, "Entidad no permitida")
    return item


@router.get("/status", response_model=HomeStatusOut)
def status(user: Account, db: Db):
    items = db.query(HomeEntity).filter_by(household_id=user.household_id).order_by(HomeEntity.room, HomeEntity.display_name).all()
    try:
        states = cached_states(user.household_id, HomeAssistantClient())
    except HomeAssistantUnavailable as error:
        return {"connected": False, "entities": [serialize(item) for item in items], "error": str(error)}
    return {"connected": True, "entities": [serialize(item, states.get(item.entity_id)) for item in items]}


@router.get("/entities", response_model=list[HomeEntityOut])
def entities(user: Account, db: Db):
    return status(user, db)["entities"]


@router.get("/discover")
def discover(user: Admin):
    try:
        return HomeAssistantClient().states()
    except HomeAssistantUnavailable as error:
        raise HTTPException(503, str(error)) from error


@router.post("/entities", response_model=HomeEntityOut, status_code=201)
def add_entity(data: HomeEntityIn, user: Admin, db: Db):
    domain = data.entity_id.split(".", 1)[0]
    try:
        state = HomeAssistantClient().state(data.entity_id)
    except HomeAssistantUnavailable as error:
        raise HTTPException(503, str(error)) from error
    item = HomeEntity(household_id=user.household_id, entity_id=data.entity_id, display_name=data.display_name, room=data.room, domain=domain, sensitive=default_sensitive(data.entity_id, state.get("attributes")) if data.sensitive is None else data.sensitive)
    db.add(item)
    try: db.commit()
    except IntegrityError as error:
        db.rollback(); raise HTTPException(409, "La entidad ya está permitida en este hogar") from error
    return serialize(item, state)


@router.put("/entities/{item_id}", response_model=HomeEntityOut)
def edit_entity(item_id: int, data: HomeEntityEdit, user: Admin, db: Db):
    item = allowed(item_id, user, db)
    item.display_name, item.room, item.sensitive = data.display_name, data.room, data.sensitive
    db.commit()
    return serialize(item)


@router.delete("/entities/{item_id}", status_code=204)
def delete_entity(item_id: int, user: Admin, db: Db):
    db.delete(allowed(item_id, user, db)); db.commit()


@router.post("/entities/{item_id}/control", response_model=HomeEntityOut)
def control(item_id: int, data: HomeControlIn, user: Account, db: Db):
    item = allowed(item_id, user, db)
    if item.domain not in CONTROLLABLE_DOMAINS:
        raise HTTPException(400, "Esta entidad no admite control")
    try:
        HomeAssistantClient().call_service(item.domain, data.action, item.entity_id)
    except HomeAssistantUnavailable as error:
        raise HTTPException(503, str(error)) from error
    invalidate_cache(user.household_id)
    return serialize(item)


@router.get("/energy")
def energy(user: Account, db: Db):
    result = status(user, db)
    return {"connected": result["connected"], "error": result.get("error"), "entities": [item for item in result["entities"] if item["consumption"] is not None]}
