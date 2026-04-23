"""
Organization-scoped isolation: user from org A must never see resources from org B.

This is the single most important security-relevant invariant in the backend —
every list endpoint must filter by current_user.organization_id, every detail
endpoint must 404 for out-of-org ids.
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import auth_headers, make_camera, make_org, make_site, make_user


def test_user_sees_only_own_org_sites(db: Session, client: TestClient) -> None:
    org_a = make_org(db, "OrgA")
    org_b = make_org(db, "OrgB")
    user_a = make_user(db, email="a@test.local", org=org_a)
    make_site(db, org_a, "A-site")
    make_site(db, org_b, "B-site")

    resp = client.get("/api/sites", headers=auth_headers(user_a))

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    names = [s["name"] for s in payload]
    assert "A-site" in names
    assert "B-site" not in names, "cross-org leak: user A saw B's site"


def test_user_cannot_fetch_foreign_site_detail(db: Session, client: TestClient) -> None:
    org_a = make_org(db, "OrgA")
    org_b = make_org(db, "OrgB")
    user_a = make_user(db, email="a@test.local", org=org_a)
    foreign_site = make_site(db, org_b, "B-site")

    resp = client.get(f"/api/sites/{foreign_site.id}", headers=auth_headers(user_a))

    assert resp.status_code == 404


def test_user_sees_only_own_org_cameras(db: Session, client: TestClient) -> None:
    org_a = make_org(db, "OrgA")
    org_b = make_org(db, "OrgB")
    user_a = make_user(db, email="a@test.local", org=org_a)
    site_a = make_site(db, org_a, "A-site")
    site_b = make_site(db, org_b, "B-site")
    make_camera(db, site_a, "A-cam")
    make_camera(db, site_b, "B-cam")

    resp = client.get("/api/cameras", headers=auth_headers(user_a))

    assert resp.status_code == 200, resp.text
    names = [c["name"] for c in resp.json()]
    assert "A-cam" in names
    assert "B-cam" not in names, "cross-org leak: user A saw B's camera"


def test_admin_sees_all_orgs_sites(db: Session, client: TestClient) -> None:
    org_a = make_org(db, "OrgA")
    org_b = make_org(db, "OrgB")
    admin = make_user(db, email="admin@test.local", org=None, is_admin=True)
    make_site(db, org_a, "A-site")
    make_site(db, org_b, "B-site")

    resp = client.get("/api/sites", headers=auth_headers(admin))

    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    assert "A-site" in names and "B-site" in names
