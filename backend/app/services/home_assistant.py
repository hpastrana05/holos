"""Small, synchronous REST client for Home Assistant.

It deliberately retries only safe GET requests.  A failed service call is never
retried because HA may already have applied the requested state change.
"""
from __future__ import annotations

import threading
import time
from typing import Any

import httpx

from app.core.config import settings


class HomeAssistantUnavailable(Exception):
    pass


class HomeAssistantClient:
    def __init__(self, *, url: str | None = None, token: str | None = None, timeout: float | None = None):
        self.url = (url if url is not None else settings.ha_url or "").rstrip("/")
        self.token = token if token is not None else settings.ha_token
        self.timeout = timeout if timeout is not None else settings.ha_timeout_seconds

    def _headers(self):
        if not self.url or not self.token:
            raise HomeAssistantUnavailable("Home Assistant no está configurado.")
        return {"Authorization": f"Bearer {self.token}"}

    def _read(self, path: str) -> Any:
        error: Exception | None = None
        for attempt in range(3):
            try:
                response = httpx.get(f"{self.url}{path}", headers=self._headers(), timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                error = exc
                if attempt < 2:
                    time.sleep(0.15 * (attempt + 1))
        raise HomeAssistantUnavailable("No se puede conectar con Home Assistant.") from error

    def states(self) -> list[dict]:
        result = self._read("/api/states")
        return result if isinstance(result, list) else []

    def state(self, entity_id: str) -> dict:
        result = self._read(f"/api/states/{entity_id}")
        return result if isinstance(result, dict) else {}

    def call_service(self, domain: str, service: str, entity_id: str) -> None:
        try:
            response = httpx.post(f"{self.url}/api/services/{domain}/{service}", headers=self._headers(), json={"entity_id": entity_id}, timeout=self.timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HomeAssistantUnavailable("Home Assistant no pudo ejecutar la acción.") from exc


_status_cache: dict[int, tuple[float, dict]] = {}
_cache_lock = threading.Lock()


def cached_states(household_id: int, client: HomeAssistantClient, *, ttl: float = 10) -> dict[str, dict]:
    now = time.monotonic()
    with _cache_lock:
        cached = _status_cache.get(household_id)
        if cached and now - cached[0] < ttl:
            return cached[1]
    states = {item.get("entity_id"): item for item in client.states() if item.get("entity_id")}
    with _cache_lock:
        _status_cache[household_id] = (now, states)
    return states


def invalidate_cache(household_id: int) -> None:
    with _cache_lock:
        _status_cache.pop(household_id, None)
