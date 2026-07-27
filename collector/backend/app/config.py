from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_user: str = "waste"
    postgres_password: str = "waste_dev_password"
    postgres_db: str = "waste_monitoring"

    # S3-compatible storage (MinIO local / Yandex Object Storage prod)
    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin_dev_password"
    s3_snapshots_bucket: str = "snapshots"
    s3_region: str = "ru-central1"

    # App
    debug: bool = True
    log_level: str = "info"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
