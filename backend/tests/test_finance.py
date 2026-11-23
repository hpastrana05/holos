from .conftest import token


def test_personal_transaction_is_isolated_but_shared_is_visible_to_household(client):
    admin = token(client)
    member = token(client, "member@test.local")
    client.post("/finance/transactions", headers=admin, json={"kind":"expense","amount":10,"date":"2026-01-10","visibility":"personal"})
    assert client.get("/finance/transactions", headers=member).json() == []
    client.post("/finance/transactions", headers=admin, json={"kind":"expense","amount":20,"date":"2026-01-10","visibility":"shared"})
    visible = client.get("/finance/transactions", headers=member).json()
    assert len(visible) == 1 and visible[0]["amount"] == 20


def test_finance_summary_and_category_filter(client):
    headers = token(client)
    cat = client.post("/finance/categories", headers=headers, json={"name":"Comida","kind":"expense"}).json()
    client.post("/finance/transactions", headers=headers, json={"kind":"income","amount":1000,"date":"2026-02-01","visibility":"personal"})
    client.post("/finance/transactions", headers=headers, json={"kind":"expense","amount":125.5,"category_id":cat["id"],"date":"2026-02-02","visibility":"personal"})
    monthly=client.get("/finance/summary/monthly?year=2026&month=2",headers=headers).json()
    assert monthly == {"income":1000.0,"expense":125.5,"balance":874.5}
    by_category=client.get("/finance/summary/categories?start=2026-02-01&end=2026-02-28",headers=headers).json()
    assert any(row["category"] == "Comida" and row["amount"] == 125.5 for row in by_category)
