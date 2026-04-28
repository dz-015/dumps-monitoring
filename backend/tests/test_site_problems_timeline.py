"""Per-site problems timeline endpoints feed the SiteDetailPage charts.

Mirrors `/api/dashboard/problems-week|month` but scoped to a single site,
so the operator can see how alert volume on this specific площадка trends.
"""
import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Alert
from tests.conftest import auth_headers, make_org, make_site, make_user


def test_problems_week_groups_alerts_by_day_for_one_site(
    db: Session, client: TestClient
) -> None:
    org = make_org(db, "OrgA")
    user = make_user(db, email="u@test.local", org=org)
    target = make_site(db, org, "Target")
    other = make_site(db, org, "Other")

    today = dt.datetime.now(dt.UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    db.add_all([
        Alert(site_id=target.id, level="overflow", status="new", created_at=today),
        Alert(site_id=target.id, level="overflow", status="new", created_at=today),
        Alert(
            site_id=target.id,
            level="contamination",
            status="new",
            created_at=today - dt.timedelta(days=2),
        ),
        Alert(site_id=other.id, level="overflow", status="new", created_at=today),
    ])
    db.commit()

    resp = client.get(
        f"/api/sites/{target.id}/problems-week", headers=auth_headers(user)
    )

    assert resp.status_code == 200
    rows = resp.json()
    counts_by_day = {r["day"]: r["count"] for r in rows}
    assert counts_by_day[str(today.date())] == 2
    assert counts_by_day[str((today - dt.timedelta(days=2)).date())] == 1
    # Other site's alert must not show up
    assert sum(r["count"] for r in rows) == 3


def test_problems_month_window_extends_back_31_days(
    db: Session, client: TestClient
) -> None:
    org = make_org(db, "OrgA")
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org, "S")
    today = dt.datetime.now(dt.UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    db.add_all([
        Alert(
            site_id=site.id,
            level="overflow",
            status="new",
            created_at=today - dt.timedelta(days=20),
        ),
        Alert(
            site_id=site.id,
            level="overflow",
            status="new",
            created_at=today - dt.timedelta(days=40),
        ),
    ])
    db.commit()

    week = client.get(f"/api/sites/{site.id}/problems-week", headers=auth_headers(user)).json()
    month = client.get(f"/api/sites/{site.id}/problems-month", headers=auth_headers(user)).json()

    assert sum(r["count"] for r in week) == 0
    assert sum(r["count"] for r in month) == 1


def test_problems_timeline_returns_404_for_other_org(
    db: Session, client: TestClient
) -> None:
    org_a = make_org(db, "A")
    org_b = make_org(db, "B")
    site_b = make_site(db, org_b, "B-site")
    user_a = make_user(db, email="a@test.local", org=org_a)

    resp = client.get(
        f"/api/sites/{site_b.id}/problems-week", headers=auth_headers(user_a)
    )

    assert resp.status_code == 404
