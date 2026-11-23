from app.models.models import User

from tests.conftest import token

NEW = {
    "name": "Alba",
    "email": "alba",
    "password": "contraseña-segura",
    "role": "member",
    "color": "#112233",
    "avatar": "moon",
    "pin": "0123",
}


def test_create_edit_and_deactivate_user(client, db):
    admin = token(client)
    response = client.post("/settings/users", headers=admin, json=NEW)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Alba" and data["has_pin"]
    assert "password_hash" not in data and "screen_pin_hash" not in data
    item = db.get(User, data["id"])
    assert item.password_hash != NEW["password"]
    assert item.screen_pin_hash != NEW["pin"]
    assert client.post("/settings/users", headers=admin, json=NEW).status_code == 409

    login = client.post(
        "/auth/login", json={"email": "alba", "password": NEW["password"]}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/settings/me", headers=headers).json() == data
    assert client.get("/health/weights", headers=headers).json() == []
    change = {
        key: value for key, value in NEW.items() if key not in ("password", "pin")
    }
    change.update(name="Alba Editada", is_active=False)
    result = client.put(f"/settings/users/{item.id}", headers=admin, json=change)
    assert result.status_code == 200
    assert result.json()["has_pin"]
    assert not result.json()["is_active"]
    assert client.get("/health/weights", headers=headers).status_code == 401
    assert (
        client.post(
            "/auth/login", json={"email": "alba", "password": NEW["password"]}
        ).status_code
        == 401
    )


def test_admin_access_is_scoped_to_household(client, db):
    member = token(client, "member@test.local")
    admin = token(client)
    assert client.get("/settings/users", headers=member).status_code == 403
    assert client.post("/settings/users", headers=member, json=NEW).status_code == 403
    other = db.query(User).filter_by(email="other@test.local").one()
    current = client.get("/settings/me", headers=admin).json()
    change = {**NEW, "is_active": False}
    assert (
        client.put(
            f"/settings/users/{other.id}", headers=admin, json=change
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/settings/users/{current['id']}", headers=admin, json=change
        ).status_code
        == 409
    )
    assert {
        item["email"] for item in client.get("/settings/users", headers=admin).json()
    } == {
        "admin@test.local",
        "member@test.local",
    }


def test_weather_location_belongs_to_household(client):
    admin = token(client)
    member = token(client, "member@test.local")
    other = token(client, "other@test.local")
    location = {"name": "Madrid", "latitude": 40.4, "longitude": -3.7}
    path = "/settings/weather-location"
    assert client.get(path, headers=admin).json()["name"] == "Toledo"
    assert client.put(path, headers=member, json=location).status_code == 403
    assert client.put(path, headers=admin, json=location).json() == location
    assert client.get(path, headers=member).json() == location
    assert client.get(path, headers=other).json()["name"] == "Toledo"
