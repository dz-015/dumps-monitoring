"""BUG-09 — timestamps must be serialized with an explicit UTC offset.

The DB stores naive-UTC datetimes; without a marker the browser parses them
as LOCAL time and every displayed timestamp shifts by the user's UTC offset.
"""

import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Alert
from tests.conftest import auth_headers, make_camera, make_org, make_site, make_user

# ISO datetime ending in Z or ±HH:MM
AWARE_RE = re.compile(r"(Z|[+-]\d{2}:\d{2})$")


def test_alert_timestamps_are_timezone_aware(db: Session, client: TestClient):
    org = make_org(db)
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org)
    db.add(Alert(site_id=site.id, level="overflow", status="new"))
    db.commit()

    items = client.get("/api/alerts", headers=auth_headers(user)).json()["items"]
    assert AWARE_RE.search(items[0]["created_at"]), items[0]["created_at"]

    site_alerts = client.get(
        f"/api/sites/{site.id}/alerts", headers=auth_headers(user)
    ).json()
    assert AWARE_RE.search(site_alerts["items"][0]["created_at"])


def test_site_and_camera_timestamps_are_timezone_aware(db: Session, client: TestClient):
    org = make_org(db)
    user = make_user(db, email="u@test.local", org=org)
    site = make_site(db, org)
    make_camera(db, site)

    sites = client.get("/api/sites", headers=auth_headers(user)).json()
    assert AWARE_RE.search(sites[0]["created_at"])

    cams = client.get("/api/cameras", headers=auth_headers(user)).json()
    assert AWARE_RE.search(cams[0]["created_at"])
