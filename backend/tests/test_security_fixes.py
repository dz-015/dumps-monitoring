"""Regression tests for security bugs.

BUG-02/07/08 — seed must not create accounts with publicly-known passwords.
BUG-04 — unset SECRET_KEY must not silently fall back to the committed constant.
BUG-32 — is_active=False must actually lock the user out (login AND token).
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import User
from app.seed import seed_db
from tests.conftest import auth_headers, make_org, make_user

OLD_COMMITTED_DEFAULT = "dev-secret-change-in-production-abc123"


class TestSecretKey:
    def test_unset_secret_key_is_not_the_committed_constant(self, monkeypatch):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        s = Settings(_env_file=None)
        assert s.SECRET_KEY != OLD_COMMITTED_DEFAULT
        assert len(s.SECRET_KEY) >= 32

    def test_unset_secret_key_is_random_per_process_not_a_constant(self, monkeypatch):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        a = Settings(_env_file=None)
        b = Settings(_env_file=None)
        # Two fresh generations must differ — proves nobody can precompute it.
        assert a.SECRET_KEY != b.SECRET_KEY

    def test_explicit_secret_key_still_respected(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "x" * 64)
        assert Settings(_env_file=None).SECRET_KEY == "x" * 64


class TestSeedPasswords:
    def test_seed_respects_env_passwords(self, db: Session, monkeypatch):
        monkeypatch.setenv("SEED_ADMIN_PASSWORD", "strong-admin-pw")
        monkeypatch.setenv("SEED_DEMO_PASSWORD", "strong-demo-pw")
        seed_db(db)

        from app.auth import verify_password

        admin = db.query(User).filter(User.email == "admin@nekobak.ru").one()
        demo = db.query(User).filter(User.email == "demo@nekobak.ru").one()
        assert verify_password("strong-admin-pw", admin.hashed_password)
        assert verify_password("strong-demo-pw", demo.hashed_password)

    def test_seed_without_env_does_not_use_known_passwords(self, db: Session, monkeypatch):
        monkeypatch.delenv("SEED_ADMIN_PASSWORD", raising=False)
        monkeypatch.delenv("SEED_DEMO_PASSWORD", raising=False)
        seed_db(db)

        from app.auth import verify_password

        admin = db.query(User).filter(User.email == "admin@nekobak.ru").one()
        demo = db.query(User).filter(User.email == "demo@nekobak.ru").one()
        assert not verify_password("admin123", admin.hashed_password)
        assert not verify_password("demo1234", demo.hashed_password)


class TestIsActiveEnforced:
    def test_login_rejected_for_deactivated_user(self, db: Session, client: TestClient):
        org = make_org(db)
        user = make_user(db, email="gone@test.local", org=org, password="pw12345678")
        user.is_active = False
        db.commit()

        resp = client.post(
            "/api/auth/login",
            json={"email": "gone@test.local", "password": "pw12345678"},
        )
        assert resp.status_code == 403

    def test_existing_token_rejected_after_deactivation(
        self, db: Session, client: TestClient
    ):
        org = make_org(db)
        user = make_user(db, email="gone@test.local", org=org)
        headers = auth_headers(user)  # token issued while active

        user.is_active = False
        db.commit()

        resp = client.get("/api/auth/me", headers=headers)
        assert resp.status_code == 403
