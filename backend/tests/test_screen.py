from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from app.core.config import settings

from tests.conftest import token


@pytest.fixture
def screen_headers(monkeypatch):
    monkeypatch.setattr(settings, "screen_token", "test-screen-token")
    monkeypatch.setattr(settings, "screen_user_email", "admin@test.local")
    return {"X-Screen-Token": "test-screen-token"}


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
    assert data["monthly_balance"] == -140
    assert [item["amount"] for item in data["recent_transactions"]] == [20, 120]
    assert set(data["recent_transactions"][0]) == {"id", "amount", "kind", "date"}


def test_screen_rejects_invalid_or_disabled_token(client, screen_headers, monkeypatch):
    assert client.get("/screen/summary").status_code == 401
    assert (
        client.get("/screen/summary", headers={"X-Screen-Token": "wrong"}).status_code
        == 401
    )
    monkeypatch.setattr(settings, "screen_user_email", "")
    assert client.get("/screen/summary", headers=screen_headers).status_code == 401
    monkeypatch.setattr(settings, "screen_token", "")
    assert client.get("/screen/summary", headers=screen_headers).status_code == 401


def test_screen_token_is_read_only(client, screen_headers):
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert (
            client.request(
                method, "/screen/summary", headers=screen_headers
            ).status_code
            == 405
        )

    bearer = {"Authorization": f"Bearer {screen_headers['X-Screen-Token']}"}
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
