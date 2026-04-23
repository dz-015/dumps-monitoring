"""
Shared test fixtures: in-memory SQLite per test, overridden get_db dependency,
factories for Organization / User / Site / Camera.

Each test gets a clean DB — no cross-test bleed.
"""
from __future__ import annotations

import secrets
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import create_access_token, hash_password
from app.db.database import Base, get_db
from app.db.models import Camera, Organization, Site, User
from app.main import app


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    def _override_get_db():
        try:
            yield db
        finally:
            pass  # fixture owns the session lifecycle

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def make_org(db: Session, name: str = "TestOrg") -> Organization:
    org = Organization(name=name, join_code=secrets.token_urlsafe(8))
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def make_user(
    db: Session,
    *,
    email: str,
    org: Organization | None = None,
    is_admin: bool = False,
    password: str = "pw12345678",
) -> User:
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=email.split("@")[0],
        is_active=True,
        is_admin=is_admin,
        organization_id=org.id if org else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_site(db: Session, org: Organization, name: str = "Site") -> Site:
    site = Site(organization_id=org.id, name=name, address=f"{name} address")
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


def make_camera(db: Session, site: Site, name: str = "Cam") -> Camera:
    cam = Camera(site_id=site.id, name=name, rtsp_url="rtsp://example/stream")
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}
