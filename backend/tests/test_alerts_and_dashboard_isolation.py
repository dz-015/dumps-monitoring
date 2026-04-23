"""Alerts and dashboard must also respect organization boundaries."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Alert
from tests.conftest import auth_headers, make_org, make_site, make_user


def test_user_sees_only_own_org_alerts(db: Session, client: TestClient) -> None:
    org_a = make_org(db, "OrgA")
    org_b = make_org(db, "OrgB")
    user_a = make_user(db, email="a@test.local", org=org_a)
    site_a = make_site(db, org_a, "A-site")
    site_b = make_site(db, org_b, "B-site")
    db.add_all(
        [
            Alert(site_id=site_a.id, level="overflow", status="new"),
            Alert(site_id=site_b.id, level="overflow", status="new"),
        ]
    )
    db.commit()

    resp = client.get("/api/alerts", headers=auth_headers(user_a))

    assert resp.status_code == 200, resp.text
    site_names = [a["site_name"] for a in resp.json()["items"]]
    assert "A-site" in site_names
    assert "B-site" not in site_names


def test_dashboard_counts_only_own_org(db: Session, client: TestClient) -> None:
    org_a = make_org(db, "OrgA")
    org_b = make_org(db, "OrgB")
    user_a = make_user(db, email="a@test.local", org=org_a)
    make_site(db, org_a, "A-site-1")
    make_site(db, org_a, "A-site-2")
    make_site(db, org_b, "B-site-1")
    make_site(db, org_b, "B-site-2")
    make_site(db, org_b, "B-site-3")

    resp = client.get("/api/dashboard/stats", headers=auth_headers(user_a))

    assert resp.status_code == 200
    assert resp.json()["total_sites"] == 2, "dashboard leaked org B's sites"


def test_admin_dashboard_sees_all(db: Session, client: TestClient) -> None:
    org_a = make_org(db, "OrgA")
    org_b = make_org(db, "OrgB")
    admin = make_user(db, email="root@test.local", org=None, is_admin=True)
    make_site(db, org_a, "A-site")
    make_site(db, org_b, "B-site")

    resp = client.get("/api/dashboard/stats", headers=auth_headers(admin))

    assert resp.status_code == 200
    assert resp.json()["total_sites"] == 2
