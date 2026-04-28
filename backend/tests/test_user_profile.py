"""Profile editing — change full_name + upload avatar.

Lives at /api/auth/me (PATCH) and /api/auth/avatar (POST). User-scoped:
authenticated user can only edit their own profile, no admin override needed
because users only ever edit themselves.
"""

import io

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import User
from tests.conftest import auth_headers, make_org, make_user


def test_patch_me_updates_full_name(db: Session, client: TestClient) -> None:
    org = make_org(db, "Org")
    user = make_user(db, email="u@test.local", org=org)

    resp = client.patch(
        "/api/auth/me",
        json={"full_name": "Иван Иванов"},
        headers=auth_headers(user),
    )

    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Иван Иванов"
    db.refresh(user)
    assert user.full_name == "Иван Иванов"


def test_me_endpoint_returns_avatar_path_field(db: Session, client: TestClient) -> None:
    org = make_org(db, "Org")
    user = make_user(db, email="u@test.local", org=org)

    resp = client.get("/api/auth/me", headers=auth_headers(user))

    assert resp.status_code == 200
    body = resp.json()
    # Field should always be present (even when null) so the frontend can rely on it.
    assert "avatar_path" in body
    assert body["avatar_path"] is None


def test_post_avatar_stores_file_and_sets_avatar_path(
    db: Session, client: TestClient
) -> None:
    org = make_org(db, "Org")
    user = make_user(db, email="u@test.local", org=org)

    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64

    resp = client.post(
        "/api/auth/avatar",
        files={"file": ("avatar.png", io.BytesIO(fake_png), "image/png")},
        headers=auth_headers(user),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["avatar_path"] is not None
    assert body["avatar_path"].startswith("avatars/")

    db.refresh(user)
    assert user.avatar_path == body["avatar_path"]


def test_post_avatar_rejects_non_image_content_type(
    db: Session, client: TestClient
) -> None:
    org = make_org(db, "Org")
    user = make_user(db, email="u@test.local", org=org)

    resp = client.post(
        "/api/auth/avatar",
        files={"file": ("evil.txt", io.BytesIO(b"not an image"), "text/plain")},
        headers=auth_headers(user),
    )

    assert resp.status_code == 400
