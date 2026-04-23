"""Seed the DB with demo data for development."""
import datetime as dt
import random
from sqlalchemy.orm import Session
from app.db.models import User, Site, Camera, Alert
from app.auth import hash_password

SITES_DATA = [
    {"name": "Площадка Москольцо", "address": "ул. Москольцо, 15, Симферополь", "latitude": 44.952, "longitude": 34.102},
    {"name": "Площадка Центральный Рынок", "address": "ул. Кирова, 2, Симферополь", "latitude": 44.949, "longitude": 34.098},
    {"name": "Площадка Парк Гагарина", "address": "ул. Гагарина, 50, Симферополь", "latitude": 44.940, "longitude": 34.110},
    {"name": "Площадка Марьино", "address": "ул. Марьинская, 8, Симферополь", "latitude": 44.958, "longitude": 34.120},
    {"name": "Площадка ЦУМ", "address": "ул. Карла Маркса, 12, Симферополь", "latitude": 44.951, "longitude": 34.100},
    {"name": "Площадка Ак-Мечеть", "address": "ул. Ак-Мечетская, 3, Симферополь", "latitude": 44.945, "longitude": 34.085},
    {"name": "Площадка Каменка", "address": "ул. Каменская, 22, Симферополь", "latitude": 44.935, "longitude": 34.095},
    {"name": "Площадка Залесская", "address": "ул. Залесская, 7, Симферополь", "latitude": 44.960, "longitude": 34.115},
]

STATUSES = ["clean", "clean", "clean", "clean", "overflow", "contamination", "clean", "overflow"]


def seed_db(db: Session):
    # Check if already seeded
    if db.query(User).first():
        return

    # Create demo user
    user = User(
        email="admin@nekobak.ru",
        hashed_password=hash_password("admin123"),
        full_name="Иван Иванович",
    )
    db.add(user)
    db.flush()

    # Create sites
    for i, site_data in enumerate(SITES_DATA):
        site = Site(**site_data, status=STATUSES[i])
        db.add(site)
        db.flush()

        # 1-3 cameras per site
        num_cams = random.randint(1, 3)
        for j in range(num_cams):
            cam = Camera(
                site_id=site.id,
                name=f"Камера {j + 1}",
                rtsp_url=f"rtsp://admin:pass@192.168.{i}.{j + 10}:554/stream",
                is_active=True,
                last_checked=dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=random.randint(5, 120)),
            )
            db.add(cam)

        # Some alerts
        num_alerts = random.randint(0, 8)
        for k in range(num_alerts):
            days_ago = random.randint(0, 30)
            level = random.choice(["overflow", "contamination"])
            status = random.choice(["new", "accepted", "resolved"])
            alert = Alert(
                site_id=site.id,
                level=level,
                status=status,
                created_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_ago, hours=random.randint(0, 23)),
                resolved_at=(
                    dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_ago - 1)
                    if status == "resolved" else None
                ),
            )
            db.add(alert)

    db.commit()
    print("Database seeded with demo data.")
