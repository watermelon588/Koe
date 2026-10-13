"""Settings loaded from backend/.env (see .env.example for the names)."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Required: the app refuses to start without it.
    gemini_api_key: str = Field(repr=False)

    # Optional until their phase; empty means "not set up yet".
    github_token: str = Field(default="", repr=False)
    github_repos: str = ""  # comma-separated "owner/repo"
    github_login: str = ""  # your GitHub username: alert rules match "me" against it
    github_webhook_secret: str = Field(default="", repr=False)
    notion_token: str = Field(default="", repr=False)
    notion_database_id: str = ""
    notion_data_source_id: str = ""  # explicit source, or resolve a single source from database ID
    google_sheets_id: str = ""
    google_sheets_tab: str = "Hours"
    whatsapp_token: str = Field(default="", repr=False)
    whatsapp_phone_number_id: str = ""
    allowed_whatsapp_numbers: str = ""  # comma-separated, e.g. 919876543210
    whatsapp_app_secret: str = Field(default="", repr=False)
    whatsapp_verify_token: str = Field(default="", repr=False)

    timezone: str = "Asia/Kolkata"
    database_url: str = Field(default="", repr=False)  # backend-only Neon URL, SSL required
    koe_owner_id: str = "rohit"  # single-user namespace, never taken from a model/browser
    koe_access_token: str = Field(default="", repr=False)  # development app password
    google_credentials_file: str = "credentials.json"
    google_token_file: str = "token.json"
    google_calendar_id: str = "primary"
    working_hours_start: str = "09:00"
    working_hours_end: str = "21:00"
    gemini_text_model: str = "gemini-3.8-flash"
    # Web Push asks every sender for a contact (mailto: or https:), shown only to push services.
    koe_push_contact: str = "mailto:koe@example.com"
    # Browser origins allowed to call the API cross-origin (comma-separated), e.g. https://koe.vercel.app.
    # Empty = same origin only (local dev through the Vite proxy).
    frontend_origins: str = ""


settings = Settings()
