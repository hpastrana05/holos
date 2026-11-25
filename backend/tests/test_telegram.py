import json
from datetime import date
from time import time

import httpx
from app.models.models import AgentAction, User, WeightEntry
from app.services.llm import (
    LLMQuotaExceeded,
    LLMResponse,
    LLMUnavailable,
    LLMUnsupportedMedia,
    ToolCall,
)
from app.services.telegram_api import TelegramAPI
from app.services.telegram_link import clear_expired, issue_code
from app.telegram_bot import TelegramBot
from sqlalchemy.orm import sessionmaker

from .conftest import token
from .test_agent import FakeLLM


def make_bot(db, response=None, file_error=False):
    outbound = []

    def telegram(request):
        if request.url.path.endswith("/getFile") and file_error:
            return httpx.Response(503, json={"ok": False, "error_code": 503})
        if request.url.path.endswith("/getFile"):
            return httpx.Response(200, json={"ok": True, "result": {"file_path": "voice.oga"}})
        if request.method == "GET":
            return httpx.Response(200, content=b"simulated voice")
        assert request.url.path.endswith("/sendMessage")
        outbound.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {}})

    api = TelegramAPI(httpx.Client(base_url="https://api.telegram.org", transport=httpx.MockTransport(telegram)), "test")
    return TelegramBot(api, FakeLLM(response), sessionmaker(bind=db.bind)), outbound


def receive(bot, chat_id, text="", message_id=1, chat_type="private", **media):
    bot.handle({"message": {"chat": {"type": chat_type, "id": chat_id}, "from": {"id": chat_id},
                            "message_id": message_id, "text": text, **media}})


def test_link_from_settings_once_and_unlink(client, db):
    headers = token(client)
    user = db.query(User).filter_by(email="admin@test.local").one()
    response = client.post("/settings/telegram/code", headers=headers)
    code = response.json()["code"]
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["expires_in"] == 600
    assert user.telegram_code_hash and user.telegram_code_hash != code
    bot, outbound = make_bot(db)
    receive(bot, 101, "/resumen")
    receive(bot, 101, f"/start {code}", chat_type="group")
    receive(bot, 101, f"/start {code}", chat_type="channel")
    assert outbound == []
    receive(bot, 101, f"/start {code}")
    receive(bot, 202, f"/start {code}")
    assert len(outbound) == 1 and outbound[0]["chat_id"] == 101
    db.expire_all()
    assert client.get("/settings/telegram", headers=headers).json() == {"linked": True}
    assert client.post("/settings/telegram/code", headers=headers).status_code == 409
    assert client.delete("/settings/telegram", headers=headers).status_code == 204
    receive(bot, 101, "/resumen", message_id=2)
    assert len(outbound) == 1


def test_expired_code_and_failed_attempt_limit(db):
    user = db.query(User).first()
    code = issue_code(db, user.id)
    user.telegram_code_expires = int(time()) - 1
    db.commit()
    bot, outbound = make_bot(db)
    receive(bot, 101, f"/start {code}")
    clear_expired(db, int(time()))
    assert user.telegram_code_hash is None
    for _ in range(4):
        receive(bot, 101, "/start invalid")
    code = issue_code(db, user.id)
    receive(bot, 101, f"/start {code}")
    assert outbound == []
    receive(bot, 202, f"/start {code}")
    assert len(outbound) == 1 and outbound[0]["chat_id"] == 202


def test_summary_and_chat_isolate_users_and_deduplicate(db):
    first, second = db.query(User).order_by(User.id).limit(2).all()
    first.telegram_id = 101
    second.telegram_id = 202
    db.add(WeightEntry(user_id=second.id, date=date.today(), weight_kg=88))
    db.commit()
    bot, outbound = make_bot(db, LLMResponse("", [ToolCall("get_weight_status", {})]))
    receive(bot, 101, "/resumen")
    receive(bot, 101, "/resumen")
    receive(bot, 202, "mi peso")
    assert len(outbound) == 2
    assert "88.0" not in outbound[0]["text"]
    assert "88.0" in outbound[1]["text"]
    actions = db.query(AgentAction).order_by(AgentAction.id).all()
    assert [action.user_id for action in actions] == [first.id] * 3 + [second.id]
    assert all(action.arguments == "{}" and "88.0" not in action.result for action in actions)


def test_calendar_confirmation_is_bound_to_one_chat_and_action(db, monkeypatch):
    first, second = db.query(User).order_by(User.id).limit(2).all()
    first.telegram_id, second.telegram_id = 101, 202
    db.commit()
    call = ToolCall("add_calendar_event", {
        "title": "Cita privada", "start": "2026-12-01T13:00:00", "end": "2026-12-01T14:00:00",
        "confirmed": True,
    })
    bot, outbound = make_bot(db, LLMResponse("Evento creado", [call]))
    executed = []

    def execute(call, user, db, **options):
        executed.append((call, user.id, options))
        return "Evento creado"

    monkeypatch.setattr("app.telegram_bot.run_tool", execute)
    receive(bot, 101, "Sí, confirmado")
    assert not executed and "Cita privada" in outbound[-1]["text"]
    confirmation = "/confirmar " + outbound[-1]["text"].split("/confirmar ", 1)[1].split()[0]
    receive(bot, 202, confirmation)
    assert not executed
    receive(bot, 101, confirmation, message_id=2)
    receive(bot, 101, confirmation, message_id=3)
    assert executed == [(call, first.id, {"confirmed": True, "private": True})]


def test_gemini_and_telegram_failures_are_user_readable(db):
    user = db.query(User).first()
    user.telegram_id = 101
    db.commit()
    bot, outbound = make_bot(db, LLMQuotaExceeded("Se ha alcanzado la cuota."), file_error=True)
    receive(bot, 101, "Hola")
    assert "cuota" in outbound[-1]["text"]
    bot.llm.response = LLMUnavailable("Gemini no está disponible.")
    receive(bot, 101, "Hola", message_id=2)
    assert "no está disponible" in outbound[-1]["text"]
    receive(bot, 101, message_id=3, voice={"file_id": "test"})
    assert "no pudo descargar" in outbound[-1]["text"]
    bot, outbound = make_bot(db, LLMUnsupportedMedia("Gemini no admite esta nota de voz."))
    receive(bot, 101, message_id=4, voice={"file_id": "test"})
    assert "no admite" in outbound[-1]["text"]
    assert db.query(AgentAction).count() == 0


def test_missing_or_rejected_token_leaves_worker_idle(monkeypatch):
    from app import telegram_bot

    notices = []
    monkeypatch.setattr(telegram_bot, "idle", notices.append)
    monkeypatch.setattr(telegram_bot.settings, "telegram_bot_token", None)
    telegram_bot.main()
    assert notices == ["Bot inactivo: TELEGRAM_BOT_TOKEN ausente o inválido."]

    fake_telegram = httpx.MockTransport(
        lambda request: httpx.Response(401, json={"ok": False, "error_code": 401}),
    )
    client = httpx.Client(base_url="https://api.telegram.org", transport=fake_telegram)
    monkeypatch.setattr(telegram_bot.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(telegram_bot.settings, "telegram_bot_token", "123:example")
    telegram_bot.main()
    assert notices[-1] == "Bot inactivo: Telegram rechazó TELEGRAM_BOT_TOKEN."
