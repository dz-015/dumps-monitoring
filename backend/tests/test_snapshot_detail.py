"""GET /api/snapshots/{id} — single snapshot with detections for the alert
detail view. Must be org-scoped like every other resource."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Detection, Snapshot
from tests.conftest import auth_headers, make_camera, make_org, make_site, make_user


def _make_snapshot(db: Session, site, cam) -> Snapshot:
    snap = Snapshot(site_id=site.id, camera_id=cam.id, image_path="snap.jpg")
    db.add(snap)
    db.flush()
    db.add(
        Detection(
            snapshot_id=snap.id, class_name="bin_overflow", confidence=0.91,
            x=0.4, y=0.5, w=0.2, h=0.3,
        )
    )
    db.commit()
    db.refresh(snap)
    return snap


def test_returns_snapshot_with_detections(db: Session, client: TestClient):
    org = make_org(db)
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org)
    cam = make_camera(db, site)
    snap = _make_snapshot(db, site, cam)

    resp = client.get(f"/api/snapshots/{snap.id}", headers=auth_headers(user))

    assert resp.status_code == 200
    body = resp.json()
    assert body["image_path"] == "snap.jpg"
    assert len(body["detections"]) == 1
    assert body["detections"][0]["class_name"] == "bin_overflow"


def test_other_org_snapshot_is_404(db: Session, client: TestClient):
    org_a = make_org(db, "A")
    org_b = make_org(db, "B")
    user_a = make_user(db, email="a@test.local", org=org_a)
    site_b = make_site(db, org_b)
    cam_b = make_camera(db, site_b)
    snap_b = _make_snapshot(db, site_b, cam_b)

    resp = client.get(f"/api/snapshots/{snap_b.id}", headers=auth_headers(user_a))

    assert resp.status_code == 404


def test_admin_sees_any_org_snapshot(db: Session, client: TestClient):
    org = make_org(db)
    admin = make_user(db, email="root@test.local", is_admin=True)
    site = make_site(db, org)
    cam = make_camera(db, site)
    snap = _make_snapshot(db, site, cam)

    resp = client.get(f"/api/snapshots/{snap.id}", headers=auth_headers(admin))

    assert resp.status_code == 200


def test_missing_snapshot_is_404(db: Session, client: TestClient):
    org = make_org(db)
    user = make_user(db, email="u@test.local", org=org)

    resp = client.get("/api/snapshots/999", headers=auth_headers(user))

    assert resp.status_code == 404
