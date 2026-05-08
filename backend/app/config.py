from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'nekobak.db'}"
    SECRET_KEY: str = "dev-secret-change-in-production-abc123"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    # Comma-separated list of origins allowed by CORS. In dev the Vite proxy
    # makes everything same-origin so this only matters once we host the
    # frontend on a separate domain.
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    # Maximum size for any uploaded file (avatars, future snapshots) in bytes.
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024  # 5 MiB

    class Config:
        env_file = ".env"


settings = Settings()
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
