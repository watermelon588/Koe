"""Settings loaded from backend/.env (see .env.example for the names)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Required: the app refuses to start without it.
    gemini_api_key: str

    # Optional until their phase; empty means "not set up yet".
    github_token: str = ""
    github_repos: str = ""  # comma-separated "owner/repo"
    github_login: str = ""  # your GitHub username: alert rules match "me" against it
    github_webhook_secret: str = ""  # same secret as in the repo's webhook settings
    notion_token: str = ""
    notion_database_id: str = ""
    notion_data_source_id: str = ""  # explicit source, or resolve a single source from database ID
    google_sheets_id: str = ""
    google_sheets_tab: str = "Hours"
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    allowed_whatsapp_numbers: str = ""  # comma-separated, e.g. 919876543210
    whatsapp_app_secret: str = ""  # Meta app -> App settings -> Basic -> App secret (signs webhooks)
    whatsapp_verify_token: str = ""  # any string you choose; paste the same one into Meta's webhook setup

    timezone: str = "Asia/Kolkata"
    supabase_url: str = ""
    supabase_secret_key: str = ""  # backend only: sb_secret_... or legacy service_role
    koe_owner_id: str = "rohit"  # single-user namespace, never taken from a model/browser
    koe_access_token: str = ""  # required for browser calls when Supabase enables writes
    google_credentials_file: str = "credentials.json"
    google_token_file: str = "token.json"
    google_calendar_id: str = "primary"
    working_hours_start: str = "09:00"
    working_hours_end: str = "21:00"
    gemini_text_model: str = "gemini-3.8-flash"
    # Web Push asks every sender for a contact (mailto: or https:), shown only to push services.
    koe_push_contact: str = "mailto:koe@example.com"


settings = Settings()
