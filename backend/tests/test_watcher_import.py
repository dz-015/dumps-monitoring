"""Тесты заведения камер платформы в нашу базу."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.db.models import Camera, Organization, Site
from app.watcher_import import (
    import_cameras,
    next_key,
    parse_coordinates,
    pretty_address,
    to_cyrillic,
)


@pytest.mark.parametrize(("stream", "expected"), [
    ("kievskaya.ul..122.g..simferopol-f9a469d498", "Киевская ул. 122 г. Симферополь"),
    ("fruktovyj.per..18.g..simferopol-7496d1f467", "Фруктовый пер. 18 г. Симферополь"),
    ("sovetskaya.ul..10.g..simferopol-aabbccddee", "Советская ул. 10 г. Симферополь"),
    ("zhelyabova.ul..37.g..simferopol-1122334455", "Желябова ул. 37 г. Симферополь"),
    ("kujbysheva.ul..29.g..simferopol-5566778899", "Куйбышева ул. 29 г. Симферополь"),
    ("industrialnaya.ul..30.g..simferopol-64769fb1af",
     "Индустриальная ул. 30 г. Симферополь"),
])
def test_pretty_address_unwraps_stream_name(stream, expected):
    assert pretty_address(stream) == expected


def test_to_cyrillic_keeps_ts_as_two_letters():
    """«ts» в наших названиях — это «тс», а не «ц» (советская, не совецкая)."""
    assert to_cyrillic("sovetskaya") == "советская"


def test_pretty_address_drops_hash_tail():
    assert pretty_address("amurskaya.ul..18.g..simferopol-8eadf1fce5").endswith("Симферополь")


def test_parse_coordinates():
    assert parse_coordinates("44.95 34.11") == (44.95, 34.11)
    assert parse_coordinates("") == (None, None)
    assert parse_coordinates("сломано") == (None, None)
    assert parse_coordinates("44.95") == (None, None)


def _platform(*cams):
    return [
        {"name": n, "coordinates": c, "stream_status": {"alive": a}}
        for n, c, a in cams
    ]


def test_import_creates_org_sites_and_cameras(db):
    data = _platform(
        ("kievskaya.ul..122.g..simferopol-aaaaaa", "44.95 34.11", True),
        ("amurskaya.ul..18.g..simferopol-bbbbbb", "44.93 34.13", False),
    )
    with patch("app.watcher_import.watcher.list_cameras", return_value=data):
        summary = import_cameras(db, "Мусорные Баки")

    assert summary["создано"] == 2
    assert summary["живых"] == 1
    org = db.query(Organization).filter(Organization.name == "Мусорные Баки").one()
    assert db.query(Site).filter(Site.organization_id == org.id).count() == 2

    cams = db.query(Camera).order_by(Camera.watcher_stream).all()
    assert [c.is_active for c in cams] == [False, True]   # amurskaya, kievskaya
    assert {c.external_key for c in cams} == {"w1", "w2"}
    assert cams[0].rtsp_url.startswith("watcher://")


def test_import_is_idempotent(db):
    data = _platform(("kievskaya.ul..122.g..simferopol-aaaaaa", "44.95 34.11", True))
    with patch("app.watcher_import.watcher.list_cameras", return_value=data):
        import_cameras(db, "Мусорные Баки")
        summary = import_cameras(db, "Мусорные Баки")

    assert summary["создано"] == 0
    assert summary["обновлено"] == 1
    assert db.query(Camera).count() == 1
    assert db.query(Site).count() == 1


def test_import_activates_camera_when_stream_returns(db):
    """Камера ожила на платформе — при следующем запуске включаем её."""
    dead = _platform(("street.ul..1.g..simferopol-cccccc", "44.9 34.1", False))
    alive = _platform(("street.ul..1.g..simferopol-cccccc", "44.9 34.1", True))

    with patch("app.watcher_import.watcher.list_cameras", return_value=dead):
        import_cameras(db, "Мусорные Баки")
    assert db.query(Camera).one().is_active is False

    with patch("app.watcher_import.watcher.list_cameras", return_value=alive):
        import_cameras(db, "Мусорные Баки")
    assert db.query(Camera).one().is_active is True


def test_dry_run_saves_nothing(db):
    data = _platform(("street.ul..1.g..simferopol-dddddd", "44.9 34.1", True))
    with patch("app.watcher_import.watcher.list_cameras", return_value=data):
        summary = import_cameras(db, "Мусорные Баки", dry_run=True)

    assert summary["создано"] == 1
    assert db.query(Camera).count() == 0
    assert db.query(Organization).count() == 0


def test_import_refuses_empty_platform_list(db):
    with patch("app.watcher_import.watcher.list_cameras", return_value=[]), \
         pytest.raises(RuntimeError):
        import_cameras(db, "Мусорные Баки")


def test_next_key_skips_used(db):
    from tests.conftest import make_camera, make_org, make_site
    org = make_org(db)
    site = make_site(db, org)
    cam = make_camera(db, site)
    cam.external_key = "w1"
    db.commit()
    assert next_key(db) == "w2"
