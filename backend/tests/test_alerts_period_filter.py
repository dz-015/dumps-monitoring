"""Time-window filter on /api/alerts.

Operators sift the alerts list by recency: today / 7 days / 30 days / all
time. The endpoint accepts a `since` ISO datetime; alerts older than that
are excluded.
"""

import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Alert
from tests.conftest import auth_headers, make_org, make_site, make_user


def test_alerts_since_filter_excludes_older(db: Session, client: TestClient) -> None:
    org = make_org(db, "Org")
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org, "S")
    now = dt.datetime.now(dt.UTC).replace(microsecond=0)
    db.add_all([
        Alert(site_id=site.id, level="overflow", status="new", created_at=now),
        Alert(
            site_id=site.id,
            level="overflow",
            status="new",
            created_at=now - dt.timedelta(days=20),
        ),
    ])
    db.commit()

    # Use the Z-suffix form so the "+" in "+00:00" doesn't get URL-decoded as a space.
    cutoff = (now - dt.timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = client.get(
        f"/api/alerts?since={cutoff}",
        headers=auth_headers(user),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1


def test_alerts_no_since_returns_all(db: Session, client: TestClient) -> None:
    org = make_org(db, "Org")
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org, "S")
    now = dt.datetime.now(dt.UTC).replace(microsecond=0)
    db.add_all([
        Alert(site_id=site.id, level="overflow", status="new", created_at=now),
        Alert(
            site_id=site.id,
            level="overflow",
            status="new",
            created_at=now - dt.timedelta(days=200),
        ),
    ])
    db.commit()

    resp = client.get("/api/alerts", headers=auth_headers(user))

    assert resp.status_code == 200
    assert resp.json()["total"] == 2
