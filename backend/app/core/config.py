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
    admin_email: str = "admin@example.local"
    admin_password: str = "change-me-now"
    household_name: str = "Mi hogar"


settings = Settings()
