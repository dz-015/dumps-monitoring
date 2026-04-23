import datetime as dt
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(512), default="")
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="clean")  # clean | overflow | contamination
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    cameras = relationship("Camera", back_populates="site", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="site", cascade="all, delete-orphan")
    snapshots = relationship("Snapshot", back_populates="site", cascade="all, delete-orphan")


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    name: Mapped[str] = mapped_column(String(255))
    rtsp_url: Mapped[str] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    site = relationship("Site", back_populates="cameras")


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"))
    image_path: Mapped[str] = mapped_column(String(512))
    taken_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    site = relationship("Site", back_populates="snapshots")
    detections = relationship("Detection", back_populates="snapshot", cascade="all, delete-orphan")


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id"))
    class_name: Mapped[str] = mapped_column(String(50))  # metal_ok, metal_overflow, ..., ground_trash
    confidence: Mapped[float] = mapped_column(Float)
    x: Mapped[float] = mapped_column(Float)  # bbox coords normalized 0..1
    y: Mapped[float] = mapped_column(Float)
    w: Mapped[float] = mapped_column(Float)
    h: Mapped[float] = mapped_column(Float)

    snapshot = relationship("Snapshot", back_populates="detections")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("snapshots.id"), nullable=True)
    level: Mapped[str] = mapped_column(String(50))  # overflow | contamination
    status: Mapped[str] = mapped_column(String(50), default="new")  # new | accepted | resolved
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    site = relationship("Site", back_populates="alerts")
