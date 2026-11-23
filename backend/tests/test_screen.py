from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from app.core.config import settings

from tests.conftest import token


@pytest.fixture(autouse=True)
def screen_household(monkeypatch):
    from app.screen_access import pin_attempts

    monkeypatch.setattr(settings, "household_name", "Hogar de prueba")
    pin_attempts.clear()


@pytest.fixture
def screen_headers(client):
    user = client.get("/screen/users").json()[0]
    response = client.post("/screen/session", json={"user_id": user["id"]})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_screen_scope(client, screen_headers):
    today = datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()
    for email, weight, amount, visibility in [
        ("admin@test.local", 71, 120, "personal"),
        ("member@test.local", 89, 900, "personal"),
        ("member@test.local", 89, 20, "shared"),
        ("other@test.local", 94, 500, "shared"),
    ]:
        auth = token(client, email)
        weight_response = client.post(
            "/health/weights",
            headers=auth,
            json={
                "date": today,
                "weight_kg": weight,
            },
        )
        assert weight_response.status_code == 201
        response = client.post(
            "/finance/transactions",
            headers=auth,
            json={
                "date": today,
                "kind": "expense",
                "amount": amount,
                "visibility": visibility,
                "note": "Nota privada",
            },
        )
        assert response.status_code == 201

    profile = client.put(
        "/health/profile",
        headers=token(client),
        json={
            "height_cm": 178,
            "birth_date": "1990-01-01",
            "sex": "male",
            "activity_level": "sedentary",
        },
    )
    assert profile.status_code == 200
    response = client.get("/screen/summary", headers=screen_headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["current_weight_kg"] == 71
    assert (
        data["target_kcal"]
        == client.get("/health/summary", headers=token(client)).json()["target_kcal"]
    )
    assert data["target_kcal"] > 0
    assert data["monthly_balance"] == -120
    assert [item["amount"] for item in data["recent_transactions"]] == [120]
    assert set(data["recent_transactions"][0]) == {"id", "amount", "kind", "date"}


def test_selector_and_pin(client):
    admin = token(client)
    users = client.get("/screen/users").json()
    assert [user["name"] for user in users] == ["Usuario 1", "Usuario 2"]
    assert set(users[0]) == {"id", "name", "color", "avatar"}
    assert client.get("/screen/summary").status_code in (401, 403)
    assert client.get("/screen/weather").status_code in (401, 403)
    assert client.get("/screen/summary", headers=admin).status_code == 401

    user_id = users[1]["id"]
    session = client.post("/screen/session", json={"user_id": user_id}).json()
    old_headers = {"Authorization": f"Bearer {session['access_token']}"}
    edit = {
        "name": "Miembro",
        "email": "member@test.local",
        "is_active": True,
        "pin": "0123",
    }
    assert (
        client.put(f"/settings/users/{user_id}", headers=admin, json=edit).status_code
        == 200
    )
    assert client.get("/screen/summary", headers=old_headers).status_code == 401
    assert (
        client.post("/screen/session", json={"user_id": user_id}).json()["detail"][
            "code"
        ]
        == "pin_required"
    )
    for _ in range(5):
        assert (
            client.post(
                "/screen/session", json={"user_id": user_id, "pin": "1234"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/screen/session", json={"user_id": user_id, "pin": "0123"}
        ).status_code
        == 429
    )

    from app.screen_access import pin_attempts

    pin_attempts.pop(user_id)
    valid = client.post("/screen/session", json={"user_id": user_id, "pin": "0123"})
    assert valid.status_code == 200
    headers = {"Authorization": f"Bearer {valid.json()['access_token']}"}
    assert (
        client.get("/screen/summary", headers=headers).json()["user_name"] == "Miembro"
    )
    assert (
        client.put(
            f"/settings/users/{user_id}",
            headers=admin,
            json={**edit, "is_active": False},
        ).status_code
        == 200
    )
    assert client.get("/screen/summary", headers=headers).status_code == 401
    assert (
        client.post(
            "/screen/session", json={"user_id": user_id, "pin": "0123"}
        ).status_code
        == 404
    )
    assert client.get("/screen/users").json() == users[:1]


def test_screen_token_is_read_only(client, screen_headers):
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert (
            client.request(
                method, "/screen/summary", headers=screen_headers
            ).status_code
            == 405
        )

    bearer = screen_headers
    assert client.get("/settings/users", headers=bearer).status_code == 401
    assert client.get("/health/summary", headers=bearer).status_code == 401
    assert (
        client.post(
            "/health/weights",
            headers=bearer,
            json={
                "date": "2026-01-01",
                "weight_kg": 70,
            },
        ).status_code
        == 401
    )
    assert (
        client.get("/screen/summary", headers=screen_headers).json()[
            "current_weight_kg"
        ]
        is None
    )
