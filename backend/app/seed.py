"""Seed the DB with demo data for development.

Run: `python -m app.seed` from `backend/` (after `alembic upgrade head`).
Idempotent — re-running is a no-op if any User already exists.

Passwords come from SEED_ADMIN_PASSWORD / SEED_DEMO_PASSWORD env vars; when
unset, a random password is generated and printed ONCE to stdout. Never
hardcode credentials here — the repo is public (BUG-02/07/08).
"""

import datetime as dt
import os
import random
import secrets

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.db.database import SessionLocal
from app.db.models import Alert, Camera, Organization, Site, User

SITES_DATA = [
    {
        "name": "Площадка Москольцо",
        "address": "ул. Москольцо, 15, Симферополь",
        "latitude": 44.952,
        "longitude": 34.102,
    },
    {
        "name": "Площадка Центральный Рынок",
        "address": "ул. Кирова, 2, Симферополь",
        "latitude": 44.949,
        "longitude": 34.098,
    },
    {
        "name": "Площадка Парк Гагарина",
        "address": "ул. Гагарина, 50, Симферополь",
        "latitude": 44.940,
        "longitude": 34.110,
    },
    {
        "name": "Площадка Марьино",
        "address": "ул. Марьинская, 8, Симферополь",
        "latitude": 44.958,
        "longitude": 34.120,
    },
    {
        "name": "Площадка ЦУМ",
        "address": "ул. Карла Маркса, 12, Симферополь",
        "latitude": 44.951,
        "longitude": 34.100,
    },
    {
        "name": "Площадка Ак-Мечеть",
        "address": "ул. Ак-Мечетская, 3, Симферополь",
        "latitude": 44.945,
        "longitude": 34.085,
    },
    {
        "name": "Площадка Каменка",
        "address": "ул. Каменская, 22, Симферополь",
        "latitude": 44.935,
        "longitude": 34.095,
    },
    {
        "name": "Площадка Залесская",
        "address": "ул. Залесская, 7, Симферополь",
        "latitude": 44.960,
        "longitude": 34.115,
    },
]

STATUSES = ["clean", "clean", "clean", "clean", "overflow", "contamination", "clean", "overflow"]


def _seed_password(env_var: str, account: str) -> str:
    """Password from env, or a random one printed once so the operator can log in."""
    pw = os.environ.get(env_var)
    if pw:
        return pw
    pw = secrets.token_urlsafe(12)
    print(f"{env_var} not set — generated password for {account}: {pw}")
    return pw


def seed_db(db: Session) -> None:
    if db.query(User).first():
        return

    demo_org = Organization(name="НЭКОБАК — демо", join_code=secrets.token_urlsafe(8))
    db.add(demo_org)
    db.flush()

    admin = User(
        email="admin@nekobak.ru",
        hashed_password=hash_password(_seed_password("SEED_ADMIN_PASSWORD", "admin@nekobak.ru")),
        full_name="Администратор",
        is_admin=True,
        organization_id=None,
    )
    demo_user = User(
        email="demo@nekobak.ru",
        hashed_password=hash_password(_seed_password("SEED_DEMO_PASSWORD", "demo@nekobak.ru")),
        full_name="Иван Иванович",
        organization_id=demo_org.id,
    )
    db.add_all([admin, demo_user])
    db.flush()

    for i, site_data in enumerate(SITES_DATA):
        site = Site(organization_id=demo_org.id, **site_data, status=STATUSES[i])
        db.add(site)
        db.flush()

        for j in range(random.randint(1, 3)):
            db.add(
                Camera(
                    site_id=site.id,
                    name=f"Камера {j + 1}",
                    rtsp_url=f"rtsp://admin:pass@192.168.{i}.{j + 10}:554/stream",
                    is_active=True,
                    last_checked=dt.datetime.now(dt.UTC)
                    - dt.timedelta(minutes=random.randint(5, 120)),
                )
            )

        for _ in range(random.randint(0, 8)):
            days_ago = random.randint(0, 30)
            status = random.choice(["new", "accepted", "resolved"])
            db.add(
                Alert(
                    site_id=site.id,
                    level=random.choice(["overflow", "contamination"]),
                    status=status,
                    created_at=dt.datetime.now(dt.UTC)
                    - dt.timedelta(days=days_ago, hours=random.randint(0, 23)),
                    resolved_at=(
                        dt.datetime.now(dt.UTC) - dt.timedelta(days=max(days_ago - 1, 0))
                        if status == "resolved"
                        else None
                    ),
                )
            )

    db.commit()
    print(
        f"Seeded: org '{demo_org.name}' (join_code={demo_org.join_code}), admin + demo user, {len(SITES_DATA)} sites."
    )


if __name__ == "__main__":
    with SessionLocal() as session:
        seed_db(session)
