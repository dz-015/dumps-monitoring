from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def _connect_args_for(database_url: str) -> dict:
    """check_same_thread is a sqlite3-only kwarg — psycopg2 and friends reject it."""
    if make_url(database_url).get_backend_name() == "sqlite":
        return {"check_same_thread": False}
    return {}


def make_engine(database_url: str) -> Engine:
    """Engine factory shared by prod and tests.

    SQLite ships with foreign-key enforcement OFF; without the pragma the
    deployed app silently accepts dangling references that the test engine
    (which always enabled it) would reject.
    """
    engine = create_engine(database_url, connect_args=_connect_args_for(database_url))
    if make_url(database_url).get_backend_name() == "sqlite":

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _record):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


engine = make_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
