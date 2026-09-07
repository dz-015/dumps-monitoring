"""Тесты Telegram-канала: токены привязки, статус-эндпойнт, рассылка из ingest.

Сеть не трогается: отправка подменяется стабом, проверяется логика выбора
получателей и склейка процессов (ingest → notify → бот привязал chat_id).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from PIL import Image

from app.config import settings
from app.db.models import Snapshot
from app.ingest import ingest_frame
from app.ml.pipeline import Verdict
from app.notify import make_link_token, notify_alerts, parse_link_token
from tests.conftest import auth_headers, make_camera, make_org, make_site, make_user

TAKEN_AT = dt.datetime(2026, 8, 3, 9, 0, 0, tzinfo=dt.timezone.utc)


@pytest.fixture
def tg_on(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123:test-token")
    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", "leti_metla_bot")


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    dest = tmp_path / "uploads"
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(dest))
    return dest


# ── токены привязки ──────────────────────────────────────────────────────

def test_link_token_roundtrip():
    assert parse_link_token(make_link_token(42)) == 42


def test_link_token_garbage_is_rejected():
    assert parse_link_token("не токен") is None
    assert parse_link_token("") is None


def test_access_token_is_not_a_link_token(db):
    # Токен логина не должен работать как токен привязки (другой purpose).
    from app.auth import create_access_token
    assert parse_link_token(create_access_token({"sub": "42"})) is None


# ── статус-эндпойнт ──────────────────────────────────────────────────────

def test_telegram_status_disabled_without_token(client, db):
    org = make_org(db)
    user = make_user(db, email="a@b.c", org=org)
    resp = client.get("/api/notifications/telegram", headers=auth_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["link"] is None


def test_telegram_status_gives_deep_link(client, db, tg_on):
    org = make_org(db)
    user = make_user(db, email="a@b.c", org=org)
    body = client.get("/api/notifications/telegram", headers=auth_headers(user)).json()
    assert body["enabled"] is True
    assert body["connected"] is False
    assert body["link"].startswith("https://t.me/leti_metla_bot?start=")
    token = body["link"].split("start=")[1]
    assert parse_link_token(token) == user.id


def test_telegram_disconnect(client, db, tg_on):
    org = make_org(db)
    user = make_user(db, email="a@b.c", org=org)
    user.telegram_chat_id = 777
    db.commit()
    body = client.delete("/api/notifications/telegram", headers=auth_headers(user)).json()
    assert body["connected"] is False
    db.refresh(user)
    assert user.telegram_chat_id is None


def test_me_exposes_telegram_connected(client, db):
    org = make_org(db)
    user = make_user(db, email="a@b.c", org=org)
    user.telegram_chat_id = 777
    db.commit()
    body = client.get("/api/auth/me", headers=auth_headers(user)).json()
    assert body["telegram_connected"] is True


# ── рассылка ─────────────────────────────────────────────────────────────

class SentLog:
    def __init__(self):
        self.photos: list[tuple[int, str]] = []


@pytest.fixture
def sent(monkeypatch):
    log = SentLog()

    def fake_photo(chat_id, photo_path, caption):
        log.photos.append((chat_id, caption))
        return True

    import app.notify as notify
    monkeypatch.setattr(notify, "send_photo", fake_photo)
    monkeypatch.setattr(notify, "send_message", lambda chat_id, text: True)
    return log


def make_frame(tmp_path) -> Path:
    path = tmp_path / "cam2_2026-08-03_090000.jpg"
    Image.new("RGB", (64, 48)).save(path, format="JPEG")
    return path


class StubPipeline:
    def run(self, image, camera_key=None, taken_at=None):
        return Verdict(detections=[], has_overflow=True, has_contamination=False,
                       dropped_by_roi=0)


def test_ingest_notifies_linked_org_users(db, tmp_path, uploads, tg_on, sent):
    org = make_org(db)
    site = make_site(db, org)
    camera = make_camera(db, site)
    linked = make_user(db, email="linked@b.c", org=org)
    linked.telegram_chat_id = 111
    unlinked = make_user(db, email="unlinked@b.c", org=org)  # noqa: F841 — без chat_id
    outsider = make_user(db, email="out@b.c", org=make_org(db, name="Другая"))
    outsider.telegram_chat_id = 222
    db.commit()

    ingest_frame(db, camera, make_frame(tmp_path), TAKEN_AT, pipeline=StubPipeline())

    chats = [chat for chat, _ in sent.photos]
    assert chats == [111]  # только привязанный пользователь СВОЕЙ организации
    assert "переполнение" in sent.photos[0][1]


def test_ingest_notifies_global_admin_too(db, tmp_path, uploads, tg_on, sent):
    org = make_org(db)
    site = make_site(db, org)
    camera = make_camera(db, site)
    admin = make_user(db, email="root@b.c", is_admin=True)  # без организации
    admin.telegram_chat_id = 999
    db.commit()

    ingest_frame(db, camera, make_frame(tmp_path), TAKEN_AT, pipeline=StubPipeline())
    assert [chat for chat, _ in sent.photos] == [999]


def test_notify_noop_without_alerts(db, tmp_path, uploads, tg_on, sent):
    org = make_org(db)
    site = make_site(db, org)
    camera = make_camera(db, site)
    snapshot = Snapshot(site_id=site.id, camera_id=camera.id,
                        image_path="snapshots/x.jpg", taken_at=TAKEN_AT.replace(tzinfo=None))
    db.add(snapshot)
    db.commit()
    assert notify_alerts(db, [], snapshot) == 0
    assert sent.photos == []


# ── бот: обработка /start ────────────────────────────────────────────────

def test_bot_links_chat_on_start(db, tg_on, monkeypatch):
    org = make_org(db)
    user = make_user(db, email="a@b.c", org=org)
    token = make_link_token(user.id)

    import app.telegram_bot as bot
    replies = []
    monkeypatch.setattr(bot, "SessionLocal", lambda: _SessionCtx(db))
    monkeypatch.setattr(
        bot.requests, "post",
        lambda url, json=None, **kw: replies.append(json) or _Ok(),
    )

    bot.handle_update({"message": {"chat": {"id": 555}, "text": f"/start {token}"}})
    db.refresh(user)
    assert user.telegram_chat_id == 555
    assert "Готово" in replies[-1]["text"]


def test_bot_start_with_bad_token_sends_help(db, tg_on, monkeypatch):
    import app.telegram_bot as bot
    replies = []
    monkeypatch.setattr(bot, "SessionLocal", lambda: _SessionCtx(db))
    monkeypatch.setattr(
        bot.requests, "post",
        lambda url, json=None, **kw: replies.append(json) or _Ok(),
    )
    bot.handle_update({"message": {"chat": {"id": 555}, "text": "/start мусор"}})
    assert "привязать" in replies[-1]["text"]


class _SessionCtx:
    """Контекст-менеджер поверх фикстурной сессии — не закрывает её."""

    def __init__(self, db):
        self._db = db

    def __enter__(self):
        return self._db

    def __exit__(self, *args):
        return False


class _Ok:
    ok = True
