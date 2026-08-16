from __future__ import annotations

import base64
import json
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    app_name: str = "Token Station"
    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./token_station.db"
    redis_url: str = ""
    secret_key: str = "development-secret-change-before-production-000000"
    token_encryption_key: str = ""
    token_encryption_key_version: int = 1
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str = "DevelopmentOnly!123"
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    secure_cookies: bool = False
    session_hours: int = 12
    auto_create_tables: bool = True
    allow_private_upstreams: bool = False
    max_request_bytes: int = 2 * 1024 * 1024
    log_retention_days: int = 90
    frontend_dist: str = "frontend/dist"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                return json.loads(value)
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def frontend_path(self) -> Path:
        return Path(self.frontend_dist).resolve()

    def encryption_key_bytes(self) -> bytes:
        if not self.token_encryption_key:
            if self.is_production:
                raise ValueError("TOKEN_ENCRYPTION_KEY is required in production")
            return b"development-token-key-32-bytes!!"
        try:
            raw = base64.urlsafe_b64decode(self.token_encryption_key.encode())
        except Exception as exc:
            raise ValueError("TOKEN_ENCRYPTION_KEY must be URL-safe base64") from exc
        if len(raw) != 32:
            raise ValueError("TOKEN_ENCRYPTION_KEY must decode to exactly 32 bytes")
        return raw

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.is_production:
            weak_values = {
                "replace-with-a-long-random-secret",
                "development-secret-change-before-production-000000",
            }
            if len(self.secret_key) < 32 or self.secret_key in weak_values:
                raise ValueError("SECRET_KEY must be a non-default value of at least 32 characters")
            if (
                "replace" in self.bootstrap_admin_password.lower()
                or len(self.bootstrap_admin_password) < 12
            ):
                raise ValueError("BOOTSTRAP_ADMIN_PASSWORD must be a strong non-default password")
            self.encryption_key_bytes()
            if not self.secure_cookies:
                raise ValueError("SECURE_COOKIES must be true in production")
            if self.auto_create_tables:
                raise ValueError("AUTO_CREATE_TABLES must be false in production; use Alembic")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
