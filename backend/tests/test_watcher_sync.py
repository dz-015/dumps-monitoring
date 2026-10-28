"""Тесты съёма кадров с платформы Watcher в каталог планировщика.

Сама платформа подменена: проверяется выбор камер, имена файлов, атомарность
раскладки и устойчивость к сбою отдельной камеры.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from unittest.mock import patch

from app.watcher_sync import frame_name, sync_once, watched_cameras
from tests.conftest import make_camera, make_org, make_site


def _camera(db, site, *, key, stream, active=True):
    cam = make_camera(db, site, name=f"cam-{key}")
    cam.external_key = key
    cam.watcher_stream = stream
    cam.is_active = active
    db.commit()
    return cam


def test_frame_name_follows_scheduler_contract():
    taken = dt.datetime(2026, 9, 21, 8, 47, 34)
    assert frame_name("7", taken) == "cam7_2026-09-21_084734.jpg"


def test_watched_cameras_takes_only_active_with_stream(db):
    org = make_org(db)
    site = make_site(db, org)
    good = _camera(db, site, key="1", stream="street.one-abc")
    _camera(db, site, key="2", stream=None)           # без потока
    _camera(db, site, key="3", stream="s3", active=False)  # выключена

    assert [c.id for c in watched_cameras(db)] == [good.id]


def test_sync_once_writes_frame_per_camera(db, tmp_path):
    org = make_org(db)
    site = make_site(db, org)
    _camera(db, site, key="1", stream="alpha-1")
    _camera(db, site, key="2", stream="beta-2")

    with patch("app.watcher_sync.watcher.grab_jpeg", return_value=b"\xff\xd8\xffDATA"):
        written = sync_once(db, tmp_path)

    assert written == 2
    files = sorted(p.name for p in tmp_path.glob("*.jpg"))
    assert len(files) == 2
    assert files[0].startswith("cam1_") and files[1].startswith("cam2_")
    assert (tmp_path / files[0]).read_bytes() == b"\xff\xd8\xffDATA"


def test_sync_once_skips_camera_without_stream_frame(db, tmp_path):
    """Камера без сигнала отдаёт None — файла нет, остальные не страдают."""
    org = make_org(db)
    site = make_site(db, org)
    _camera(db, site, key="1", stream="dead-1")
    _camera(db, site, key="2", stream="live-2")

    def fake_grab(name):
        return None if name == "dead-1" else b"\xff\xd8\xffOK"

    with patch("app.watcher_sync.watcher.grab_jpeg", side_effect=fake_grab):
        written = sync_once(db, tmp_path)

    assert written == 1
    assert [p.name.split("_")[0] for p in tmp_path.glob("*.jpg")] == ["cam2"]


def test_sync_once_survives_camera_error(db, tmp_path):
    """Сбой на одной камере не останавливает обход остальных."""
    org = make_org(db)
    site = make_site(db, org)
    _camera(db, site, key="1", stream="boom-1")
    _camera(db, site, key="2", stream="good-2")

    def fake_grab(name):
        if name == "boom-1":
            raise RuntimeError("платформа недоступна")
        return b"\xff\xd8\xffOK"

    with patch("app.watcher_sync.watcher.grab_jpeg", side_effect=fake_grab):
        written = sync_once(db, tmp_path)

    assert written == 1
    assert [p.name.split("_")[0] for p in tmp_path.glob("*.jpg")] == ["cam2"]


def test_sync_once_leaves_no_temporary_files(db, tmp_path):
    """Кадр появляется целиком: планировщик не должен увидеть недописанный файл."""
    org = make_org(db)
    site = make_site(db, org)
    _camera(db, site, key="1", stream="alpha-1")

    with patch("app.watcher_sync.watcher.grab_jpeg", return_value=b"\xff\xd8\xffDATA"):
        sync_once(db, tmp_path)

    assert list(tmp_path.glob("*.tmp")) == []
    assert len(list(tmp_path.glob("*.jpg"))) == 1


def test_sync_once_creates_ingest_dir(db, tmp_path):
    org = make_org(db)
    site = make_site(db, org)
    _camera(db, site, key="1", stream="alpha-1")
    target = Path(tmp_path) / "does-not-exist-yet"

    with patch("app.watcher_sync.watcher.grab_jpeg", return_value=b"\xff\xd8\xffDATA"):
        sync_once(db, target)

    assert len(list(target.glob("*.jpg"))) == 1
