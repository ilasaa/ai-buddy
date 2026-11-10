from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    jwt_secret: str = ""
    session_minutes: int = Field(default=60, ge=1, le=1440)
    cookie_secure: bool = False
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    postgres_user: str
    postgres_password: str
    postgres_db: str

    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
