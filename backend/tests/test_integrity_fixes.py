"""Regression tests for data-integrity bugs.

BUG-06 — delete_site must remove detections (and not 500 under FK enforcement).
BUG-05 — delete_camera must not leave snapshots dangling.
BUG-16 — alert status PATCH must reject values outside new/accepted/resolved.
BUG-17/23 — dashboard status_counts/clean_percent must use the same
             alert-derived status as every other page.
"""

import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Alert, Camera, Detection, Site, Snapshot
from tests.conftest import auth_headers, make_camera, make_org, make_site, make_user


def _add_snapshot_with_detection(db: Session, site: Site, cam: Camera) -> Snapshot:
    snap = Snapshot(site_id=site.id, camera_id=cam.id, image_path="x.jpg")
    db.add(snap)
    db.flush()
    db.add(
        Detection(
            snapshot_id=snap.id, class_name="bin_overflow", confidence=0.9,
            x=0.5, y=0.5, w=0.1, h=0.1,
        )
    )
    db.commit()
    db.refresh(snap)
    return snap


class TestDeleteSite:
    def test_delete_site_with_detections_and_snapshot_alert(
        self, db: Session, client: TestClient
    ):
        org = make_org(db)
        user = make_user(db, email="u@test.local", org=org)
        site = make_site(db, org)
        cam = make_camera(db, site)
        snap = _add_snapshot_with_detection(db, site, cam)
        db.add(
            Alert(
                site_id=site.id, snapshot_id=snap.id, level="overflow", status="new",
                created_at=dt.datetime.now(dt.UTC),
            )
        )
        db.commit()

        resp = client.delete(f"/api/sites/{site.id}", headers=auth_headers(user))

        assert resp.status_code == 204
        assert db.query(Site).count() == 0
        assert db.query(Camera).count() == 0
        assert db.query(Snapshot).count() == 0
        assert db.query(Alert).count() == 0
        # The old bulk delete bypassed the ORM cascade and left these behind.
        assert db.query(Detection).count() == 0


class TestDeleteCamera:
    def test_delete_camera_removes_its_snapshots(self, db: Session, client: TestClient):
        org = make_org(db)
        user = make_user(db, email="u@test.local", org=org)
        site = make_site(db, org)
        cam = make_camera(db, site)
        _add_snapshot_with_detection(db, site, cam)

        resp = client.delete(f"/api/cameras/{cam.id}", headers=auth_headers(user))

        assert resp.status_code == 204
        assert db.query(Camera).count() == 0
        assert db.query(Snapshot).count() == 0
        assert db.query(Detection).count() == 0


class TestAlertStatusValidation:
    def test_arbitrary_status_rejected(self, db: Session, client: TestClient):
        org = make_org(db)
        user = make_user(db, email="u@test.local", org=org)
        site = make_site(db, org)
        alert = Alert(site_id=site.id, level="overflow", status="new")
        db.add(alert)
        db.commit()

        resp = client.patch(
            f"/api/alerts/{alert.id}",
            json={"status": "wontfix_lol"},
            headers=auth_headers(user),
        )

        assert resp.status_code == 422
        db.refresh(alert)
        assert alert.status == "new"


class TestDashboardDerivedStatus:
    def test_unresolved_overflow_counts_as_overflow(self, db: Session, client: TestClient):
        org = make_org(db)
        user = make_user(db, email="u@test.local", org=org)
        make_site(db, org, name="Clean")
        alerted_site = make_site(db, org, name="Alerted")  # status='clean' in DB
        db.add(Alert(site_id=alerted_site.id, level="overflow", status="new"))
        db.commit()

        stats = client.get("/api/dashboard/stats", headers=auth_headers(user)).json()

        assert stats["status_counts"]["overflow"] == 1
        assert stats["status_counts"]["clean"] == 1
        assert stats["clean_percent"] == 50.0
        # Consistency with the sites list (the page everyone else sees).
        sites = client.get("/api/sites", headers=auth_headers(user)).json()
        by_name = {s["name"]: s for s in sites}
        assert by_name["Alerted"]["active_status"] == "overflow"
        assert by_name["Clean"]["active_status"] == "clean"

    def test_resolving_returns_site_to_clean(self, db: Session, client: TestClient):
        org = make_org(db)
        user = make_user(db, email="u@test.local", org=org)
        site = make_site(db, org)
        db.add(Alert(site_id=site.id, level="contamination", status="resolved",
                     resolution_reason="false_alarm"))
        db.commit()

        stats = client.get("/api/dashboard/stats", headers=auth_headers(user)).json()

        assert stats["status_counts"]["contamination"] == 0
        assert stats["status_counts"]["clean"] == 1
        assert stats["clean_percent"] == 100.0
