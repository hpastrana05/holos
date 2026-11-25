"""Private Telegram chat worker. Run separately from FastAPI."""
import logging
import re
from collections import deque
from dataclasses import dataclass, field
from io import BytesIO
from time import monotonic, sleep, time

import httpx
from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError
from sqlalchemy import or_, update
from sqlalchemy.exc import SQLAlchemyError

from app.agent_routes import (
    CalendarEventInput,
    HomeControlInput,
    MealInput,
    run_chat,
    run_tool,
)
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.models import HomeEntity, User
from app.nutrition_routes import resize_photo
from app.schemas import AgentChatIn, ChatMessage
from app.services.calendar import MADRID
from app.services.llm import Attachment, GeminiProvider, LLMProvider, ToolCall
from app.services.telegram_api import MediaTooLarge, TelegramAPI, TelegramError
from app.services.telegram_link import clear_expired, redeem_code, unlink

logger = logging.getLogger(__name__)
HELP = "Envía texto, una nota de voz o una foto de comida. /resumen muestra tu resumen y /desvincular desconecta Telegram."
CONFIRM_TTL = 300
ALBUM_WAIT = 2


@dataclass
class Conversation:
    user_id: int
    expires: float
    history: list[ChatMessage] = field(default_factory=list)
    pending: tuple[str, ToolCall, float] | None = None


class TelegramBot:
    def __init__(self, api: TelegramAPI, llm: LLMProvider, sessions=SessionLocal):
        self.api = api
        self.llm = llm
        self.sessions = sessions
        self.failures = deque()
        self.conversations: dict[int, Conversation] = {}
        self.albums: dict[tuple[int, str], tuple[float, list[dict]]] = {}

    def accept(self, update_data, now=None):
        """Collect consecutive Telegram album items before making one model request."""
        now = monotonic() if now is None else now
        message = update_data.get("message", {})
        chat = message.get("chat", {})
        sender = message.get("from", {})
        chat_id = chat.get("id")
        if chat.get("type") != "private" or not chat_id or sender.get("id") != chat_id or sender.get("is_bot"):
            return
        group = message.get("media_group_id")
        if group and message.get("photo"):
            key = (chat_id, group)
            _, items = self.albums.get(key, (now, []))
            if not any(item["message_id"] == message["message_id"] for item in items):
                items.append(message)
            self.albums[key] = (now + ALBUM_WAIT, items)
        else:
            self.flush_albums(now, chat_id=chat_id)
            self.handle(update_data)

    def flush_albums(self, now=None, chat_id=None):
        now = monotonic() if now is None else now
        for key, (deadline, items) in list(self.albums.items()):
            if (chat_id is not None and key[0] == chat_id) or (chat_id is None and deadline <= now):
                del self.albums[key]
                items.sort(key=lambda item: item["message_id"])
                message = {**items[-1], "album_items": items,
                           "caption": " ".join(item.get("caption", "") for item in items).strip()}
                self.handle({"message": message})

    def prune(self, now):
        while self.failures and self.failures[0][0] <= now - 600:
            self.failures.popleft()
        for chat_id, conversation in list(self.conversations.items()):
            if conversation.expires <= now:
                del self.conversations[chat_id]

    def link(self, db, chat_id, parts, now):
        if len(self.failures) >= 60 or sum(sender == chat_id for _, sender in self.failures) >= 5:
            return None
        if (
            len(parts) == 2
            and re.fullmatch(r"[A-Za-z0-9_-]{24}", parts[1])
            and redeem_code(db, chat_id, parts[1], int(time()))
        ):
            self.conversations.pop(chat_id, None)
            return "Telegram vinculado a Holos. " + HELP
        self.failures.append((now, chat_id))
        return None

    def attachment(self, message):
        if voice := message.get("voice"):
            mime = voice.get("mime_type") or "audio/ogg"
            if mime not in {"audio/ogg", "audio/mpeg", "audio/mp3", "audio/mp4"}:
                raise HTTPException(415, "El modelo Gemini no admite el formato de esta nota de voz.")
            if mime == "audio/mp4":
                mime = "audio/m4a"
            return Attachment(self.api.download(voice), mime)
        if photos := message.get("photo"):
            photo = photos[-1]
            if photo["width"] * photo["height"] > 12_000_000:
                raise MediaTooLarge
            raw = self.api.download(photo)
            with Image.open(BytesIO(raw)) as image:
                if image.width * image.height > 12_000_000:
                    raise MediaTooLarge
            return Attachment(*resize_photo(raw, "image/jpeg"))
        return None

    def confirmation(self, call, user, db, conversation, now):
        if not db.query(User.id).filter_by(id=user.id, telegram_id=user.telegram_id, is_active=True).scalar():
            return "La vinculación de Telegram se ha desactivado."
        try:
            if call.name == "add_calendar_event":
                data = CalendarEventInput.model_validate(call.arguments)
                start = data.start.replace(tzinfo=MADRID) if data.start.tzinfo is None else data.start.astimezone(MADRID)
                end = data.end.replace(tzinfo=MADRID) if data.end.tzinfo is None else data.end.astimezone(MADRID)
                if end <= start:
                    raise ValueError
                details = (f"Crear «{data.title}» del {start:%d/%m/%Y a las %H:%M} "
                           f"al {end:%d/%m/%Y a las %H:%M} (hora de Madrid)"
                           f"\nCalendario: {data.calendar_id or 'predeterminado'}")
                if data.description:
                    details += f"\nDescripción: {data.description}"
            elif call.name == "control_device":
                data = HomeControlInput.model_validate(call.arguments)
                entity = db.query(HomeEntity).filter_by(
                    household_id=user.household_id, entity_id=data.entity_id, sensitive=True,
                ).first()
                if entity is None:
                    return None
                action = {"turn_on": "Encender", "turn_off": "Apagar", "toggle": "Cambiar el estado de"}
                details = f"{action[data.action]} {entity.display_name} ({entity.entity_id})"
            elif call.name == "add_meal":
                data = MealInput.model_validate(call.arguments)
                details = (f"Registrar «{data.name}» ({data.meal_type.value}), {data.eaten_at:%d/%m/%Y a las %H:%M}\n"
                           f"{data.kcal:g} kcal · {data.protein_g:g} g de proteína · "
                           f"{data.carbs_g:g} g de hidratos · {data.fat_g:g} g de grasa")
            else:
                return None
        except (ValidationError, ValueError, TypeError):
            if call.name == "add_meal":
                return ("No he podido preparar el registro de la comida. Indica de nuevo el nombre, "
                        "las kcal, los macronutrientes, el tipo de comida y la fecha y hora.")
            return "Necesito datos válidos antes de pedirte confirmación."
        kind = {"add_meal": "comida", "add_calendar_event": "evento", "control_device": "dispositivo"}[call.name]
        command = f"/confirmar {kind}"
        conversation.pending = (command, call, now + CONFIRM_TTL)
        return f"{details}\n\nPara confirmar, envía {command} en los próximos 5 minutos. Envía /cancelar para cancelar."

    def handle(self, update_data):
        message = update_data.get("message", {})
        chat = message.get("chat", {})
        sender = message.get("from", {})
        chat_id = chat.get("id")
        if chat.get("type") != "private" or not chat_id or sender.get("id") != chat_id or sender.get("is_bot"):
            return
        with self.sessions() as db:
            try:
                reply = self.reply(db, chat_id, message)
            except SQLAlchemyError:
                logger.warning("Telegram no pudo acceder a la base de datos.")
                return
        if reply:
            self.api.send(chat_id, reply)

    def reply(self, db, chat_id, message):
        now = monotonic()
        self.prune(now)
        raw = message.get("text", "").strip()
        parts = raw.split(maxsplit=1)
        command = parts[0].split("@")[0].lower() if parts else ""
        user = db.query(User).filter_by(telegram_id=chat_id, is_active=True).first()
        if user is None:
            return self.link(db, chat_id, parts, now) if command == "/start" else None

        # Claim each linked message once, even across worker restarts.
        message_id = message["message_id"]
        claimed = db.execute(update(User).where(
            User.id == user.id, User.is_active.is_(True), User.telegram_id == chat_id,
            or_(User.telegram_last_message.is_(None), User.telegram_last_message < message_id),
        ).values(telegram_last_message=message_id))
        db.commit()
        if not claimed.rowcount:
            return None

        if command in {"/start", "/ayuda"}:
            return HELP
        if command == "/desvincular":
            unlink(db, user.id, chat_id)
            self.conversations.pop(chat_id, None)
            return "Telegram desvinculado de Holos."
        if command == "/resumen":
            return "\n\n".join(run_tool(ToolCall(name, {}), user, db, private=True) for name in (
                "get_finance_summary", "get_weight_status", "get_nutrition_status",
            ))

        conversation = self.conversations.get(chat_id)
        if conversation is None or conversation.user_id != user.id:
            if len(self.conversations) >= 128:
                del self.conversations[next(iter(self.conversations))]
            conversation = self.conversations[chat_id] = Conversation(user.id, now + 900)
        conversation.expires = now + 900
        if command == "/confirmar":
            pending = conversation.pending
            if pending and pending[2] > now and raw.lower() == "/confirmar":
                return f"Para confirmar esta acción, envía {pending[0]}."
            if not pending or pending[2] <= now or raw != pending[0]:
                return "No hay una confirmación válida para ese código."
            conversation.pending = None
            call = pending[1]
            return run_tool(ToolCall(call.name, {**call.arguments, "confirmed": True}), user, db,
                            confirmed=True, private=True)
        if command == "/cancelar":
            conversation.pending = None
            return "Confirmación cancelada."
        if command.startswith("/"):
            return HELP
        conversation.pending = None
        try:
            attachments = [self.attachment(item) for item in message.get("album_items", [message])]
            attachments = [item for item in attachments if item is not None]
        except MediaTooLarge:
            return "El archivo supera el límite de tamaño. Envía una nota de voz o foto más pequeña."
        except TelegramError:
            return "Telegram no pudo descargar el archivo. Inténtalo de nuevo más tarde."
        except (HTTPException, Image.DecompressionBombError, UnidentifiedImageError, OSError) as error:
            return error.detail if isinstance(error, HTTPException) else "No se ha podido leer la foto."

        if attachments:
            caption = message.get("caption", "")
            prompt = ("Atiende la petición de esta nota de voz." if attachments[0].mime_type.startswith("audio/")
                      else "Estima en conjunto la comida de las fotos con kcal y macronutrientes. Si no reconoces comida, indícalo.")
            raw = f"{prompt} {caption}".strip()
        if not raw:
            return HELP
        data = AgentChatIn(message=raw[:4000], history=conversation.history)
        result = run_chat(data, user, db, self.llm, attachments=attachments,
                          gate=lambda call: self.confirmation(call, user, db, conversation, now))
        if conversation.pending is None:
            conversation.history = (conversation.history + [
                ChatMessage(role="user", content=raw[:4000]),
                ChatMessage(role="assistant", content=result.response[:4000]),
            ])[-12:]
        return result.response


def idle(message):
    logger.warning(message)
    while True:
        sleep(3600)


def main():
    logging.basicConfig(level=logging.INFO)
    token = (settings.telegram_bot_token or "").strip()
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
        idle("Bot inactivo: TELEGRAM_BOT_TOKEN ausente o inválido.")
        return
    with httpx.Client(base_url="https://api.telegram.org", timeout=40) as client:
        api = TelegramAPI(client, token)
        bot = TelegramBot(api, GeminiProvider())
        offset = None
        next_cleanup = 0
        identified = False
        while True:
            try:
                if not identified:
                    api.call("getMe")
                    identified = True
                if monotonic() >= next_cleanup:
                    bot.prune(monotonic())
                    with SessionLocal() as db:
                        clear_expired(db, int(time()))
                    next_cleanup = monotonic() + 60
                bot.flush_albums()
                updates = api.call("getUpdates", offset=offset, timeout=1 if bot.albums else 30, limit=20,
                                   allowed_updates=["message"])
                for item in updates:
                    offset = item["update_id"] + 1
                    try:
                        bot.accept(item)
                    except TelegramError as error:
                        if error.status == 401:
                            raise
                        logger.warning("Telegram no pudo enviar una respuesta.")
                        if error.retry_after:
                            sleep(min(60, error.retry_after))
            except TelegramError as error:
                if error.status in {401, 404} or (not identified and error.status == 400):
                    idle("Bot inactivo: Telegram rechazó TELEGRAM_BOT_TOKEN.")
                    return
                logger.warning("Telegram no está disponible para long polling (estado %d).", error.status)
                sleep(min(60, max(5, error.retry_after)))
            except SQLAlchemyError:
                logger.warning("Telegram no puede abrir la base de datos compartida de Holos. Comprueba DATABASE_URL.")
                sleep(30)


if __name__ == "__main__":
    main()
