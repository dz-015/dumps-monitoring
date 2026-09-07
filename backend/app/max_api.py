"""Клиент Bot API мессенджера МАКС (наследник TamTam Bot API).

Все обращения к platform-api2.max.ru собраны здесь, чтобы предположения о
формате API жили в одном месте (docs/MAX_BOT.md — конспект документации).

Грабли, учтённые в коде:
- токен передаётся в заголовке ``Authorization`` БЕЗ префикса ``Bearer``
  (с ним API отвечает 401);
- личный диалог адресуется ``user_id`` пользователя, а не ``chat_id``;
- вложение-фото обрабатывается асинхронно: отправка сразу после аплоада
  может вернуть 400 «attachment not ready» — нужен ретрай с паузой;
- лимиты: 30 rps на бота, ≤2 сообщений/с в один диалог, текст ≤4000 симв.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import requests

from app.config import settings

logger = logging.getLogger(__name__)

# Сколько раз пробуем отправить сообщение с ещё не обработанным вложением.
_ATTACHMENT_ATTEMPTS = 5


def enabled() -> bool:
    return bool(settings.MAX_BOT_TOKEN)


def _url(path: str) -> str:
    return f"{settings.MAX_API_BASE}{path}"


def _headers() -> dict[str, str]:
    return {"Authorization": settings.MAX_BOT_TOKEN}


def get_updates(marker: int | None, timeout: int = 50) -> dict:
    """Long polling: один запрос /updates. Возвращает {"updates": [...], "marker": N}.

    Ошибки сети пробрасываются — цикл в max_bot.main() сам решает, сколько спать.
    """
    params: dict = {"timeout": timeout, "types": "bot_started,message_created"}
    if marker is not None:
        params["marker"] = marker
    resp = requests.get(_url("/updates"), params=params, headers=_headers(),
                        timeout=timeout + 10)
    resp.raise_for_status()
    return resp.json()


def send_message(user_id: int, text: str) -> bool:
    try:
        resp = requests.post(
            _url("/messages"),
            params={"user_id": user_id},
            json={"text": text, "notify": True},
            headers=_headers(),
            timeout=15,
        )
        if not resp.ok:
            logger.warning("max send_message %s: %s %s", user_id, resp.status_code,
                           resp.text[:200])
        return resp.ok
    except Exception:
        logger.exception("max send_message не прошёл (user %s)", user_id)
        return False


def _upload_image(photo_path: Path) -> dict | None:
    """Двухшаговый аплоад: взять upload-URL → залить файл.

    Возвращает тело ответа аплоада (``{"photos": {...}}``) — оно и есть
    payload вложения типа image.
    """
    resp = requests.post(_url("/uploads"), params={"type": "image"},
                         headers=_headers(), timeout=15)
    if not resp.ok:
        logger.warning("max /uploads: %s %s", resp.status_code, resp.text[:200])
        return None
    upload_url = resp.json().get("url")
    if not upload_url:
        return None
    with photo_path.open("rb") as fh:
        uploaded = requests.post(
            upload_url,
            files={"data": (photo_path.name, fh, "image/jpeg")},
            timeout=30,
        )
    if not uploaded.ok:
        logger.warning("max upload файла: %s %s", uploaded.status_code,
                       uploaded.text[:200])
        return None
    return uploaded.json()


def send_photo(user_id: int, photo_path: Path, caption: str) -> bool:
    """Фото с подписью; при недоступном вложении откатывается на текст."""
    try:
        payload = _upload_image(photo_path)
    except Exception:
        logger.exception("max аплоад фото не прошёл (user %s)", user_id)
        payload = None
    if payload is None:
        return send_message(user_id, caption)

    body = {
        "text": caption,
        "notify": True,
        "attachments": [{"type": "image", "payload": payload}],
    }
    for attempt in range(_ATTACHMENT_ATTEMPTS):
        try:
            resp = requests.post(
                _url("/messages"),
                params={"user_id": user_id},
                json=body,
                headers=_headers(),
                timeout=30,
            )
        except Exception:
            logger.exception("max send_photo не прошёл (user %s)", user_id)
            return False
        if resp.ok:
            return True
        # Вложение ещё обрабатывается — подождать и повторить.
        if resp.status_code == 400 and "attachment" in resp.text.lower():
            time.sleep(1 + attempt)
            continue
        logger.warning("max send_photo %s: %s %s", user_id, resp.status_code,
                       resp.text[:200])
        break
    return send_message(user_id, caption)
