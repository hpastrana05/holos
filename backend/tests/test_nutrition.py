from app.agent_routes import provider
from app.main import app
from app.models.models import Meal, User
from app.services.health import target_kcal
from .conftest import token


class FakeNutritionLLM:
    def __init__(self): self.image = None
    def analyze_meal(self, *, text, image, mime_type):
        self.image = image
        return [{"name": "Tostada", "description": "Pan con tomate", "kcal": 220, "protein_g": 7, "carbs_g": 35, "fat_g": 6, "confidence": .7}]


def test_analysis_does_not_store_a_meal_or_photo(client, db):
    fake = FakeNutritionLLM(); app.dependency_overrides[provider] = lambda: fake
    try:
        response = client.post("/nutrition/analyze", headers=token(client), data={"text": "tostada"})
    finally:
        app.dependency_overrides.pop(provider, None)
    assert response.status_code == 200
    assert response.json()["meals"][0]["kcal"] == 220
    assert db.query(Meal).count() == 0 and fake.image is None


def test_meals_are_private_and_summary_uses_only_current_user(client, db):
    admin, member = token(client), token(client, "member@test.local")
    item = {"eaten_at": "2026-11-23T12:00:00", "meal_type": "lunch", "name": "Ensalada", "kcal": 300, "protein_g": 10, "carbs_g": 20, "fat_g": 15, "source": "manual"}
    assert client.post("/nutrition/meals", headers=admin, json=item).status_code == 201
    assert client.get("/nutrition/meals?day=2026-11-23", headers=member).json() == []
    assert client.get("/nutrition/summary?day=2026-11-23", headers=member).json()["totals"]["kcal"] == 0


def test_safe_kcal_deficit_is_limited():
    assert target_kcal(170, __import__("datetime").date(1990, 1, 1), "female", "moderate", 70, 40) >= 1200
