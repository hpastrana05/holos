from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./holos.db"
    secret_key: str = "development-only-change-me"
    access_token_minutes: int = 1440
    admin_email: str = "admin@example.local"
    admin_password: str = "change-me-now"
    screen_token: str = ""
    screen_user_email: str = ""
    household_name: str = "Mi hogar"


settings = Settings()
