from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from time import monotonic

import httpx
from app.settings_routes import WeatherLocation
from pydantic import BaseModel

TTL_SECONDS = 30 * 60
RETRY_SECONDS = 60
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class Hour(BaseModel):
    time: datetime
    temperature: float | None
    precipitation_probability: float | None
    uv: float | None


class Forecast(BaseModel):
    location: str
    time: datetime
    temperature: float | None
    apparent_temperature: float | None
    weather_code: int | None
    wind: float | None
    precipitation_probability: float | None
    uv: float | None
    maximum: float | None
    minimum: float | None
    sunrise: datetime | None
    sunset: datetime | None
    hourly: list[Hour]
    summary: str
    stale: bool = False


def describe(code: int | None, rain: float | None) -> str:
    if code is None:
        condition = "Estado del cielo sin datos"
    elif code == 0:
        condition = "Cielo despejado"
    elif code <= 3:
        condition = "Nubes y claros" if code < 3 else "Cielo cubierto"
    elif code in (45, 48):
        condition = "Niebla"
    elif code >= 95:
        condition = "Tormenta"
    elif code in (71, 73, 75, 77, 85, 86):
        condition = "Nieve"
    else:
        condition = "Lluvia o llovizna"
    if rain is None:
        return f"{condition}."
    return f"{condition}. Probabilidad de precipitación esta hora: {rain:.0f} %."


def fetch_forecast(client: httpx.Client, location: WeatherLocation) -> Forecast:
    response = client.get(
        FORECAST_URL,
        params={
            "latitude": location.latitude,
            "longitude": location.longitude,
            "timezone": "Europe/Madrid",
            "forecast_days": 1,
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
            "hourly": "temperature_2m,precipitation_probability,uv_index",
            "daily": "temperature_2m_max,temperature_2m_min,sunrise,sunset",
        },
    )
    response.raise_for_status()
    data = response.json()
    current, hourly, daily = data["current"], data["hourly"], data["daily"]
    time = datetime.fromisoformat(current["time"])
    forecast_hours = [
        Hour(time=slot, temperature=temp, precipitation_probability=rain, uv=uv)
        for slot, temp, rain, uv in zip(
            hourly["time"],
            hourly["temperature_2m"],
            hourly["precipitation_probability"],
            hourly["uv_index"],
            strict=True,
        )
    ]
    hour = next(
        (
            item
            for item in forecast_hours
            if item.time == time.replace(minute=0, second=0)
        ),
        None,
    )
    rain = hour.precipitation_probability if hour else None
    return Forecast(
        location=location.name,
        time=time,
        temperature=current["temperature_2m"],
        apparent_temperature=current["apparent_temperature"],
        weather_code=current["weather_code"],
        wind=current["wind_speed_10m"],
        precipitation_probability=rain,
        uv=hour.uv if hour else None,
        maximum=daily["temperature_2m_max"][0],
        minimum=daily["temperature_2m_min"][0],
        sunrise=daily["sunrise"][0],
        sunset=daily["sunset"][0],
        hourly=forecast_hours,
        summary=describe(current["weather_code"], rain),
    )


@dataclass
class CacheEntry:
    location: WeatherLocation
    until: float
    forecast: Forecast | None


class WeatherUnavailable(Exception):
    pass


class WeatherCache:
    def __init__(self, client: httpx.Client):
        self.client = client
        self.entries: dict[int, CacheEntry] = {}
        self.lock = Lock()

    def get(self, household_id: int, location: WeatherLocation) -> Forecast:
        with self.lock:
            cached = self.entries.get(household_id)
            if cached and cached.location != location:
                cached = None
            if cached and cached.until > monotonic():
                if cached.forecast is None:
                    raise WeatherUnavailable()
                return cached.forecast
            try:
                forecast = fetch_forecast(self.client, location)
            except (
                httpx.HTTPError,
                KeyError,
                TypeError,
                ValueError,
                IndexError,
            ) as error:
                fallback = (
                    cached.forecast.model_copy(update={"stale": True})
                    if cached and cached.forecast
                    else None
                )
                self.entries[household_id] = CacheEntry(
                    location, monotonic() + RETRY_SECONDS, fallback
                )
                if fallback is None:
                    raise WeatherUnavailable() from error
                return fallback
            self.entries[household_id] = CacheEntry(
                location, monotonic() + TTL_SECONDS, forecast
            )
            return forecast
