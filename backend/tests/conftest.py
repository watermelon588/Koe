"""No test may inherit the owner's live storage configuration from backend/.env."""
import os

os.environ.setdefault("GEMINI_API_KEY", "test")

import pytest

from koe.config import settings
from koe import events


@pytest.fixture(autouse=True)
def isolate_live_storage(monkeypatch):
    monkeypatch.setattr(events, "hub", events.Hub())
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_secret_key", "")
    monkeypatch.setattr(settings, "koe_access_token", "")
