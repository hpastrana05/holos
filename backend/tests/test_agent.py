from app.agent_routes import provider
from app.main import app
from types import SimpleNamespace

from app.models.models import AgentAction, Category, CategoryBudget, Transaction, TransactionType, User, WeightEntry
from app.services.llm import LLMQuotaExceeded, LLMResponse, LLMUnavailable, ToolCall
from .conftest import token


class FakeLLM:
    def __init__(self, response): self.response = response
    def complete(self, **_):
        if isinstance(self.response, Exception): raise self.response
        return self.response


def post(client, headers, response):
    app.dependency_overrides[provider] = lambda: FakeLLM(response)
    try: return client.post("/agent/chat", headers=headers, json={"message": "hazlo", "history": []})
    finally: app.dependency_overrides.pop(provider, None)


def add_category(db, household_id, name, kind):
    item = Category(household_id=household_id, name=name, kind=kind); db.add(item); db.commit()


def test_agent_creates_data_and_audits_it(client, db):
    headers = token(client); user = db.query(User).filter_by(email="admin@test.local").one()
    add_category(db, user.household_id, "Comida", TransactionType.expense)
    response = post(client, headers, LLMResponse("", [ToolCall("add_expense", {"amount": 12, "category": "Comida", "date": "2026-11-23"})]))
    assert response.status_code == 200 and "Registrado: gasto" in response.json()["response"]
    assert db.query(Transaction).one().user_id == user.id
    assert db.query(AgentAction).one().tool == "add_expense"


def test_agent_weight_and_queries(client, db):
    headers = token(client)
    for call in [ToolCall("add_weight", {"weight_kg": 75.5, "date": "2026-11-23"}), ToolCall("get_weight_status", {}), ToolCall("get_finance_summary", {})]:
        assert post(client, headers, LLMResponse("", [call])).status_code == 200
    assert db.query(WeightEntry).count() == 1
    assert db.query(AgentAction).count() == 3


def test_income_budget_and_weather_tools(client, db, monkeypatch):
    headers = token(client); user = db.query(User).filter_by(email="admin@test.local").one()
    category = Category(household_id=user.household_id, name="Nómina", kind=TransactionType.income)
    expense = Category(household_id=user.household_id, name="Hogar", kind=TransactionType.expense)
    db.add_all([category, expense]); db.flush()
    db.add(CategoryBudget(household_id=user.household_id, category_id=expense.id, year=2026, month=11, amount=100)); db.commit()
    calls = [
        ToolCall("add_income", {"amount": 1000, "category": "Nómina", "date": "2026-11-01"}),
        ToolCall("get_budget_status", {"category": "Hogar", "year": 2026, "month": 11}),
    ]
    for call in calls: assert post(client, headers, LLMResponse("", [call])).status_code == 200
    monkeypatch.setattr("app.agent_routes.fetch_forecast", lambda *_: SimpleNamespace(location="Toledo", temperature=20, summary="Cielo despejado."))
    assert "Toledo" in post(client, headers, LLMResponse("", [ToolCall("get_today_weather", {})])).json()["response"]


def test_agent_rejects_ambiguous_or_foreign_category(client, db):
    headers = token(client); user = db.query(User).filter_by(email="admin@test.local").one(); other = db.query(User).filter_by(email="other@test.local").one()
    add_category(db, user.household_id, "Casa", TransactionType.expense); add_category(db, user.household_id, "CASA", TransactionType.expense)
    response = post(client, headers, LLMResponse("", [ToolCall("add_expense", {"amount": 4, "category": "Casa", "date": "2026-11-23"})]))
    assert "No he registrado nada" in response.json()["response"] and db.query(Transaction).count() == 0
    add_category(db, other.household_id, "Secreto", TransactionType.expense)
    response = post(client, headers, LLMResponse("", [ToolCall("add_expense", {"amount": 4, "category": "Secreto", "date": "2026-11-23"})]))
    assert "No he registrado nada" in response.json()["response"] and db.query(Transaction).count() == 0


def test_question_and_quota_do_not_break_chat(client):
    headers = token(client)
    response = post(client, headers, LLMResponse("¿Qué importe quieres registrar?", []))
    assert response.status_code == 200 and response.json()["actions"] == []
    response = post(client, headers, LLMQuotaExceeded("Se ha alcanzado temporalmente la cuota gratuita de Gemini."))
    assert response.status_code == 200 and "chat sigue disponible" in response.json()["response"]
    response = post(client, headers, LLMUnavailable("Gemini no está disponible ahora."))
    assert response.status_code == 200 and "no está disponible" in response.json()["response"]


def test_text_meal_estimates_multiple_dishes_and_waits_for_confirmation(client, db):
    from app.models.models import Meal

    class MealLLM:
        def complete(self, **kwargs):
            assert 'nunca los pidas' in kwargs['system']
            return LLMResponse('', [ToolCall('add_meal', {'name': 'Ensalada y carcamusa', 'meal_type': 'dinner'})])

        def analyze_meal(self, **kwargs):
            assert '250 g' in kwargs['text']
            return [
                {'name': 'Ensalada', 'kcal': 300, 'protein_g': 25, 'carbs_g': 10, 'fat_g': 15, 'confidence': .8},
                {'name': 'Carcamusa', 'kcal': 250, 'protein_g': 20, 'carbs_g': 8, 'fat_g': 12, 'confidence': .6},
            ]

    headers = token(client)
    app.dependency_overrides[provider] = lambda: MealLLM()
    try:
        response = client.post('/agent/chat', headers=headers, json={'message': 'Para cenar ensalada 250 g y carcamusa 200 g', 'history': []})
    finally:
        app.dependency_overrides.pop(provider, None)
    text = response.json()['response']
    assert '550 kcal' in text and 'Ensalada: 300' in text and 'Carcamusa: 250' in text
    assert 'Confianza: media' in text and 'Origen: texto' in text and '¿Confirmas' in text
    assert db.query(Meal).count() == 0


def test_vague_meal_is_clarified_without_saving(client, db):
    from app.models.models import Meal
    headers = token(client)
    response = post(client, headers, LLMResponse('¿Qué alimentos has comido?', []))
    assert 'alimentos' in response.json()['response']
    assert db.query(Meal).count() == 0
