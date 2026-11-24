from datetime import UTC, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import current_user
from app.db.session import get_db
from app.models.models import CalendarCredential, User
from app.schemas import CalendarEventIn, CalendarSelectionIn, CalendarStatusOut
from app.services.calendar import CalendarDisconnected, CalendarUnavailable, cached_events, calendars as google_calendars, clear_events, disconnect, exchange_code, encrypt_refresh, oauth_url, request
from urllib.parse import quote

router = APIRouter(prefix="/calendar", tags=["calendar"])
Db = Annotated[Session, Depends(get_db)]
Account = Annotated[User, Depends(current_user)]
MADRID = ZoneInfo("Europe/Madrid")

def credential(user: User, db: Session) -> CalendarCredential | None:
    return db.query(CalendarCredential).filter_by(user_id=user.id).first()

def connected(user: User, db: Session) -> CalendarCredential:
    item = credential(user, db)
    if not item or not item.connected: raise HTTPException(409, "Google Calendar no está conectado.")
    return item

def translate(error: Exception):
    status = 409 if isinstance(error, CalendarDisconnected) else 503
    raise HTTPException(status, str(error)) from error

@router.get("/status", response_model=CalendarStatusOut)
def status(user: Account, db: Db):
    item = credential(user, db)
    return {"connected": bool(item and item.connected)}

@router.get("/connect")
def connect(user: Account):
    state = jwt.encode({"sub": str(user.id), "exp": datetime.now(UTC) + timedelta(minutes=10), "scope": "calendar_oauth"}, settings.secret_key, algorithm="HS256")
    try: return {"authorization_url": oauth_url(user.id, state)}
    except CalendarUnavailable as error: translate(error)

@router.get("/callback", include_in_schema=False)
def callback(code: str | None = None, state: str | None = None, error: str | None = None, db: Db = None):
    if error or not code or not state: return RedirectResponse("/?calendar=error")
    try:
        payload = jwt.decode(state, settings.secret_key, algorithms=["HS256"], options={"require": ["sub", "scope", "exp"]})
        if payload["scope"] != "calendar_oauth": raise jwt.InvalidTokenError()
        user = db.get(User, int(payload["sub"]))
        if not user: raise jwt.InvalidTokenError()
        data = exchange_code(code)
        refresh = data.get("refresh_token")
        if not refresh: raise CalendarUnavailable("Google no entregó un token de acceso sin conexión.")
        item = credential(user, db) or CalendarCredential(user_id=user.id)
        item.refresh_token_encrypted = encrypt_refresh(refresh); item.connected = True
        db.add(item); db.commit(); clear_events(user.id)
    except (jwt.InvalidTokenError, ValueError, CalendarUnavailable):
        return RedirectResponse("/?calendar=error")
    return RedirectResponse("/?calendar=connected")

@router.delete("/connection", status_code=204)
def remove_connection(user: Account, db: Db):
    item = credential(user, db)
    if item: disconnect(db, item)

@router.get("/calendars")
def calendars(user: Account, db: Db):
    try:
        return google_calendars(db, connected(user, db))
    except (CalendarDisconnected, CalendarUnavailable) as error: translate(error)

@router.put("/calendars")
def select_calendars(data: CalendarSelectionIn, user: Account, db: Db):
    item = connected(user, db)
    try:
        available = {calendar["id"] for calendar in google_calendars(db, item)}
    except (CalendarDisconnected, CalendarUnavailable) as error: translate(error)
    if not set(data.calendar_ids).issubset(available): raise HTTPException(422, "Hay calendarios no disponibles.")
    import json
    item.selected_calendar_ids = json.dumps(data.calendar_ids)
    db.commit(); clear_events(user.id)
    return google_calendars(db, item)

def range_events(user: User, db: Session, start: datetime, end: datetime, key: str):
    try:
        item = connected(user, db)
        return cached_events(db, item, start, end, key, google_calendars(db, item))
    except (CalendarDisconnected, CalendarUnavailable) as error: translate(error)

def screen_events(user: User, db: Session):
    item = credential(user, db)
    if not item or not item.connected: return {"connected": False, "events": []}
    try:
        now = datetime.now(MADRID)
        return {"connected": True, "events": cached_events(db, item, now, now + timedelta(days=7), "screen", google_calendars(db, item))[:3]}
    except (CalendarDisconnected, CalendarUnavailable) as error:
        return {"connected": False, "events": [], "error": str(error)}

@router.get("/events/today")
def today_events(user: Account, db: Db):
    now = datetime.now(MADRID); start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return range_events(user, db, start, start + timedelta(days=1), "today")

@router.get("/events/upcoming")
def upcoming_events(days: int = Query(7, ge=1, le=31), user: Account = None, db: Db = None):
    start = datetime.now(MADRID); return range_events(user, db, start, start + timedelta(days=days), f"upcoming-{days}")

@router.get("/events/month")
def month_events(year: int | None = None, month: int | None = Query(None, ge=1, le=12), user: Account = None, db: Db = None):
    now = datetime.now(MADRID); year, month = year or now.year, month or now.month
    start = datetime(year, month, 1, tzinfo=MADRID)
    end = datetime(year + 1, 1, 1, tzinfo=MADRID) if month == 12 else datetime(year, month + 1, 1, tzinfo=MADRID)
    return range_events(user, db, start, end, f"month-{year}-{month}")

@router.get("/events/range")
def events_range(start: datetime, end: datetime, user: Account, db: Db):
    if end <= start or end - start > timedelta(days=32): raise HTTPException(422, "El rango del calendario no es válido.")
    start = start.replace(tzinfo=MADRID) if start.tzinfo is None else start.astimezone(MADRID)
    end = end.replace(tzinfo=MADRID) if end.tzinfo is None else end.astimezone(MADRID)
    return range_events(user, db, start, end, f"range-{start.isoformat()}-{end.isoformat()}")

@router.post("/events", status_code=201)
def create_event(data: CalendarEventIn, user: Account, db: Db):
    if data.end <= data.start: raise HTTPException(422, "La hora de fin debe ser posterior a la de inicio.")
    start = data.start.replace(tzinfo=MADRID) if data.start.tzinfo is None else data.start.astimezone(MADRID)
    end = data.end.replace(tzinfo=MADRID) if data.end.tzinfo is None else data.end.astimezone(MADRID)
    try:
        item = connected(user, db); sources = google_calendars(db, item)
        available = {source["id"] for source in sources if source["selected"]}
        calendar_id = data.calendar_id or next((source["id"] for source in sources if source["id"] == "primary" and source["selected"]), next(iter(available), None))
        if not calendar_id or calendar_id not in available: raise HTTPException(422, "Elige un calendario activo para el evento.")
        result = request(db, item, "POST", f"/calendars/{quote(calendar_id, safe='')}/events", json={"summary": data.title, "description": data.description, "start": {"dateTime": start.isoformat(), "timeZone": "Europe/Madrid"}, "end": {"dateTime": end.isoformat(), "timeZone": "Europe/Madrid"}})
        clear_events(user.id)
        return {"id": result.get("id"), "title": result.get("summary", data.title), "start": result.get("start", {}).get("dateTime", start.isoformat()), "end": result.get("end", {}).get("dateTime", end.isoformat()), "all_day": False}
    except (CalendarDisconnected, CalendarUnavailable) as error: translate(error)
