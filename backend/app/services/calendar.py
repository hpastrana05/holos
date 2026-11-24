"""Google Calendar REST/OAuth client; refresh tokens are never logged or cached."""
from __future__ import annotations

import base64
import hashlib
import json
import time
from datetime import datetime
from threading import Lock
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import CalendarCredential

SCOPES = "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.calendarlist.readonly"
MADRID = ZoneInfo("Europe/Madrid")
_cache: dict[tuple[int, str], tuple[float, Any]] = {}
_lock = Lock()

class CalendarUnavailable(Exception): pass
class CalendarDisconnected(Exception): pass

def cipher() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
    return Fernet(key)

def encrypt_refresh(token: str) -> str: return cipher().encrypt(token.encode()).decode()
def decrypt_refresh(token: str) -> str:
    try: return cipher().decrypt(token.encode()).decode()
    except InvalidToken as error: raise CalendarDisconnected("Las credenciales ya no son legibles; vuelve a conectar Google.") from error

def disconnect(db: Session, credential: CalendarCredential):
    credential.connected = False; credential.refresh_token_encrypted = None; credential.calendar_email = None
    db.commit()
    with _lock:
        for key in list(_cache):
            if key[0] == credential.user_id: _cache.pop(key, None)

def oauth_url(user_id: int, state: str) -> str:
    if not all((settings.google_client_id, settings.google_client_secret, settings.google_redirect_uri)):
        raise CalendarUnavailable("Google Calendar no está configurado.")
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({"client_id": settings.google_client_id, "redirect_uri": settings.google_redirect_uri, "response_type": "code", "scope": SCOPES, "access_type": "offline", "prompt": "consent", "state": state})

def exchange_code(code: str) -> dict:
    try:
        response = httpx.post("https://oauth2.googleapis.com/token", data={"code": code, "client_id": settings.google_client_id, "client_secret": settings.google_client_secret, "redirect_uri": settings.google_redirect_uri, "grant_type": "authorization_code"}, timeout=10)
        response.raise_for_status(); return response.json()
    except httpx.HTTPError as error: raise CalendarUnavailable("Google no pudo completar la conexión.") from error

def access_token(db: Session, credential: CalendarCredential) -> str:
    if not credential.connected or not credential.refresh_token_encrypted: raise CalendarDisconnected("Google Calendar no está conectado.")
    try: refresh = decrypt_refresh(credential.refresh_token_encrypted)
    except CalendarDisconnected:
        disconnect(db, credential); raise
    try:
        response = httpx.post("https://oauth2.googleapis.com/token", data={"client_id": settings.google_client_id, "client_secret": settings.google_client_secret, "refresh_token": refresh, "grant_type": "refresh_token"}, timeout=10)
        if response.status_code in {400, 401}: disconnect(db, credential); raise CalendarDisconnected("La autorización de Google ha caducado o fue revocada.")
        response.raise_for_status(); return response.json()["access_token"]
    except CalendarDisconnected: raise
    except (httpx.HTTPError, KeyError) as error: raise CalendarUnavailable("No se puede conectar con Google Calendar.") from error

def request(db: Session, credential: CalendarCredential, method: str, path: str, **kwargs) -> Any:
    try:
        response = httpx.request(method, "https://www.googleapis.com/calendar/v3" + path, headers={"Authorization": "Bearer " + access_token(db, credential)}, timeout=10, **kwargs)
        if response.status_code in {401, 403}: disconnect(db, credential); raise CalendarDisconnected("La autorización de Google ha caducado o fue revocada.")
        response.raise_for_status(); return response.json()
    except CalendarDisconnected: raise
    except httpx.HTTPError as error: raise CalendarUnavailable("Google Calendar no está disponible ahora.") from error

def calendars(db: Session, credential: CalendarCredential) -> list[dict]:
    cache_key = (credential.user_id, "calendar-list"); now = time.monotonic()
    with _lock:
        cached = _cache.get(cache_key)
        items = cached[1] if cached and now - cached[0] < 60 else None
    if items is None:
        items = request(db, credential, "GET", "/users/me/calendarList").get("items", [])
        with _lock: _cache[cache_key] = (now, items)
    selected = None if credential.selected_calendar_ids is None else set(json.loads(credential.selected_calendar_ids))
    return [{"id": item["id"], "name": item.get("summaryOverride") or item.get("summary") or "Sin nombre", "color": item.get("backgroundColor") or "#5f7cff", "selected": selected is None or item["id"] in selected} for item in items if item.get("id")]

def cached_events(db: Session, credential: CalendarCredential, start: datetime, end: datetime, key: str, calendar_items: list[dict] | None = None) -> list[dict]:
    calendar_items = calendar_items if calendar_items is not None else calendars(db, credential)
    selected = [item for item in calendar_items if item["selected"]]
    cache_key = (credential.user_id, f"{key}:{','.join(sorted(item['id'] for item in selected))}"); now = time.monotonic()
    with _lock:
        item = _cache.get(cache_key)
        if item and now - item[0] < 30: return item[1]
    rows = []
    for calendar in selected:
        payload = request(db, credential, "GET", f"/calendars/{httpx.URL(calendar['id']).raw_path.decode()}/events", params={"timeMin": start.astimezone(MADRID).isoformat(), "timeMax": end.astimezone(MADRID).isoformat(), "singleEvents": "true", "orderBy": "startTime", "timeZone": "Europe/Madrid"})
        rows.extend({"id": f"{calendar['id']}:{event.get('id')}", "calendar_id": calendar["id"], "calendar_name": calendar["name"], "color": calendar["color"], "title": event.get("summary") or "Sin título", "start": event.get("start", {}).get("dateTime") or event.get("start", {}).get("date"), "end": event.get("end", {}).get("dateTime") or event.get("end", {}).get("date"), "all_day": "date" in event.get("start", {})} for event in payload.get("items", []))
    rows.sort(key=lambda event: event["start"])
    with _lock: _cache[cache_key] = (now, rows)
    return rows

def clear_events(user_id: int):
    with _lock:
        for key in list(_cache):
            if key[0] == user_id: _cache.pop(key, None)
