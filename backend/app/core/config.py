from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    llm_api_key: SecretStr = SecretStr("")
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = ""
    deepseek_api_key: SecretStr = SecretStr("")
    deepseek_model: str = "deepseek-flash"
    llm_max_tokens: int = Field(default=1000, ge=64, le=1200)
    llm_timeout_seconds: float = Field(default=45, ge=1, le=120)
    chat_max_message_chars: int = Field(default=3000, ge=100, le=10000)
    chat_history_messages: int = Field(default=8, ge=0, le=20)
    chat_history_chars: int = Field(default=12000, ge=1000, le=30000)
    chat_daily_limit: int = Field(default=30, ge=1, le=500)
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_cache_dir: str = str(BASE_DIR / ".cache" / "huggingface")
    embedding_local_only: bool = True
    rag_top_k: int = Field(default=5, ge=1, le=10)
    rag_min_score: float | None = Field(default=None, ge=-1, le=1)
    rag_context_chars: int = Field(default=8000, ge=500, le=15000)

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
