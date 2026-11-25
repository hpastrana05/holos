from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./holos.db"
    secret_key: str = Field(
        default="development-only-change-me",
        validation_alias=AliasChoices("SECRET_KEY", "HOLOS_SECRET_KEY"),
    )
    access_token_minutes: int = 1440
    admin_email: str = Field(
        default="admin@example.local",
        validation_alias=AliasChoices("ADMIN_EMAIL", "HOLOS_ADMIN_EMAIL"),
    )
    admin_password: str = Field(
        default="change-me-now",
        validation_alias=AliasChoices("ADMIN_PASSWORD", "HOLOS_ADMIN_PASSWORD"),
    )
    household_name: str = "Mi hogar"
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    gemini_fallback_models: str = "gemini-3.1-flash-lite"
    telegram_bot_token: str | None = None
    ha_url: str | None = None
    ha_token: str | None = None
    ha_timeout_seconds: float = 8
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None


settings = Settings()
