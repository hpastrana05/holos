"""Small provider boundary: the application never depends on Gemini in routes."""

from dataclasses import dataclass
import json
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


@dataclass(frozen=True)
class Attachment:
    data: bytes
    mime_type: str


class LLMUnavailable(Exception):
    pass


class LLMUnsupportedMedia(LLMUnavailable):
    pass


class LLMQuotaExceeded(LLMUnavailable):
    pass


class LLMProvider(Protocol):
    def complete(self, *, system: str, messages: list[dict], tools: list[dict], attachments: list[Attachment] | None = None) -> LLMResponse: ...
    def analyze_meal(self, *, text: str | None, image: bytes | None, mime_type: str | None) -> list[dict]: ...


class GeminiProvider:
    """Gemini implementation, loaded only when chat is actually used."""

    def __init__(self, api_key: str | None = None, model: str | None = None, fallback_models: str | None = None):
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model = model if model is not None else settings.gemini_model
        fallbacks = settings.gemini_fallback_models if fallback_models is None else fallback_models
        self.models = list(dict.fromkeys(name.strip() for name in [self.model or "", *fallbacks.split(",")] if name.strip()))

    def _generate(self, client, *, contents, config, media_kind=None):
        last_error = None
        all_quota = True
        for model in self.models:
            for attempt in range(3):
                try:
                    return client.models.generate_content(model=model, contents=contents, config=config)
                except Exception as error:
                    last_error = error
                    code = getattr(error, "status_code", None) or getattr(error, "code", None)
                    if media_kind and code in (400, 415, 422):
                        raise LLMUnsupportedMedia(f"El modelo Gemini configurado no admite {media_kind}.") from error
                    if code == 429:
                        if attempt == 0:
                            sleep(1)
                            continue
                        break
                    all_quota = False
                    if code is not None and code not in (408, 500, 502, 503, 504):
                        raise LLMUnavailable("Gemini no ha podido procesar la solicitud. Comprueba la configuración.") from error
                    if attempt < 2:
                        sleep(attempt + 1)
        if all_quota:
            raise LLMQuotaExceeded("Se ha alcanzado temporalmente la cuota de los modelos Gemini configurados.") from last_error
        raise LLMUnavailable("Los modelos Gemini configurados no están disponibles ahora. Inténtalo de nuevo más tarde.") from last_error

    def complete(self, *, system: str, messages: list[dict], tools: list[dict], attachments: list[Attachment] | None = None) -> LLMResponse:
        if not self.api_key or not self.model:
            raise LLMUnavailable("Configura GEMINI_API_KEY y GEMINI_MODEL para usar el chat.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as error:
            raise LLMUnavailable("El proveedor Gemini no está instalado en el servidor.") from error
        contents = [{"role": "model" if item["role"] == "assistant" else item["role"], "parts": [{"text": item["content"]}]} for item in messages]
        for attachment in attachments or []:
            contents[-1]["parts"].append({"inline_data": {"data": attachment.data, "mime_type": attachment.mime_type}})
        client = genai.Client(api_key=self.api_key)
        kind = None if not attachments else ("esta nota de voz" if attachments[0].mime_type.startswith("audio/") else "estas fotos")
        response = self._generate(client, contents=contents,
                                  config=types.GenerateContentConfig(system_instruction=system, tools=tools),
                                  media_kind=kind)
        calls = [ToolCall(call.name, dict(call.args or {})) for call in (response.function_calls or [])]
        return LLMResponse(response.text or "", calls)

    def analyze_meal(self, *, text: str | None, image: bytes | None, mime_type: str | None) -> list[dict]:
        if not self.api_key or not self.model:
            raise LLMUnavailable("Configura GEMINI_API_KEY y GEMINI_MODEL para analizar comidas.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as error:
            raise LLMUnavailable("El proveedor Gemini no está instalado en el servidor.") from error
        prompt = """Estima una comida de forma orientativa. Devuelve exclusivamente JSON con {\"meals\":[{\"name\":str,\"description\":str,\"kcal\":number,\"protein_g\":number,\"carbs_g\":number,\"fat_g\":number,\"confidence\":number}]} . No inventes certezas: usa confidence entre 0 y 1. Si no reconoces la comida devuelve meals vacío."""
        parts = [types.Part.from_text(text=prompt + (f" Texto del usuario: {text}" if text else ""))]
        if image: parts.append(types.Part.from_bytes(data=image, mime_type=mime_type or "image/jpeg"))
        client = genai.Client(api_key=self.api_key)
        response = self._generate(client, contents=[{"role": "user", "parts": parts}],
                                  config=types.GenerateContentConfig(response_mime_type="application/json"),
                                  media_kind="esta foto" if image else None)
        try:
            data = json.loads(response.text or "{}")
            meals = data.get("meals", [])
            if not isinstance(meals, list):
                raise ValueError("Respuesta de análisis no válida")
            return meals
        except (ValueError, AttributeError, TypeError) as error:
            raise LLMUnavailable("No he podido analizar la comida ahora. Inténtalo más tarde.") from error

