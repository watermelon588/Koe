"""Preflight diagnostics must never expose credentials or use Neon-unsupported startup options."""
import json
from types import SimpleNamespace

from scripts import check_spotify_setup as check


def test_preflight_sanitizes_provider_and_database_failures(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(check.settings, "spotify_client_id", "a" * 32)
    monkeypatch.setattr(check.settings, "spotify_client_secret", "private-spotify-secret")
    monkeypatch.setattr(check.sp, "configured", lambda: True)

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, **kwargs):
            assert url == check.sp.TOKEN_URL
            assert kwargs["data"] == {"grant_type": "client_credentials"}
            return SimpleNamespace(status_code=200, json=lambda: {"access_token": "private-access-token"})

    monkeypatch.setattr(check.httpx, "Client", Client)
    monkeypatch.setattr(check.store, "connection_options", lambda: {"password": "private-database-password"})

    def fail_database(**kwargs):
        assert "options" not in kwargs  # rejected by Neon's pooler
        raise RuntimeError("private-database-password")

    monkeypatch.setattr(check.psycopg, "connect", fail_database)
    output = tmp_path / "preflight.json"
    result = check.main(output)
    captured = capsys.readouterr().out
    saved = output.read_text()
    assert result["checks"]["spotify_client_credentials"]["accepted"] is True
    assert result["checks"]["database"] == {"reachable": False, "exception_type": "RuntimeError"}
    assert json.loads(saved) == result
    for secret in ("private-spotify-secret", "private-access-token", "private-database-password", "a" * 32):
        assert secret not in saved
        assert secret not in captured
