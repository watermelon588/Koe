"""No test may inherit the owner's live storage configuration from backend/.env."""
import os

os.environ.setdefault("GEMINI_API_KEY", "test")

import pytest

from koe.config import settings
from koe import agent, app_channel, events, whatsapp


@pytest.fixture(autouse=True)
def isolate_live_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(events, "hub", events.Hub())
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(settings, "koe_access_token", "")
    # The Koe app's chat history, voice notes and push keys live in backend/data: never touch the real ones.
    data = tmp_path / "data"
    monkeypatch.setattr(app_channel, "DATA", data)
    monkeypatch.setattr(app_channel, "VOICE", data / "voice")
    monkeypatch.setattr(app_channel, "DB", data / "app.db")
    monkeypatch.setattr(app_channel, "CHAT", whatsapp.Chat(context=agent.Conversation("app")))  # fresh lock per test loop
