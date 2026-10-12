from types import SimpleNamespace

import pytest

from koe import google_auth
from koe.config import settings


def test_missing_token_gives_setup_instruction_without_opening_browser(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "google_token_file", str(tmp_path / "token.json"))
    with pytest.raises(google_auth.GoogleAuthError, match="scripts.google_auth"):
        google_auth.credentials()


def test_missing_calendar_scope_requires_reauthorization(tmp_path, monkeypatch):
    path = tmp_path / "token.json"
    path.write_text("{}")
    monkeypatch.setattr(settings, "google_token_file", str(path))
    monkeypatch.setattr(google_auth.Credentials, "from_authorized_user_file", lambda _: SimpleNamespace(has_scopes=lambda _: False))
    with pytest.raises(google_auth.GoogleAuthError, match="permission is missing"):
        google_auth.credentials()


def test_expired_token_refreshes_and_is_saved_without_partial_file(tmp_path, monkeypatch):
    path = tmp_path / "token.json"
    path.write_text("{}")
    monkeypatch.setattr(settings, "google_token_file", str(path))
    refreshed = []
    creds = SimpleNamespace(has_scopes=lambda _: True, valid=False, refresh_token="fake",
                            refresh=lambda request: refreshed.append(True), to_json=lambda: '{"token":"fake-new"}')
    monkeypatch.setattr(google_auth.Credentials, "from_authorized_user_file", lambda _: creds)
    assert google_auth.credentials() is creds
    assert refreshed and path.read_text() == '{"token":"fake-new"}'
    assert not path.with_name("token.json.tmp").exists()


def test_calendar_consent_does_not_silently_grant_sheets(tmp_path, monkeypatch):
    path = tmp_path / 'token.json'
    path.write_text('{}')
    monkeypatch.setattr(settings, 'google_token_file', str(path))
    creds = SimpleNamespace(has_scopes=lambda required: set(required) <= set(google_auth.CALENDAR_SCOPES), valid=True)
    monkeypatch.setattr(google_auth.Credentials, 'from_authorized_user_file', lambda _: creds)
    assert google_auth.credentials() is creds
    with pytest.raises(google_auth.GoogleAuthError, match='--with-sheets --reauthorize'):
        google_auth.credentials(required_scopes=[google_auth.SHEETS_SCOPE])
