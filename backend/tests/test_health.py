from datetime import date
from app.services.health import estimate_arrival, target_kcal
from .conftest import token


def test_kcal_has_safe_floor_and_goal_adjustment():
    maintenance = target_kcal(170, date(1990, 1, 1), "female", "moderate", 70, None)
    losing = target_kcal(170, date(1990, 1, 1), "female", "moderate", 70, 60)
    assert losing < maintenance
    assert losing >= 1200
    assert estimate_arrival(80, 70, 0.5, date(2026, 1, 1)) == date(2026, 5, 21)


def test_health_data_is_private(client):
    admin = token(client)
    member = token(client, "member@test.local")
    created = client.post("/health/weights", headers=admin, json={"date": "2026-01-01", "weight_kg": 80, "source": "manual"})
    assert created.status_code == 201
    assert client.get("/health/weights", headers=member).json() == []
    assert client.put(f"/health/weights/{created.json()['id']}", headers=member, json={"date":"2026-01-01","weight_kg":70,"source":"manual"}).status_code == 404


def test_health_summary(client):
    headers = token(client)
    client.put("/health/profile", headers=headers, json={"height_cm": 170, "birth_date": "1990-01-01", "sex": "female", "activity_level": "moderate"})
    client.post("/health/weights", headers=headers, json={"date":"2026-01-01","weight_kg":80,"source":"manual"})
    client.post("/health/weights", headers=headers, json={"date":"2026-01-08","weight_kg":79,"source":"manual"})
    client.post("/health/goals", headers=headers, json={"start_weight_kg":80,"target_weight_kg":70,"start_date":"2026-01-01","weekly_rate_kg":0.5,"mode":"lose","active":True})
    summary=client.get("/health/summary",headers=headers).json()
    assert summary["current_weight_kg"] == 79
    assert summary["trend_kg"] == -1
    assert summary["target_kcal"] >= 1200
