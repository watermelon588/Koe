"""Settings loaded from backend/.env (see .env.example for the names)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Required: the app refuses to start without it.
    gemini_api_key: str

    # Optional until their phase; empty means "not set up yet".
    github_token: str = ""
    github_repos: str = ""  # comma-separated "owner/repo"
    notion_token: str = ""
    notion_database_id: str = ""
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    allowed_whatsapp_numbers: str = ""  # comma-separated, e.g. 919876543210

    timezone: str = "Asia/Kolkata"


settings = Settings()
