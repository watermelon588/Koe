"""Google OAuth for the owner's account. Interactive consent only runs in scripts.google_auth.
https://developers.google.com/workspace/calendar/api/quickstart/python
"""
import os
import threading
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from koe.config import settings

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
_lock = threading.Lock()


class GoogleAuthError(Exception):
    pass


def save_token(creds: Credentials):
    path = Path(settings.google_token_file)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(creds.to_json(), encoding="utf-8")
    os.replace(temporary, path)


def credentials(required_scopes: list[str] | None = None) -> Credentials:
    """Refresh cached consent without opening a browser in an HTTP/WebSocket worker."""
    with _lock:
        path = Path(settings.google_token_file)
        if not path.exists():
            raise GoogleAuthError("Google is not connected. Run: python -m scripts.google_auth")
        try:
            # Read granted scopes; don't overwrite them by passing a larger scopes list.
            creds = Credentials.from_authorized_user_file(str(path))
            required = required_scopes if required_scopes is not None else CALENDAR_SCOPES
            if not creds.has_scopes(required):
                if SHEETS_SCOPE in required:
                    raise GoogleAuthError("Sheets permission is missing. Run: python -m scripts.google_auth --with-sheets --reauthorize")
                raise GoogleAuthError("Calendar permission is missing. Run: python -m scripts.google_auth --reauthorize")
            if not creds.valid:
                if not creds.refresh_token:
                    raise GoogleAuthError("Google consent expired. Run: python -m scripts.google_auth --reauthorize")
                creds.refresh(Request())
                try:
                    save_token(creds)
                except OSError:  # read-only token file (Render secret file): refresh again next time
                    pass
            return creds
        except GoogleAuthError:
            raise
        except (ValueError, OSError):
            raise GoogleAuthError("Cannot read Google token.json; run scripts.google_auth --reauthorize.") from None
        except Exception:
            raise GoogleAuthError("Google token refresh failed; run scripts.google_auth --reauthorize.") from None
