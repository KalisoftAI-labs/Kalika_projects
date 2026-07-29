from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "Kalika E-Commerce API"
    DEBUG: bool = True

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "ecom_fastapi_dev"
    DB_USER: str = "vikas"
    DB_PASSWORD: str = "kalika1667"

    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60

    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET_NAME: str = "kalika-ecom"

    GEMINI_API_KEY: str | None = None

    PUNCHOUT_SHARED_SECRET: str = "test-secret"
    PUNCHOUT_ANID: str = "AN01284122159-T"
    PUNCHOUT_SUPPLIER_DUNS: str = "651009354"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
