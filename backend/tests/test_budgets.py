from .conftest import token


def test_budget_progress_and_transaction_filters(client):
    headers = token(client)
    category = client.post("/finance/categories", headers=headers, json={"name": "Prueba", "kind": "expense"}).json()
    budget = client.put("/finance/budgets", headers=headers, json={"category_id": category["id"], "year": 2026, "month": 3, "amount": 100}).json()
    assert budget["amount"] == 100
    client.post("/finance/transactions", headers=headers, json={"kind": "expense", "amount": 25, "category_id": category["id"], "date": "2026-03-08", "visibility": "personal"})
    progress = client.get("/finance/budgets/progress?year=2026&month=3", headers=headers).json()
    assert progress[0]["spent"] == 25 and progress[0]["progress_pct"] == 25
    filtered = client.get(f"/finance/transactions?start=2026-03-01&end=2026-03-31&category_id={category['id']}&kind=expense", headers=headers).json()
    assert len(filtered) == 1


def test_monthly_series(client):
    headers = token(client)
    client.post("/finance/transactions", headers=headers, json={"kind": "income", "amount": 500, "date": "2026-02-01", "visibility": "personal"})
    series = client.get("/finance/summary/monthly-series?year=2026&month=3&months=2", headers=headers).json()
    assert [item["label"] for item in series] == ["02/2026", "03/2026"]
    assert series[0]["income"] == 500
