import datetime as dt

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    join_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    users = relationship("User", back_populates="organization")
    sites = relationship("Site", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    avatar_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Telegram chat_id, записывается ботом при /start по deep-link (бот не может
    # написать первым по хэндлу — только так). BigInteger: chat_id > 2^31.
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # user_id в МАКС, записывается ботом по событию bot_started с payload
    # deep-link (личка в МАКС адресуется по user_id, а не chat_id).
    max_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    organization = relationship("Organization", back_populates="users")

    @property
    def telegram_connected(self) -> bool:
        return self.telegram_chat_id is not None

    @property
    def max_connected(self) -> bool:
        return self.max_user_id is not None


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(512), default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="clean"
    )  # clean | overflow | contamination
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    organization = relationship("Organization", back_populates="sites")
    cameras = relationship("Camera", back_populates="site", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="site", cascade="all, delete-orphan")
    snapshots = relationship("Snapshot", back_populates="site", cascade="all, delete-orphan")


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    rtsp_url: Mapped[str] = mapped_column(String(512))
    # Ключ камеры у сборщика: "2" для кадров cam2_*.jpg. По нему планировщик
    # находит камеру для кадра, а пайплайн — её ROI в cameras_roi_v2.json.
    external_key: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    # Имя потока на платформе Flussonic Watcher (источник кадров вместо RTSP).
    # В имени потока есть точки и дефисы, поэтому в именах файлов кадров
    # используется короткий external_key, а не оно.
    watcher_stream: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    site = relationship("Site", back_populates="cameras")
    # Snapshots die with their camera — without this, deleting a camera leaves
    # snapshot rows with a dangling camera_id (or 500s under FK enforcement).
    snapshots = relationship(
        "Snapshot", back_populates="camera", cascade="all, delete-orphan"
    )


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"))
    image_path: Mapped[str] = mapped_column(String(512))
    taken_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    site = relationship("Site", back_populates="snapshots")
    camera = relationship("Camera", back_populates="snapshots")
    detections = relationship("Detection", back_populates="snapshot", cascade="all, delete-orphan")


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id"))
    class_name: Mapped[str] = mapped_column(
        String(50)
    )  # bin_ok | bin_overflow | ground_trash (модель материал бака не различает)
    confidence: Mapped[float] = mapped_column(Float)
    x: Mapped[float] = mapped_column(Float)  # normalized 0..1
    y: Mapped[float] = mapped_column(Float)
    w: Mapped[float] = mapped_column(Float)
    h: Mapped[float] = mapped_column(Float)

    snapshot = relationship("Snapshot", back_populates="detections")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("snapshots.id"), nullable=True)
    level: Mapped[str] = mapped_column(String(50))  # overflow | contamination
    status: Mapped[str] = mapped_column(String(50), default="new")  # new | accepted | resolved
    # Set only when status=resolved. Feeds operator-feedback loop (decisions log, 2026-04-23).
    resolution_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    site = relationship("Site", back_populates="alerts")
