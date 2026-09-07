import json
import secrets
import warnings
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'nekobak.db'}"
    # Empty means "not configured". A fresh random key is generated per process
    # (see the validator below) — dev keeps working, but there is no committed
    # constant an attacker could use to forge JWTs. Set a real value in prod
    # (docker-compose already refuses to start without one); note that an
    # ephemeral key invalidates all sessions on every restart.
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    # Каталог, куда синк выкладывает кадры сборщика для часового контура
    # (app/scheduler.py). Обработанные уходят в processed/, битые — в failed/.
    INGEST_DIR: str = str(BASE_DIR / "ingest")
    # Origins allowed by CORS. Accepts either a JSON list
    # (`["https://a.example"]`) or a comma-separated string
    # (`https://a.example,https://b.example`). In dev the Vite proxy makes
    # everything same-origin so this only matters once we host the frontend
    # on a separate domain.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("SECRET_KEY", mode="after")
    @classmethod
    def _generate_secret_key_if_unset(cls, v: str) -> str:
        if v:
            return v
        warnings.warn(
            "SECRET_KEY is not set — generated an ephemeral random key. "
            "All tokens will be invalidated on restart. Set SECRET_KEY in .env "
            "for anything beyond local development.",
            stacklevel=2,
        )
        return secrets.token_hex(32)
    # Maximum size for any uploaded file (avatars, future snapshots) in bytes.
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024  # 5 MiB

    # ── ML ────────────────────────────────────────────────
    # Directory holding the exported *.onnx models (every file in it is loaded
    # as one ensemble member). ~130 MB each, so they are mounted, not baked
    # into the image. The default points at the dev checkout.
    ML_MODEL_DIR: str = str(BASE_DIR.parent / "ml" / "models" / "rtdetr_temporal_640")
    ML_ROI_CONFIG: str = str(BASE_DIR.parent / "ml" / "configs" / "cameras_roi_v2.json")
    # Deployable operating point from the thesis. Deliberately NOT the
    # threshold that maximises F1 in hindsight — that one peeks at the answers.
    ML_CONF_THRESHOLD: float = 0.25
    # How many ensemble members must agree before a detection is reported.
    ML_MIN_VOTES: int = 2

    # ── Уведомления: Telegram ─────────────────────────────
    # Токен от @BotFather. Пусто — бот и рассылка выключены, всё остальное
    # работает как раньше. Username бота (без @) нужен для deep-link
    # «Подключить» в профиле.
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BOT_USERNAME: str = ""
    # Прокси ТОЛЬКО для запросов к api.telegram.org (хостер прода режет
    # Telegram). Пример: http://172.20.0.1:10809 — socat-мост к ssh-туннелю.
    # Пусто — ходим напрямую.
    TELEGRAM_PROXY: str = ""

    # ── Уведомления: МАКС ─────────────────────────────────
    # Токен из кабинета dev.max.ru (выдаётся после модерации бота). Пусто —
    # канал выключен. Username — сгенерированный хендл бота (вида id<ИНН>_bot)
    # для deep-link «Подключить MAX» в профиле.
    # Синк кадров сборщика (app/s3_sync.py): бакет, куда пишет collector/.
    # Пустой endpoint = синк выключен (процесс спит, как боты без токена).
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_SNAPSHOTS_BUCKET: str = ""
    S3_REGION: str = "ru-central1"

    MAX_BOT_TOKEN: str = ""
    MAX_BOT_USERNAME: str = ""
    # База Bot API. Именно platform-api2: старый platform-api.max.ru мёртв
    # после миграции июля 2026.
    MAX_API_BASE: str = "https://platform-api2.max.ru"

    class Config:
        env_file = ".env"


settings = Settings()
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
