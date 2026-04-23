"""/api/sites should surface the derived per-site operational fields:

- `last_checked`: max(camera.last_checked) across the site's cameras; null if none.
- `active_status`: derived from unresolved alerts; falls back to the stored site.status.

These are pragmatic fields the UI needs and have no natural home on any single
underlying row. Compute them in the endpoint, don't denormalize into the Site table.
"""
import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Alert, Camera
from tests.conftest import auth_headers, make_camera, make_org, make_site, make_user


def test_last_checked_is_max_across_site_cameras(db: Session, client: TestClient) -> None:
    org = make_org(db, "OrgA")
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org, "Mixed cams")
    old = dt.datetime(2026, 4, 20, 10, 0, tzinfo=dt.UTC)
    new = dt.datetime(2026, 4, 23, 11, 0, tzinfo=dt.UTC)
    db.add_all([
        Camera(site_id=site.id, name="old-cam", rtsp_url="rtsp://x", last_checked=old),
        Camera(site_id=site.id, name="new-cam", rtsp_url="rtsp://y", last_checked=new),
    ])
    db.commit()

    resp = client.get("/api/sites", headers=auth_headers(user))

    assert resp.status_code == 200
    [payload] = resp.json()
    assert payload["last_checked"] is not None
    assert payload["last_checked"].startswith("2026-04-23T11:00")


def test_last_checked_null_when_no_cameras(db: Session, client: TestClient) -> None:
    org = make_org(db, "OrgA")
    user = make_user(db, email="u@test.local", org=org)
    make_site(db, org, "No cams")

    resp = client.get("/api/sites", headers=auth_headers(user))

    [payload] = resp.json()
    assert payload["last_checked"] is None


def test_active_status_reflects_open_overflow(db: Session, client: TestClient) -> None:
    org = make_org(db, "OrgA")
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org, "Busy site")
    # Stored status is "clean" but there's an unresolved overflow — derived should win.
    db.add(Alert(site_id=site.id, level="overflow", status="new"))
    db.commit()

    resp = client.get("/api/sites", headers=auth_headers(user))

    [payload] = resp.json()
    assert payload["active_status"] == "overflow"


def test_active_status_overflow_beats_contamination(db: Session, client: TestClient) -> None:
    org = make_org(db, "OrgA")
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org, "Both problems")
    db.add_all([
        Alert(site_id=site.id, level="overflow", status="accepted"),
        Alert(site_id=site.id, level="contamination", status="new"),
    ])
    db.commit()

    resp = client.get("/api/sites", headers=auth_headers(user))

    [payload] = resp.json()
    assert payload["active_status"] == "overflow"


def test_active_status_resolved_alerts_ignored(db: Session, client: TestClient) -> None:
    org = make_org(db, "OrgA")
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org, "Resolved site")
    make_camera(db, site, "cam")
    db.add(Alert(site_id=site.id, level="overflow", status="resolved"))
    db.commit()

    resp = client.get("/api/sites", headers=auth_headers(user))

    [payload] = resp.json()
    # No unresolved alerts + site has cameras → "clean"
    assert payload["active_status"] == "clean"
