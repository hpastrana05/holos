from app.models.models import HomeEntity, User
from app.services.home_assistant import HomeAssistantUnavailable, invalidate_cache
from tests.conftest import token


class FakeHA:
    states_data = [
        {"entity_id": "switch.lampara", "state": "off", "attributes": {"friendly_name": "Lámpara"}},
        {"entity_id": "sensor.enchufe_potencia", "state": "42.5", "attributes": {"friendly_name": "Enchufe", "unit_of_measurement": "W"}},
        {"entity_id": "lock.puerta", "state": "locked", "attributes": {"friendly_name": "Puerta"}},
        {"entity_id": "cover.garaje", "state": "closed", "attributes": {"device_class": "garage"}},
    ]
    calls = []
    fail = False
    def states(self):
        if self.fail: raise HomeAssistantUnavailable("No se puede conectar con Home Assistant.")
        return self.states_data
    def state(self, entity_id):
        if self.fail: raise HomeAssistantUnavailable("No se puede conectar con Home Assistant.")
        return next(item for item in self.states_data if item["entity_id"] == entity_id)
    def call_service(self, domain, service, entity_id):
        if self.fail: raise HomeAssistantUnavailable("Home Assistant no pudo ejecutar la acción.")
        self.calls.append((domain, service, entity_id))


def install_fake(monkeypatch):
    from app import home_routes
    FakeHA.calls = []; FakeHA.fail = False
    monkeypatch.setattr(home_routes, "HomeAssistantClient", FakeHA)
    invalidate_cache(1); invalidate_cache(2)


def add(client, headers, entity_id="switch.lampara"):
    return client.post("/home/entities", headers=headers, json={"entity_id": entity_id, "display_name": "Lámpara", "room": "Salón"})


def test_home_whitelist_and_energy(client, monkeypatch):
    install_fake(monkeypatch)
    admin = token(client)
    assert add(client, admin).status_code == 201
    assert add(client, admin, "sensor.enchufe_potencia").status_code == 201
    status = client.get("/home/status", headers=admin).json()
    assert status["connected"] and {item["entity_id"] for item in status["entities"]} == {"switch.lampara", "sensor.enchufe_potencia"}
    energy = client.get("/home/energy", headers=admin).json()["entities"]
    assert energy[0]["consumption"] == 42.5 and energy[0]["consumption_unit"] == "W"


def test_control_denies_other_household_and_non_whitelisted(client, db, monkeypatch):
    install_fake(monkeypatch)
    admin = token(client); other = token(client, "other@test.local")
    entity = add(client, admin).json()
    assert client.post("/home/entities/999/control", headers=admin, json={"action": "turn_on"}).status_code == 404
    assert client.post(f"/home/entities/{entity['id']}/control", headers=other, json={"action": "turn_on"}).status_code == 404
    assert client.post(f"/home/entities/{entity['id']}/control", headers=admin, json={"action": "turn_on"}).status_code == 200
    assert FakeHA.calls == [("switch", "turn_on", "switch.lampara")]


def test_admin_discovery_and_sensitive_defaults(client, monkeypatch):
    install_fake(monkeypatch)
    admin = token(client); member = token(client, "member@test.local")
    assert client.get("/home/discover", headers=member).status_code == 403
    assert len(client.get("/home/discover", headers=admin).json()) == 4
    assert add(client, admin, "lock.puerta").json()["sensitive"] is True
    assert add(client, admin, "cover.garaje").json()["sensitive"] is True


def test_ha_failure_is_reported_without_control_retry(client, monkeypatch):
    install_fake(monkeypatch)
    admin = token(client)
    entity = add(client, admin).json()
    FakeHA.fail = True
    invalidate_cache(1)
    status = client.get("/home/status", headers=admin)
    assert status.status_code == 200 and not status.json()["connected"]
    failed = client.post(f"/home/entities/{entity['id']}/control", headers=admin, json={"action": "turn_on"})
    assert failed.status_code == 503 and FakeHA.calls == []
