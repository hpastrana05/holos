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


def test_category_deletion_is_scoped_and_preserves_referenced_records(client):
    headers = token(client)
    other = token(client, "other@test.local")
    response = client.post("/finance/categories", headers=headers, json={"name": "  Libros  ", "kind": "expense"})
    assert response.status_code == 201
    category = response.json()
    assert category["name"] == "Libros"
    category_path = f"/finance/categories/{category['id']}"
    assert client.get("/finance/categories", headers=other).json() == []
    assert client.delete(category_path, headers=other).status_code == 404

    response = client.put("/finance/budgets", headers=headers, json={
        "category_id": category["id"], "year": 2026, "month": 2, "amount": 40,
    })
    budget = response.json()
    assert client.delete(category_path, headers=headers).status_code == 409
    assert client.delete(f"/finance/budgets/{budget['id']}", headers=headers).status_code == 204

    response = client.post("/finance/transactions", headers=headers, json={
        "kind": "expense", "amount": 14, "category_id": category["id"], "date": "2026-02-01",
    })
    transaction = response.json()
    transaction_path = f"/finance/transactions/{transaction['id']}"
    assert client.delete(category_path, headers=headers).status_code == 409
    response = client.put(transaction_path, headers=headers, json={
        "kind": "expense", "amount": 14, "category_id": None, "date": "2026-02-01",
    })
    assert response.status_code == 200
    assert client.delete(category_path, headers=headers).status_code == 204
    assert client.get("/finance/categories", headers=headers).json() == []
    assert client.get("/finance/transactions", headers=headers).json()[0]["amount"] == 14


def test_seed_does_not_restore_deleted_categories(db, monkeypatch):
    from sqlalchemy.orm import sessionmaker

    from app import seed
    from app.models.models import Category, Household

    monkeypatch.setattr(seed, "SessionLocal", sessionmaker(bind=db.bind))
    monkeypatch.setattr(seed.settings, "household_name", "Hogar nuevo")
    seed.seed()
    household = db.query(Household).filter_by(name="Hogar nuevo").one()
    categories = db.query(Category).filter_by(household_id=household.id)
    assert categories.count() == len(seed.DEFAULT_CATEGORIES)
    db.delete(categories.filter_by(name="Ocio").one())
    db.commit()
    seed.seed()
    assert categories.filter_by(name="Ocio").first() is None
