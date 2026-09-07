"""Уведомления об алертах: Telegram и МАКС.

Ни один из ботов не может написать пользователю первым — привязка через
deep-link: профиль выдаёт ссылку t.me/<bot>?start=<токен> (или
max.ru/<bot>?start=<токен>), бот получает событие старта с токеном и
запоминает адрес доставки (см. app/telegram_bot.py и app/max_bot.py).
Здесь — обратная сторона: рассылка по уже привязанным адресам.

Рассылка best-effort: упавший мессенджер не должен ронять приём кадра,
поэтому все ошибки логируются и глотаются.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Alert, Site, Snapshot, User

logger = logging.getLogger(__name__)

_LINK_PURPOSE = "telegram-link"
_LINK_TTL_SECONDS = 3600

LEVEL_TEXT = {
    "overflow": "переполнение баков",
    "contamination": "навал мусора",
}


def telegram_enabled() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN)


def max_enabled() -> bool:
    from app import max_api

    return max_api.enabled()


# ── deep-link токены ─────────────────────────────────────────────────────

def _sign(payload: str, purpose: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(),
        f"{payload}|{purpose}".encode(),
        hashlib.sha256,
    ).hexdigest()[:20]


def make_link_token(user_id: int, purpose: str = _LINK_PURPOSE) -> str:
    """Короткоживущий токен для /start: кто нажал «Подключить» в профиле.

    Telegram ограничивает параметр deep-link 64 символами из [A-Za-z0-9_-]
    (у МАКС лимит payload — 128), поэтому НЕ JWT (в нём точки и ~150
    символов), а компактный hex-формат: ``<uid>-<истекает>-<hmac>``
    (~35 символов). ``purpose`` входит в подпись — токен одного канала
    нельзя скормить боту другого.
    """
    payload = f"{user_id:x}-{int(time.time()) + _LINK_TTL_SECONDS:x}"
    return f"{payload}-{_sign(payload, purpose)}"


def parse_link_token(token: str, purpose: str = _LINK_PURPOSE) -> int | None:
    parts = token.split("-")
    if len(parts) != 3:
        return None
    payload = f"{parts[0]}-{parts[1]}"
    if not hmac.compare_digest(_sign(payload, purpose), parts[2]):
        return None
    try:
        user_id, expires = int(parts[0], 16), int(parts[1], 16)
    except ValueError:
        return None
    if time.time() > expires:
        return None
    return user_id


def deep_link(user_id: int) -> str | None:
    if not settings.TELEGRAM_BOT_USERNAME:
        return None
    return f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={make_link_token(user_id)}"


MAX_LINK_PURPOSE = "max-link"


def max_deep_link(user_id: int) -> str | None:
    if not settings.MAX_BOT_USERNAME:
        return None
    token = make_link_token(user_id, purpose=MAX_LINK_PURPOSE)
    return f"https://max.ru/{settings.MAX_BOT_USERNAME}?start={token}"


# ── отправка ─────────────────────────────────────────────────────────────

def _api(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"


def _proxies() -> dict | None:
    return {"https": settings.TELEGRAM_PROXY} if settings.TELEGRAM_PROXY else None


def send_message(chat_id: int, text: str) -> bool:
    import requests

    try:
        resp = requests.post(_api("sendMessage"), json={"chat_id": chat_id, "text": text},
                             timeout=15, proxies=_proxies())
        return resp.ok
    except Exception:
        logger.exception("telegram sendMessage не прошёл (chat %s)", chat_id)
        return False


def send_photo(chat_id: int, photo_path: Path, caption: str) -> bool:
    import requests

    try:
        with photo_path.open("rb") as fh:
            resp = requests.post(
                _api("sendPhoto"),
                data={"chat_id": chat_id, "caption": caption},
                files={"photo": (photo_path.name, fh, "image/jpeg")},
                timeout=30,
                proxies=_proxies(),
            )
        return resp.ok
    except Exception:
        logger.exception("telegram sendPhoto не прошёл (chat %s)", chat_id)
        return False


def notify_alerts(db: Session, alerts: list[Alert], snapshot: Snapshot) -> int:
    """Шлёт фото кадра с описанием всем привязанным пользователям организации.

    Каналы независимы: пользователь с обеими привязками получит сообщение и в
    Telegram, и в МАКС. Возвращает число доставленных сообщений (для лога и
    тестов).
    """
    if not alerts or not (telegram_enabled() or max_enabled()):
        return 0

    site = db.query(Site).filter(Site.id == snapshot.site_id).first()
    if site is None:
        return 0
    from sqlalchemy import or_

    # Пользователи организации площадки + глобальные админы (они вне
    # организаций, но отвечают за всё).
    users = (
        db.query(User)
        .filter(
            or_(
                User.organization_id == site.organization_id,
                User.is_admin.is_(True),
            ),
            or_(
                User.telegram_chat_id.isnot(None),
                User.max_user_id.isnot(None),
            ),
            User.is_active.is_(True),
        )
        .all()
    )
    if not users:
        return 0

    problems = ", ".join(LEVEL_TEXT.get(a.level, a.level) for a in alerts)
    caption = (
        f"⚠️ ТКО-Мониторинг: {problems}\n"
        f"Площадка: {site.name}\n"
        f"Снимок: {snapshot.taken_at:%d.%m.%Y %H:%M} UTC\n"
        f"https://leti-metla.ru/alerts"
    )
    photo = Path(settings.UPLOAD_DIR) / snapshot.image_path
    has_photo = photo.is_file()

    from app import max_api

    delivered = 0
    attempted = 0
    for user in users:
        if telegram_enabled() and user.telegram_chat_id:
            attempted += 1
            ok = (
                send_photo(user.telegram_chat_id, photo, caption)
                if has_photo
                else send_message(user.telegram_chat_id, caption)
            )
            delivered += int(ok)
        if max_enabled() and user.max_user_id:
            attempted += 1
            ok = (
                max_api.send_photo(user.max_user_id, photo, caption)
                if has_photo
                else max_api.send_message(user.max_user_id, caption)
            )
            delivered += int(ok)
    logger.info("уведомления: %d/%d доставлено (site %s)",
                delivered, attempted, site.id)
    return delivered
