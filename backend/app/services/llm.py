"""Small provider boundary: the application never depends on Gemini in routes."""

from dataclasses import dataclass
from time import sleep
from typing import Protocol

from app.core.config import settings


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall]


class LLMUnavailable(Exception):
    pass


class LLMQuotaExceeded(LLMUnavailable):
    pass


class LLMProvider(Protocol):
    def complete(self, *, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse: ...


class GeminiProvider:
    """Gemini implementation, loaded only when chat is actually used."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model = model if model is not None else settings.gemini_model

    def complete(self, *, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
        if not self.api_key or not self.model:
            raise LLMUnavailable("Configura GEMINI_API_KEY y GEMINI_MODEL para usar el chat.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as error:
            raise LLMUnavailable("El proveedor Gemini no está instalado en el servidor.") from error
        contents = [{"role": item["role"], "parts": [{"text": item["content"]}]} for item in messages]
        try:
            client = genai.Client(api_key=self.api_key)
            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model=self.model,
                        contents=contents,
                        config=types.GenerateContentConfig(system_instruction=system, tools=tools),
                    )
                    calls = [ToolCall(call.name, dict(call.args or {})) for call in (response.function_calls or [])]
                    return LLMResponse(response.text or "", calls)
                except Exception as error:
                    code = getattr(error, "status_code", None) or getattr(error, "code", None)
                    if code == 429:
                        if attempt == 2:
                            raise LLMQuotaExceeded("Se ha alcanzado temporalmente la cuota gratuita de Gemini.") from error
                        sleep(attempt + 1)
                    elif attempt == 2:
                        raise LLMUnavailable("Gemini no está disponible ahora. Inténtalo de nuevo en unos minutos.") from error
                    else:
                        sleep(attempt + 1)
        except LLMUnavailable:
            raise

