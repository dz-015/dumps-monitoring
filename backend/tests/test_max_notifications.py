"""Тесты MAX-канала: токены привязки, статус-эндпойнт, бот, рассылка.

Сеть не трогается: HTTP к platform-api2.max.ru подменяется стабами.
Схема зеркальна Telegram: deep-link из профиля → событие bot_started с
payload → бот запоминает max_user_id → рассылка из ingest.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from PIL import Image

from app.config import settings
from app.ingest import ingest_frame
from app.max_bot import handle_update
from app.ml.pipeline import Verdict
from app.notify import make_link_token, max_deep_link, parse_link_token
from tests.conftest import auth_headers, make_camera, make_org, make_site, make_user

TAKEN_AT = dt.datetime(2026, 8, 3, 9, 0, 0, tzinfo=dt.UTC)


@pytest.fixture
def max_on(monkeypatch):
    monkeypatch.setattr(settings, "MAX_BOT_TOKEN", "max-test-token")
    monkeypatch.setattr(settings, "MAX_BOT_USERNAME", "id1234_bot")


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    dest = tmp_path / "uploads"
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(dest))
    return dest


# ── токены привязки ──────────────────────────────────────────────────────

def test_max_link_token_is_not_a_telegram_token():
    # Токены каналов не взаимозаменяемы: другой purpose — другая подпись.
    tg = make_link_token(42)
    mx = make_link_token(42, purpose="max-link")
    assert parse_link_token(tg) == 42
    assert parse_link_token(mx, purpose="max-link") == 42
    assert parse_link_token(tg, purpose="max-link") is None
    assert parse_link_token(mx) is None


def test_max_deep_link_format(max_on):
    link = max_deep_link(7)
    assert link.startswith("https://max.ru/id1234_bot?start=")
    token = link.split("start=")[1]
    assert len(token) <= 128  # лимит payload у МАКС
    assert parse_link_token(token, purpose="max-link") == 7


# ── статус-эндпойнт ──────────────────────────────────────────────────────

def test_max_status_disabled_without_token(client, db):
    org = make_org(db)
    user = make_user(db, email="a@b.c", org=org)
    body = client.get("/api/notifications/max", headers=auth_headers(user)).json()
    assert body["enabled"] is False
    assert body["link"] is None


def test_max_status_gives_deep_link(client, db, max_on):
    org = make_org(db)
    user = make_user(db, email="a@b.c", org=org)
    body = client.get("/api/notifications/max", headers=auth_headers(user)).json()
    assert body["enabled"] is True
    assert body["connected"] is False
    assert body["link"].startswith("https://max.ru/id1234_bot?start=")


def test_max_disconnect(client, db, max_on):
    org = make_org(db)
    user = make_user(db, email="a@b.c", org=org)
    user.max_user_id = 555
    db.commit()
    body = client.delete("/api/notifications/max", headers=auth_headers(user)).json()
    assert body["connected"] is False
    db.refresh(user)
    assert user.max_user_id is None


def test_me_exposes_max_connected(client, db):
    org = make_org(db)
    user = make_user(db, email="a@b.c", org=org)
    user.max_user_id = 555
    db.commit()
    body = client.get("/api/auth/me", headers=auth_headers(user)).json()
    assert body["max_connected"] is True


# ── бот: bot_started с payload ───────────────────────────────────────────

@pytest.fixture
def max_replies(monkeypatch):
    sent: list[tuple[int, str]] = []

    import app.max_api as max_api
    monkeypatch.setattr(max_api, "send_message",
                        lambda user_id, text: sent.append((user_id, text)) or True)
    return sent


def bot_started(max_user_id: int, payload: str) -> dict:
    return {
        "update_type": "bot_started",
        "chat_id": 100,
        "user": {"user_id": max_user_id, "name": "Тест"},
        "payload": payload,
    }


def test_bot_started_links_account(db, max_on, max_replies, monkeypatch):
    _bind_test_db(monkeypatch, db)
    org = make_org(db)
    user = make_user(db, email="a@b.c", org=org)

    handle_update(bot_started(555, make_link_token(user.id, purpose="max-link")))

    db.expire_all()
    assert user.max_user_id == 555
    assert max_replies and max_replies[0][0] == 555
    assert "a@b.c" in max_replies[0][1]


def test_bot_started_with_garbage_payload_sends_help(db, max_on, max_replies, monkeypatch):
    _bind_test_db(monkeypatch, db)
    handle_update(bot_started(555, "мусор"))
    assert max_replies and "профиль" in max_replies[0][1].lower()


def test_telegram_token_is_rejected_by_max_bot(db, max_on, max_replies, monkeypatch):
    _bind_test_db(monkeypatch, db)
    org = make_org(db)
    user = make_user(db, email="a@b.c", org=org)

    handle_update(bot_started(555, make_link_token(user.id)))  # telegram-purpose

    db.expire_all()
    assert user.max_user_id is None


def _bind_test_db(monkeypatch, db):
    """handle_update открывает собственную сессию — подсовываем тестовую."""
    import app.max_bot as max_bot

    class _Ctx:
        def __enter__(self):
            return db
        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(max_bot, "SessionLocal", lambda: _Ctx())


# ── рассылка из ingest ───────────────────────────────────────────────────

class StubPipeline:
    def run(self, image, camera_key=None, taken_at=None):
        return Verdict(detections=[], has_overflow=True, has_contamination=False,
                       dropped_by_roi=0)


def make_frame(tmp_path) -> Path:
    path = tmp_path / "cam2_2026-08-03_090000.jpg"
    Image.new("RGB", (64, 48)).save(path, format="JPEG")
    return path


def test_ingest_notifies_max_and_telegram_channels(db, tmp_path, uploads, max_on, monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123:test-token")
    tg_sent, max_sent = [], []
    import app.max_api as max_api
    import app.notify as notify
    monkeypatch.setattr(notify, "send_photo",
                        lambda chat_id, path, caption: tg_sent.append(chat_id) or True)
    monkeypatch.setattr(notify, "send_message", lambda chat_id, text: True)
    monkeypatch.setattr(max_api, "send_photo",
                        lambda user_id, path, caption: max_sent.append(user_id) or True)
    monkeypatch.setattr(max_api, "send_message", lambda user_id, text: True)

    org = make_org(db)
    site = make_site(db, org)
    camera = make_camera(db, site)
    both = make_user(db, email="both@b.c", org=org)
    both.telegram_chat_id = 111
    both.max_user_id = 555
    only_max = make_user(db, email="max@b.c", org=org)
    only_max.max_user_id = 777
    db.commit()

    ingest_frame(db, camera, make_frame(tmp_path), TAKEN_AT, pipeline=StubPipeline())

    assert tg_sent == [111]
    assert sorted(max_sent) == [555, 777]


def test_ingest_max_only_channel(db, tmp_path, uploads, max_on, monkeypatch):
    # Telegram не настроен вовсе — MAX-канал работает сам по себе.
    max_sent = []
    import app.max_api as max_api
    monkeypatch.setattr(max_api, "send_photo",
                        lambda user_id, path, caption: max_sent.append((user_id, caption)) or True)

    org = make_org(db)
    site = make_site(db, org)
    camera = make_camera(db, site)
    user = make_user(db, email="max@b.c", org=org)
    user.max_user_id = 555
    db.commit()

    ingest_frame(db, camera, make_frame(tmp_path), TAKEN_AT, pipeline=StubPipeline())

    assert [uid for uid, _ in max_sent] == [555]
    assert "переполнение" in max_sent[0][1]


# ── отправка фото: ретрай «attachment not ready» ─────────────────────────

def test_send_photo_retries_until_attachment_ready(tmp_path, max_on, monkeypatch):
    import app.max_api as max_api

    photo = tmp_path / "x.jpg"
    Image.new("RGB", (8, 8)).save(photo, format="JPEG")

    class Resp:
        def __init__(self, status, body=""):
            self.status_code = status
            self.ok = status < 400
            self.text = body
        def json(self):
            import json
            return json.loads(self.text)

    calls = {"messages": 0}

    def fake_post(url, **kwargs):
        if "/uploads" in url:
            return Resp(200, '{"url": "https://upload.example/u1"}')
        if "upload.example" in url:
            return Resp(200, '{"photos": {"p1": {"token": "tok"}}}')
        calls["messages"] += 1
        if calls["messages"] < 3:
            return Resp(400, '{"code": "attachment.not.ready"}')
        return Resp(200, "{}")

    monkeypatch.setattr(max_api.requests, "post", fake_post)
    monkeypatch.setattr(max_api.time, "sleep", lambda s: None)

    assert max_api.send_photo(555, photo, "подпись") is True
    assert calls["messages"] == 3
