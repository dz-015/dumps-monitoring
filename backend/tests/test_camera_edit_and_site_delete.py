"""Editing existing cameras and deleting whole sites (with their cameras + history).

Operators need to fix typos in RTSP URLs after wiring a camera up wrong, and to
remove площадки that no longer exist. The DB has 1:N Site→Camera but the UI
treats them as 1:1, so "delete camera" in UI maps to "delete site + its
cameras + snapshots + alerts" on the backend.
"""

import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Alert, Camera, Site, Snapshot
from tests.conftest import auth_headers, make_camera, make_org, make_site, make_user


def test_patch_camera_updates_rtsp_url(db: Session, client: TestClient) -> None:
    org = make_org(db, "OrgA")
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org, "S")
    cam = make_camera(db, site, "cam-1")

    resp = client.patch(
        f"/api/cameras/{cam.id}",
        json={"rtsp_url": "rtsp://new-host:554/stream"},
        headers=auth_headers(user),
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["rtsp_url"] == "rtsp://new-host:554/stream"
    assert payload["name"] == "cam-1"  # untouched


def test_patch_camera_404_for_other_org(db: Session, client: TestClient) -> None:
    org_a = make_org(db, "A")
    org_b = make_org(db, "B")
    site_b = make_site(db, org_b, "B-site")
    cam_b = make_camera(db, site_b, "B-cam")
    user_a = make_user(db, email="a@test.local", org=org_a)

    resp = client.patch(
        f"/api/cameras/{cam_b.id}",
        json={"rtsp_url": "rtsp://hijack"},
        headers=auth_headers(user_a),
    )

    assert resp.status_code == 404


def test_delete_site_cascades_to_cameras_snapshots_alerts(
    db: Session, client: TestClient
) -> None:
    org = make_org(db, "OrgA")
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org, "S")
    cam = make_camera(db, site, "cam")
    db.add_all([
        Snapshot(
            site_id=site.id,
            camera_id=cam.id,
            image_path="x.jpg",
            taken_at=dt.datetime.now(dt.UTC),
        ),
        Alert(site_id=site.id, level="overflow", status="new"),
    ])
    db.commit()

    resp = client.delete(f"/api/sites/{site.id}", headers=auth_headers(user))

    assert resp.status_code == 204
    assert db.query(Site).filter(Site.id == site.id).first() is None
    assert db.query(Camera).filter(Camera.site_id == site.id).count() == 0
    assert db.query(Snapshot).filter(Snapshot.site_id == site.id).count() == 0
    assert db.query(Alert).filter(Alert.site_id == site.id).count() == 0
