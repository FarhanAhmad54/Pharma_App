from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Pharma Management API"
    environment: str = "development"
    database_url: str = ""
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_required_runtime_settings(self) -> "Settings":
        if self.environment != "testing" and (not self.database_url or not self.jwt_secret):
            raise ValueError("DATABASE_URL and JWT_SECRET must be configured outside testing")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
