"""Registration flow creates or joins an organization atomically."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Organization, User
from tests.conftest import make_org


def test_register_creates_new_organization(db: Session, client: TestClient) -> None:
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "first@test.local",
            "password": "pw12345678",
            "full_name": "First User",
            "organization_name": "Acme Waste Co",
        },
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "first@test.local"
    assert body["organization_id"] is not None

    org = db.query(Organization).filter(Organization.name == "Acme Waste Co").one()
    assert body["organization_id"] == org.id
    assert org.join_code, "join_code must be auto-generated"

    user = db.query(User).filter(User.email == "first@test.local").one()
    assert user.organization_id == org.id
    assert user.is_admin is False


def test_register_joins_existing_organization(db: Session, client: TestClient) -> None:
    existing = make_org(db, "Existing Co")

    resp = client.post(
        "/api/auth/register",
        json={
            "email": "joiner@test.local",
            "password": "pw12345678",
            "full_name": "Joiner",
            "join_code": existing.join_code,
        },
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["organization_id"] == existing.id

    user = db.query(User).filter(User.email == "joiner@test.local").one()
    assert user.organization_id == existing.id


def test_register_rejects_bad_join_code(db: Session, client: TestClient) -> None:
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "bad@test.local",
            "password": "pw12345678",
            "full_name": "Bad",
            "join_code": "no-such-code",
        },
    )
    assert resp.status_code == 400


def test_register_requires_one_of_org_name_or_join_code(db: Session, client: TestClient) -> None:
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "noone@test.local",
            "password": "pw12345678",
            "full_name": "Noone",
        },
    )
    assert resp.status_code == 400


def test_register_rejects_both_org_name_and_join_code(db: Session, client: TestClient) -> None:
    existing = make_org(db, "Existing Co")
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "both@test.local",
            "password": "pw12345678",
            "full_name": "Both",
            "organization_name": "New Co",
            "join_code": existing.join_code,
        },
    )
    assert resp.status_code == 400
