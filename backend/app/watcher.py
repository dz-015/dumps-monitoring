"""Клиент платформы видеонаблюдения Flussonic Watcher.

Камеры переехали на платформу (журнал 2026-08): прямой доступ к ним по RTSP
закрыли, кадр теперь берём у Watcher. Здесь собран весь HTTP к платформе и
декодирование кадра, чтобы предположения о её API жили в одном месте.

Грабли, учтённые в коде:
- сессия выдаётся ``POST /vsaas/api/v2/auth/login`` и передаётся заголовком
  ``x-vsaas-session`` (НЕ Bearer и не кука — иначе 403 "login is required");
- сессия протухает, и API отвечает 403; тогда нужен перелогин и повтор;
- у каждой камеры СВОЙ playback-токен из ``playback_config.token``, он идёт
  в query медиа-запросов;
- JPEG-превью платформа не отдаёт (``preview.jpg`` → 404), только видео
  ``preview.mp4``; первый кадр декодируем сами;
- видео приходит в H.265, поэтому нужен настоящий декодер (PyAV);
- для камеры без сигнала ``preview.mp4`` возвращает 10-байтную заглушку
  ``not found`` с кодом 200 — это не видео, проверяем размер.
"""

from __future__ import annotations

import logging
import threading

import requests

from app.config import settings

logger = logging.getLogger(__name__)

# Ответ короче этого — не видео, а текстовая заглушка платформы.
_MIN_VIDEO_BYTES = 1024

_session: str | None = None
_lock = threading.Lock()


def enabled() -> bool:
    return bool(settings.WATCHER_URL and settings.WATCHER_LOGIN)


def reset_session() -> None:
    """Забыть текущую сессию (перелогин при следующем запросе)."""
    global _session
    with _lock:
        _session = None


def _url(path: str) -> str:
    return f"{settings.WATCHER_URL.rstrip('/')}{path}"


def _login() -> str:
    """Получить сессию. Исключение пробрасываем — вызывающий решает, что делать."""
    resp = requests.post(
        _url("/vsaas/api/v2/auth/login"),
        json={"login": settings.WATCHER_LOGIN, "password": settings.WATCHER_PASSWORD},
        headers={"Content-Type": "application/json"},
        timeout=20,
    )
    resp.raise_for_status()
    session = resp.json().get("session")
    if not session:
        raise RuntimeError("Watcher: вход прошёл, но сессии в ответе нет")
    return session


def session() -> str:
    global _session
    with _lock:
        if _session is None:
            _session = _login()
        return _session


def _get(path: str, *, params: dict | None = None, timeout: int = 30):
    """GET к платформе с сессией. На 403 — один перелогин и повтор."""
    resp = requests.get(
        _url(path), params=params,
        headers={"x-vsaas-session": session()}, timeout=timeout,
    )
    if resp.status_code == 403:
        logger.info("Watcher: сессия протухла, вхожу заново")
        reset_session()
        resp = requests.get(
            _url(path), params=params,
            headers={"x-vsaas-session": session()}, timeout=timeout,
        )
    return resp


def list_cameras() -> list[dict]:
    """Все камеры, видимые нашей учётной записи (она ограничена одной организацией)."""
    resp = _get("/vsaas/api/v2/cameras", params={"limit": 1000})
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    for key in ("cameras", "results", "data"):
        if isinstance(data.get(key), list):
            return data[key]
    return []


def alive_names() -> list[str]:
    """Имена камер, которые прямо сейчас отдают поток."""
    return [
        c["name"] for c in list_cameras()
        if c.get("stream_status", {}).get("alive")
    ]


def camera_detail(name: str) -> dict:
    resp = _get(f"/vsaas/api/v2/cameras/{name}")
    resp.raise_for_status()
    return resp.json()


def playback_token(name: str) -> str | None:
    """Токен просмотра конкретной камеры (у каждой свой)."""
    try:
        return camera_detail(name).get("playback_config", {}).get("token") or None
    except Exception:
        logger.exception("Watcher: не смог получить playback-токен камеры %s", name)
        return None


def decode_first_frame(video: bytes) -> bytes | None:
    """Первый кадр видео → JPEG.

    PyAV импортируется лениво: модуль должен грузиться и там, где декодер не
    нужен (тесты, веб-процесс), а сам пакет тяжёлый.
    """
    import io

    import av  # noqa: PLC0415 — ленивый импорт намеренно

    try:
        with av.open(io.BytesIO(video)) as container:
            for frame in container.decode(video=0):
                image = frame.to_image()
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=92)
                return buffer.getvalue()
    except Exception:
        logger.exception("Watcher: не удалось декодировать кадр")
    return None


def grab_jpeg(name: str) -> bytes | None:
    """Снять текущий кадр камеры. None — если потока нет или он не декодируется."""
    token = playback_token(name)
    if not token:
        logger.info("Watcher: у камеры %s нет playback-токена (нет потока)", name)
        return None

    resp = _get(f"/{name}/preview.mp4", params={"token": token}, timeout=45)
    if not resp.ok or len(resp.content) < _MIN_VIDEO_BYTES:
        logger.info("Watcher: камера %s не отдала видео (%s, %d байт)",
                    name, resp.status_code, len(resp.content))
        return None

    return decode_first_frame(resp.content)
