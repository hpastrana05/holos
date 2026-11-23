import httpx
import pytest
from app.services import weather
from app.settings_routes import WeatherLocation

PAYLOAD = {
    "current": {
        "time": "2026-11-23T09:15",
        "temperature_2m": 11,
        "apparent_temperature": 9,
        "weather_code": 3,
        "wind_speed_10m": 14,
    },
    "hourly": {
        "time": ["2026-11-23T09:00", "2026-11-23T10:00"],
        "temperature_2m": [11, 13],
        "precipitation_probability": [25, 30],
        "uv_index": [0.3, 0.4],
    },
    "daily": {
        "temperature_2m_max": [15],
        "temperature_2m_min": [5],
        "sunrise": ["2026-11-23T08:06"],
        "sunset": ["2026-11-23T17:55"],
    },
}


def test_cache_and_fallback(monkeypatch):
    now, calls = 100, 0

    def handler(request):
        nonlocal calls
        calls += 1
        assert request.url.params["timezone"] == "Europe/Madrid"
        assert request.url.params["forecast_days"] == "1"
        return httpx.Response(200, json=PAYLOAD) if calls == 1 else httpx.Response(503)

    monkeypatch.setattr(weather, "monotonic", lambda: now)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        cache = weather.WeatherCache(client)
        location = WeatherLocation(name="Toledo", latitude=39.86, longitude=-4.02)
        result = cache.get(1, location)
        assert result.temperature == 11
        assert result.apparent_temperature == 9
        assert result.precipitation_probability == 25
        assert result.uv == 0.3
        assert result.maximum == 15 and result.minimum == 5
        assert result.sunrise.hour == 8 and result.sunset.hour == 17
        assert result.hourly[1].temperature == 13
        assert (
            result.summary
            == "Cielo cubierto. Probabilidad de precipitación esta hora: 25 %."
        )
        now += 1799
        assert cache.get(1, location) == result
        assert calls == 1
        now += 1
        assert cache.get(1, location).stale
        assert cache.get(1, location).stale
        assert calls == 2
        with pytest.raises(weather.WeatherUnavailable):
            cache.get(2, location)
        with pytest.raises(weather.WeatherUnavailable):
            cache.get(1, location.model_copy(update={"longitude": -3}))


def test_screen_weather_uses_the_selected_household(client, monkeypatch):
    from app import screen_access
    from app.core.config import settings

    monkeypatch.setattr(settings, "household_name", "Hogar de prueba")
    calls = []

    def handler(request):
        calls.append(request.url.params["latitude"])
        return httpx.Response(200, json=PAYLOAD)

    with httpx.Client(transport=httpx.MockTransport(handler)) as upstream:
        monkeypatch.setattr(screen_access, "weather", weather.WeatherCache(upstream))
        profile = client.get("/screen/users").json()[0]
        session = client.post("/screen/session", json={"user_id": profile["id"]}).json()
        headers = {"Authorization": f"Bearer {session['access_token']}"}
        response = client.get("/screen/weather", headers=headers)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["location"] == "Toledo"
        assert calls == ["39.8628"]
