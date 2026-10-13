"""No test may inherit the owner's live storage configuration from backend/.env."""
import os

os.environ.setdefault("GEMINI_API_KEY", "test")

import pytest

from koe.config import settings
from koe import agent, app_channel, connections, db, events, usage, whatsapp


@pytest.fixture(autouse=True)
def isolate_live_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(events, "hub", events.Hub())
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "koe_access_token", "")
    monkeypatch.setattr(settings, "google_web_client_id", "")  # sign-in off unless a test turns it on
    monkeypatch.setattr(settings, "koe_secret_key", "")  # connections off unless a test turns them on
    monkeypatch.setattr(connections, "_prefs", {})  # per-person settings cache: fresh per test
    monkeypatch.setattr(usage, "_own_keys", {})  # own-Gemini-key cache: fresh per test
    monkeypatch.setattr(connections, "_github", {})  # GitHub account cache: fresh per test
    # With DATABASE_URL cleared above, the Koe app's chat falls back to SQLite: point it at a temp file.
    data = tmp_path / "data"
    monkeypatch.setattr(app_channel, "DATA", data)
    monkeypatch.setattr(db, "DATA", data)
    monkeypatch.setattr(db, "DB", data / "app.db")
    monkeypatch.setattr(app_channel, "CHATS", {})  # fresh conversations (and locks) per test loop
