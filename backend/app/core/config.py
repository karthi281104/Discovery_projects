from pathlib import Path
from pydantic import model_validator
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

    # Discovery worker settings
    discovery_enabled: bool = True
    discovery_interval_minutes: int = 60
    discovery_request_timeout: float = 15.0
    discovery_max_pages_per_source: int = 10
    discovery_max_concurrent_sources: int = 3
    discovery_user_agent: str = "TamilEventDiscoveryBot/1.0 (+https://github.com/karthi281104/Discovery_projects)"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.app_env.lower() == "production":
            unsafe_secrets = {
                "change-me-in-production",
                "replace-with-a-long-random-secret",
                "secret",
                "changeme",
                "secret_key",
            }
            if self.secret_key in unsafe_secrets or len(self.secret_key) < 32:
                raise ValueError(
                    "In production, SECRET_KEY must be set to a secure string with at least 32 characters."
                )

            unsafe_passwords = {"change-me", "admin", "password", "12345678", "admin123"}
            if self.admin_password in unsafe_passwords or len(self.admin_password) < 8:
                raise ValueError(
                    "In production, ADMIN_PASSWORD must be explicitly configured with at least 8 characters."
                )

            if self.database_url.startswith("sqlite"):
                raise ValueError(
                    "In production, DATABASE_URL must configure a PostgreSQL database, not SQLite."
                )
        return self


settings = Settings()
