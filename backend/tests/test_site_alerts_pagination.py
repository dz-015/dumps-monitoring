"""BUG-40 — site alert history must be server-paginated with a real total,
not silently truncated to the first 50 rows."""

import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Alert
from tests.conftest import auth_headers, make_org, make_site, make_user


def _add_alerts(db: Session, site_id: int, n: int) -> None:
    now = dt.datetime.now(dt.UTC)
    db.add_all(
        Alert(
            site_id=site_id,
            level="overflow",
            status="new",
            created_at=now - dt.timedelta(hours=i),
        )
        for i in range(n)
    )
    db.commit()


def test_total_reflects_full_history_beyond_old_50_cap(
    db: Session, client: TestClient
) -> None:
    org = make_org(db)
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org)
    _add_alerts(db, site.id, 60)

    resp = client.get(f"/api/sites/{site.id}/alerts", headers=auth_headers(user))

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 60
    assert len(body["items"]) == 10  # default page size


def test_pages_are_disjoint_and_ordered_newest_first(
    db: Session, client: TestClient
) -> None:
    org = make_org(db)
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org)
    _add_alerts(db, site.id, 25)

    p1 = client.get(
        f"/api/sites/{site.id}/alerts?page=1&per_page=10", headers=auth_headers(user)
    ).json()
    p3 = client.get(
        f"/api/sites/{site.id}/alerts?page=3&per_page=10", headers=auth_headers(user)
    ).json()

    assert len(p1["items"]) == 10
    assert len(p3["items"]) == 5
    ids_p1 = {a["id"] for a in p1["items"]}
    ids_p3 = {a["id"] for a in p3["items"]}
    assert not ids_p1 & ids_p3
    created = [a["created_at"] for a in p1["items"]]
    assert created == sorted(created, reverse=True)
