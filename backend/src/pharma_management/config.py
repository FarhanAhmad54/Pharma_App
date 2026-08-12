from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Pharma Management API"
    app_version: str = "1.0.0"
    environment: str = "development"
    database_url: str = ""
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout: int = 30
    database_statement_timeout_ms: int = 30000
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]
    enable_docs: bool = True
    security_headers: bool = True
    trusted_hosts: list[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("cors_origins", "trusted_hosts", mode="before")
    @classmethod
    def parse_lists(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_required_runtime_settings(self) -> "Settings":
        if self.environment != "testing":
            if not self.database_url or not self.jwt_secret:
                raise ValueError("DATABASE_URL and JWT_SECRET must be configured outside testing")
            if len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters outside testing")
            if self.access_token_minutes < 5 or self.access_token_minutes > 120:
                raise ValueError("ACCESS_TOKEN_MINUTES must be between 5 and 120")
            if self.environment == "production":
                if self.enable_docs:
                    raise ValueError("ENABLE_DOCS must be false in production")
                if "*" in self.cors_origins:
                    raise ValueError("CORS_ORIGINS cannot contain '*' in production")
                if "*" in self.trusted_hosts:
                    raise ValueError("TRUSTED_HOSTS cannot contain '*' in production")
                if self.database_statement_timeout_ms < 1000:
                    raise ValueError("DATABASE_STATEMENT_TIMEOUT_MS is too low for production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
