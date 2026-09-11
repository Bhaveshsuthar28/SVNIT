from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # A connection string is deliberately required. Credentials belong in the
    # developer's untracked .env file, never in application source code.
    database_url: str
    app_env: str = Field(default="development")
    cors_origins: str = Field(default="http://localhost:5173")
    log_level: str = Field(default="INFO")
    dataset_name: str = Field(default="trajectories67.csv")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
