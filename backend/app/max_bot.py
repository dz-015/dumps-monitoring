"""МАКС-бот привязки: long polling.

Единственная задача — принять событие ``bot_started`` с deep-link-токеном из
профиля (или сообщение ``/start <токен>``) и запомнить ``user_id``
пользователя; после этого рассылку делает app/notify.py прямо из приёма
кадра. Long polling выбран как и для Telegram: не нужен публичный URL, а
нагрузка — единицы сообщений в день. Дока называет polling «для разработки»;
когда упрёмся — переезд на webhook затронет только main(), обработчик общий.

Запуск:  python -m app.max_bot   (compose-сервис max-bot)
Без MAX_BOT_TOKEN процесс мирно спит, чтобы compose не рестартовал его в цикле.
"""

from __future__ import annotations

import logging
import time

from app import max_api
from app.config import settings
from app.db.database import SessionLocal
from app.db.models import User
from app.notify import MAX_LINK_PURPOSE, parse_link_token

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Это бот уведомлений «ТКО-Мониторинг».\n"
    "Чтобы привязать аккаунт, зайдите в профиль на https://leti-metla.ru, "
    "нажмите «Подключить MAX» и перейдите по ссылке — она добавит "
    "нужный код автоматически."
)


def _link_account(max_user_id: int, token: str) -> None:
    site_user_id = parse_link_token(token, purpose=MAX_LINK_PURPOSE) if token else None
    if site_user_id is None:
        max_api.send_message(max_user_id, HELP_TEXT)
        return

    with SessionLocal() as db:
        user = db.query(User).filter(User.id == site_user_id).first()
        if user is None:
            reply = "Аккаунт не найден — ссылка устарела. Возьмите свежую в профиле."
        else:
            user.max_user_id = max_user_id
            db.commit()
            reply = (f"Готово! Уведомления о переполнении и навалах будут "
                     f"приходить сюда ({user.email}).")
            logger.info("привязан max user %s к пользователю %s", max_user_id, user.id)
    max_api.send_message(max_user_id, reply)


def handle_update(update: dict) -> None:
    utype = update.get("update_type")

    if utype == "bot_started":
        max_user_id = (update.get("user") or {}).get("user_id")
        if not max_user_id:
            return
        logger.info("bot_started: user=%s payload=%r",
                    max_user_id, (update.get("payload") or "")[:40])
        _link_account(max_user_id, (update.get("payload") or "").strip())
        return

    if utype == "message_created":
        message = update.get("message") or {}
        max_user_id = (message.get("sender") or {}).get("user_id")
        text = ((message.get("body") or {}).get("text") or "").strip()
        if not max_user_id:
            return
        logger.info("message_created: user=%s text=%r", max_user_id, text[:40])
        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            _link_account(max_user_id, parts[1].strip() if len(parts) == 2 else "")
        else:
            max_api.send_message(max_user_id, HELP_TEXT)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not settings.MAX_BOT_TOKEN:
        logger.warning("MAX_BOT_TOKEN не задан — бот выключен, сплю.")
        while True:
            time.sleep(3600)

    logger.info("МАКС-бот запущен (long polling, база %s)", settings.MAX_API_BASE)
    marker: int | None = None
    while True:
        try:
            data = max_api.get_updates(marker)
            marker = data.get("marker", marker)
            for update in data.get("updates", []):
                try:
                    handle_update(update)
                except Exception:
                    logger.exception("ошибка обработки update %r", update)
        except Exception:
            logger.exception("/updates упал, пауза 10 с")
            time.sleep(10)


if __name__ == "__main__":
    raise SystemExit(main())
