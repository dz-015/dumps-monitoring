"""Regression tests for deploy/config bugs.

BUG-14 — CORS_ORIGINS: comma-separated value (documented format) must parse,
          not crash the app at import time.
BUG-15 — production SQLite engine must enforce foreign keys (tests always did,
          prod never — behaviour diverged).
BUG-33 — sqlite-only connect_args must not be passed to non-SQLite backends.
"""

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db.database import Base, _connect_args_for, make_engine


class TestCorsOriginsParsing:
    def test_json_list_still_works(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", '["https://a.example"]')
        assert Settings().CORS_ORIGINS == ["https://a.example"]

    def test_comma_separated(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "https://a.example,https://b.example")
        assert Settings().CORS_ORIGINS == ["https://a.example", "https://b.example"]

    def test_single_bare_origin(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "https://nekobak.example.com")
        assert Settings().CORS_ORIGINS == ["https://nekobak.example.com"]

    def test_whitespace_and_trailing_comma_tolerated(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", " https://a.example , https://b.example ,")
        assert Settings().CORS_ORIGINS == ["https://a.example", "https://b.example"]


class TestEngineFactory:
    def test_sqlite_gets_check_same_thread(self):
        assert _connect_args_for("sqlite:///x.db") == {"check_same_thread": False}

    def test_postgres_gets_no_sqlite_args(self):
        # BUG-33: psycopg2 rejects check_same_thread at connect time.
        assert _connect_args_for("postgresql+psycopg2://u:p@host/db") == {}

    def test_sqlite_fk_pragma_enabled(self):
        engine = make_engine("sqlite://")
        with engine.connect() as conn:
            assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1

    def test_sqlite_fk_violation_raises(self):
        # BUG-15: prod engine silently accepted dangling FKs.
        engine = make_engine("sqlite://")
        Base.metadata.create_all(engine)
        with engine.connect() as conn:
            try:
                conn.execute(
                    text(
                        "INSERT INTO cameras (site_id, name, rtsp_url, is_active)"
                        " VALUES (999, 'cam', 'rtsp://x', 1)"
                    )
                )
                conn.commit()
                raised = False
            except IntegrityError:
                raised = True
        assert raised, "FK violation must raise IntegrityError on the prod engine"
