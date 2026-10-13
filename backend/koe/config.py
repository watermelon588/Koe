"""Settings loaded from backend/.env (see .env.example for the names)."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Required: the app refuses to start without it.
    gemini_api_key: str = Field(repr=False)
    gemini_api_key_2: str = Field(default="", repr=False)  # a second key with its own quota: used when the first hits 429 (gemini.py)

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
    # Tried in order when the main model is overloaded (503); all answered live on 2026-10-13 (gemini.py).
    gemini_fallback_models: str = "gemini-3.6-flash,gemini-3.5-flash,gemini-3-flash-preview"
    # Both spellings work: .env had OPEN_ROUTER_API_KEY while this read OPENROUTER_API_KEY, so the backup never ran.
    openrouter_api_key: str = Field(default="", repr=False, validation_alias=AliasChoices("OPENROUTER_API_KEY", "OPEN_ROUTER_API_KEY"))
    openrouter_model: str = 'openrouter/free'  # free-only optional text fallback; voice still Gemini
    # Web Push asks every sender for a contact (mailto: or https:), shown only to push services.
    koe_push_contact: str = "mailto:koe@example.com"
    # The push identity (base64url private key, from scripts.vapid_key). Set it on hosts whose disk is wiped
    # (Render free); empty = generate backend/data/vapid.pem once and reuse it.
    vapid_private_key: str = Field(default="", repr=False)
    # Browser origins allowed to call the API cross-origin (comma-separated), e.g. https://koe.vercel.app.
    # Empty = same origin only (local dev through the Vite proxy).
    frontend_origins: str = ""
    # Google sign-in (ACCOUNTS_SPEC.md): a "Web application" OAuth client. Empty = sign-in is off.
    google_web_client_id: str = ""
    google_web_client_secret: str = Field(default="", repr=False)
    koe_admin_email: str = ""  # the owner: always allowed, can invite; their user id is koe_owner_id
    koe_public_url: str = ""  # the site people open, e.g. https://koe-pi.vercel.app (Google's redirect goes back here)
    koe_secret_key: str = Field(default="", repr=False)  # encrypts connection tokens (connections.py); 32+ random chars
    koe_daily_turns: int = 60  # turns a day for friends on the shared Gemini key (usage.py); the owner is never limited
    # GitHub connection (connections.py): an OAuth App with callback <site>/auth/github/callback. Empty = off.
    github_client_id: str = ""
    github_client_secret: str = Field(default="", repr=False)


settings = Settings()
