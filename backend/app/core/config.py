from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    app_name: str = "Tamil Event Discovery API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = f"sqlite:///{BASE_DIR / 'event_discovery.db'}"
    cors_origins: str = "http://localhost:5173"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60
    admin_email: str = "admin@example.com"
    admin_password: str = "change-me"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
