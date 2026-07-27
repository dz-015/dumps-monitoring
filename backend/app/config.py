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

    class Config:
        env_file = ".env"


settings = Settings()
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
