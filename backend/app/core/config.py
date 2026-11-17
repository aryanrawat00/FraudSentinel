from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_env: Literal["development", "test", "production"] = "development"
    demo_mode: bool = False
    postgres_host: str = "127.0.0.1"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = "fraudsentinel"
    postgres_user: str = "fraudsentinel"
    postgres_password: SecretStr = SecretStr("")
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @model_validator(mode="after")
    def validate_production(self):
        if self.app_env == "production":
            if self.demo_mode:
                raise ValueError("DEMO_MODE must be disabled in production")
            if not self.postgres_password.get_secret_value().strip():
                raise ValueError("POSTGRES_PASSWORD is required in production")
            if "*" in self.cors_origins:
                raise ValueError("Production CORS origins must be explicit")
        return self

    @property
    def database_url(self) -> URL:
        # Build a URL object so passwords containing @, $, or : need no escaping.
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )
