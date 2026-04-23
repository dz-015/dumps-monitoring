"""When an operator resolves an alert, they must say why.

Three allowed reasons:
- confirmed_and_cleared: real problem, crew dispatched, fixed.
- false_alarm: model was wrong; feeds future retraining.
- resolved_externally: problem went away on its own (truck came, wind cleared).

The field is required on transition to status=resolved. For other status changes
(new → accepted) it must be absent. Sending an invalid reason string returns 400.
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Alert
from tests.conftest import auth_headers, make_org, make_site, make_user


def _make_alert(db: Session, site_id: int) -> Alert:
    alert = Alert(site_id=site_id, level="overflow", status="new")
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def test_resolving_with_valid_reason_saves_it(db: Session, client: TestClient) -> None:
    org = make_org(db, "OrgA")
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org, "A-site")
    alert = _make_alert(db, site.id)

    resp = client.patch(
        f"/api/alerts/{alert.id}",
        headers=auth_headers(user),
        json={"status": "resolved", "resolution_reason": "confirmed_and_cleared"},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["resolution_reason"] == "confirmed_and_cleared"


def test_resolving_without_reason_is_rejected(db: Session, client: TestClient) -> None:
    org = make_org(db, "OrgA")
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org, "A-site")
    alert = _make_alert(db, site.id)

    resp = client.patch(
        f"/api/alerts/{alert.id}",
        headers=auth_headers(user),
        json={"status": "resolved"},
    )

    assert resp.status_code == 400


def test_resolving_with_invalid_reason_is_rejected(db: Session, client: TestClient) -> None:
    org = make_org(db, "OrgA")
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org, "A-site")
    alert = _make_alert(db, site.id)

    resp = client.patch(
        f"/api/alerts/{alert.id}",
        headers=auth_headers(user),
        json={"status": "resolved", "resolution_reason": "made_it_up"},
    )

    assert resp.status_code == 400


def test_accepting_alert_without_reason_is_ok(db: Session, client: TestClient) -> None:
    org = make_org(db, "OrgA")
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org, "A-site")
    alert = _make_alert(db, site.id)

    resp = client.patch(
        f"/api/alerts/{alert.id}",
        headers=auth_headers(user),
        json={"status": "accepted"},
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    assert resp.json()["resolution_reason"] is None


def test_accepting_with_reason_is_rejected(db: Session, client: TestClient) -> None:
    """resolution_reason belongs to resolved, not accepted."""
    org = make_org(db, "OrgA")
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org, "A-site")
    alert = _make_alert(db, site.id)

    resp = client.patch(
        f"/api/alerts/{alert.id}",
        headers=auth_headers(user),
        json={"status": "accepted", "resolution_reason": "false_alarm"},
    )

    assert resp.status_code == 400


def test_false_alarm_reason_is_accepted(db: Session, client: TestClient) -> None:
    org = make_org(db, "OrgA")
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org, "A-site")
    alert = _make_alert(db, site.id)

    resp = client.patch(
        f"/api/alerts/{alert.id}",
        headers=auth_headers(user),
        json={"status": "resolved", "resolution_reason": "false_alarm"},
    )

    assert resp.status_code == 200
    assert resp.json()["resolution_reason"] == "false_alarm"


def test_resolved_externally_reason_is_accepted(db: Session, client: TestClient) -> None:
    org = make_org(db, "OrgA")
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org, "A-site")
    alert = _make_alert(db, site.id)

    resp = client.patch(
        f"/api/alerts/{alert.id}",
        headers=auth_headers(user),
        json={"status": "resolved", "resolution_reason": "resolved_externally"},
    )

    assert resp.status_code == 200
    assert resp.json()["resolution_reason"] == "resolved_externally"
