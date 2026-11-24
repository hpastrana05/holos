from app.models.models import CalendarCredential, User
from app.services.calendar import CalendarDisconnected
from tests.conftest import token


def connect(db, email="admin@test.local"):
    user = db.query(User).filter_by(email=email).one()
    item = CalendarCredential(user_id=user.id, refresh_token_encrypted="encrypted", connected=True)
    db.add(item); db.commit(); return item


def test_calendar_is_private_to_user(client, db, monkeypatch):
    connect(db)
    from app import calendar_routes
    seen = []
    def events(_db, credential, _start, _end, _key):
        seen.append(credential.user_id); return [{"id": "a", "title": "Privado", "start": "2026-01-01T10:00:00+01:00", "end": None, "all_day": False}]
    monkeypatch.setattr(calendar_routes, "cached_events", events)
    admin = token(client); member = token(client, "member@test.local")
    assert client.get("/calendar/status", headers=admin).json()["connected"]
    assert not client.get("/calendar/status", headers=member).json()["connected"]
    assert client.get("/calendar/events/upcoming", headers=admin).json()[0]["title"] == "Privado"
    assert client.get("/calendar/events/upcoming", headers=member).status_code == 409
    assert seen == [db.query(User).filter_by(email="admin@test.local").one().id]


def test_calendar_create_and_api_error(client, db, monkeypatch):
    connect(db)
    from app import calendar_routes
    captured = {}
    def fake_request(_db, _credential, method, path, **kwargs):
        captured.update(method=method, path=path, **kwargs); return {"id": "created", "summary": "Cena", "start": {"dateTime": "2026-01-01T20:00:00+01:00"}, "end": {"dateTime": "2026-01-01T21:00:00+01:00"}}
    monkeypatch.setattr(calendar_routes, "request", fake_request)
    result = client.post("/calendar/events", headers=token(client), json={"title": "Cena", "start": "2026-01-01T20:00:00", "end": "2026-01-01T21:00:00"})
    assert result.status_code == 201 and captured["method"] == "POST" and captured["json"]["start"]["timeZone"] == "Europe/Madrid"
    monkeypatch.setattr(calendar_routes, "cached_events", lambda *_: (_ for _ in ()).throw(CalendarDisconnected("La autorización de Google ha caducado o fue revocada.")))
    assert client.get("/calendar/events/today", headers=token(client)).status_code == 409


def test_calendar_invalid_encryption_disconnects(db):
    from app.services.calendar import access_token
    item = connect(db)
    try: access_token(db, item)
    except CalendarDisconnected: pass
    db.refresh(item)
    assert not item.connected and item.refresh_token_encrypted is None
