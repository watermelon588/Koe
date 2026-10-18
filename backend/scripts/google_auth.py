"""Run from backend: python -m scripts.google_auth [--with-sheets] [--reauthorize]."""
import argparse
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from koe import google_auth, connections
from koe.config import settings


def main():
    parser = argparse.ArgumentParser(description="Connect your Google Calendar (and optionally Sheets) to Koe.")
    parser.add_argument("--with-sheets", action="store_true")
    parser.add_argument("--with-docs", action="store_true")
    parser.add_argument("--reauthorize", action="store_true")
    args = parser.parse_args()
    scopes = google_auth.CALENDAR_SCOPES + ([google_auth.SHEETS_SCOPE] if args.with_sheets else [])
    if args.with_docs:
        scopes += [connections.DOCS_SCOPE, connections.DRIVE_FILE_SCOPE]
    if not args.reauthorize:
        try:
            creds = google_auth.credentials()
            if creds.has_scopes(scopes):
                print("Google is already authorized for the requested permissions.")
                return
        except google_auth.GoogleAuthError:
            pass
    if not Path(settings.google_credentials_file).is_file():
        parser.exit(1, "Missing credentials.json. Follow docs/PHASE2_SETUP.md first.\n")
    try:
        flow = InstalledAppFlow.from_client_secrets_file(settings.google_credentials_file, scopes)
        creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        if not creds.has_scopes(scopes):
            parser.exit(1, "Not all requested permissions were granted. Run again and select them.\n")
        google_auth.save_token(creds)
    except Exception:
        parser.exit(1, "Google authorization failed. Check your Desktop client, enabled APIs and test-user email.\n")
    print("Google connected. Saved token.json locally; it is ignored by Git.")


if __name__ == "__main__":
    main()
