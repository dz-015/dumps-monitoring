"""Telegram-бот привязки: long polling, БЕЗ вебхука.

Единственная задача — принять /start с deep-link-токеном из профиля и
запомнить chat_id пользователя; после этого рассылку делает app/notify.py
прямо из приёма кадра. Long polling выбран сознательно: не нужен публичный
URL и настройка вебхука, а нагрузка — единицы сообщений в день.

Запуск:  python -m app.telegram_bot   (compose-сервис telegram-bot)
Без TELEGRAM_BOT_TOKEN процесс мирно спит, чтобы compose не рестартовал его
в цикле.
"""

from __future__ import annotations

import logging
import time

import requests

from app.config import settings
from app.db.database import SessionLocal
from app.db.models import User
from app.notify import _proxies, parse_link_token

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Это бот уведомлений «ТКО-Мониторинг».\n"
    "Чтобы привязать аккаунт, зайдите в профиль на https://leti-metla.ru, "
    "нажмите «Подключить Telegram» и перейдите по ссылке — она добавит "
    "нужный код автоматически."
)


def _api(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"


def handle_update(update: dict) -> None:
    message = update.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    text = (message.get("text") or "").strip()
    logger.info("update %s: chat=%s text=%r", update.get("update_id"), chat_id, text[:40])
    if not chat_id or not text.startswith("/start"):
        return

    parts = text.split(maxsplit=1)
    token = parts[1].strip() if len(parts) == 2 else ""
    user_id = parse_link_token(token) if token else None
    if user_id is None:
        requests.post(_api("sendMessage"),
                      json={"chat_id": chat_id, "text": HELP_TEXT}, timeout=15,
                      proxies=_proxies())
        return

    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            reply = "Аккаунт не найден — ссылка устарела. Возьмите свежую в профиле."
        else:
            user.telegram_chat_id = chat_id
            db.commit()
            reply = (f"Готово! Уведомления о переполнении и навалах будут "
                     f"приходить сюда ({user.email}).")
            logger.info("привязан chat %s к пользователю %s", chat_id, user.id)
    requests.post(_api("sendMessage"), json={"chat_id": chat_id, "text": reply}, timeout=15,
                  proxies=_proxies())


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN не задан — бот выключен, сплю.")
        while True:
            time.sleep(3600)

    logger.info("бот запущен (long polling)")
    offset = 0
    while True:
        try:
            resp = requests.get(
                _api("getUpdates"),
                params={"timeout": 50, "offset": offset,
                        "allowed_updates": '["message"]'},
                timeout=60,
                proxies=_proxies(),
            )
            for update in resp.json().get("result", []):
                offset = max(offset, update["update_id"] + 1)
                try:
                    handle_update(update)
                except Exception:
                    logger.exception("ошибка обработки update %s", update.get("update_id"))
        except Exception:
            logger.exception("getUpdates упал, пауза 10 с")
            time.sleep(10)


if __name__ == "__main__":
    raise SystemExit(main())
