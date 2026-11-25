from types import SimpleNamespace

import pytest

from app.services.llm import GeminiProvider, LLMQuotaExceeded, LLMUnavailable, LLMUnsupportedMedia


class APIError(Exception):
    def __init__(self, code):
        self.code = code


def client_for(outcomes):
    calls = []

    def generate_content(*, model, **kwargs):
        calls.append(model)
        outcome = outcomes[model]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)), calls


def test_rotates_after_quota_and_deduplicates(monkeypatch):
    monkeypatch.setattr("app.services.llm.sleep", lambda _: None)
    provider = GeminiProvider("key", "primary", "primary, light, light")
    client, calls = client_for({"primary": APIError(429), "light": "ok"})
    assert provider._generate(client, contents=[], config={}) == "ok"
    assert calls == ["primary", "primary", "light"]


def test_rotates_after_transient_failure(monkeypatch):
    monkeypatch.setattr("app.services.llm.sleep", lambda _: None)
    provider = GeminiProvider("key", "primary", "light")
    client, calls = client_for({"primary": APIError(503), "light": "ok"})
    assert provider._generate(client, contents=[], config={}) == "ok"
    assert calls == ["primary", "primary", "primary", "light"]


def test_exhaustion_and_non_retryable_errors(monkeypatch):
    monkeypatch.setattr("app.services.llm.sleep", lambda _: None)
    provider = GeminiProvider("key", "primary", "light")
    client, calls = client_for({"primary": APIError(429), "light": APIError(429)})
    with pytest.raises(LLMQuotaExceeded):
        provider._generate(client, contents=[], config={})
    assert calls == ["primary", "primary", "light", "light"]
    client, calls = client_for({"primary": APIError(400), "light": "ok"})
    with pytest.raises(LLMUnsupportedMedia):
        provider._generate(client, contents=[], config={}, media_kind="esta foto")
    assert calls == ["primary"]
    client, calls = client_for({"primary": APIError(401), "light": "ok"})
    with pytest.raises(LLMUnavailable):
        provider._generate(client, contents=[], config={})
    assert calls == ["primary"]
