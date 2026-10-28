import asyncio
from types import SimpleNamespace

import pytest
from fastapi import Response
from google.auth.exceptions import RefreshError

from koe import connections
from koe.config import settings


def test_revoked_google_grant_reports_reconnect_without_leaking_provider_body(monkeypatch):
    monkeypatch.setattr(settings, 'koe_secret_key', 'synthetic-google-recovery-key-long-enough')
    monkeypatch.setattr(connections, '_google_reconnect', set(), raising=False)
    monkeypatch.setattr(connections, 'load', lambda *args: {'account':'qa@example.test',
        'scopes':connections.GOOGLE_SCOPES, 'token':{'access_token':'old','refresh_token':'refresh'}})
    def refresh(request):
        raise RefreshError('private provider body', {'error':'invalid_grant'})
    monkeypatch.setattr(connections, 'Credentials', lambda **kwargs: SimpleNamespace(valid=False, refresh_token='refresh', refresh=refresh))
    with pytest.raises(connections.ConnectionError_, match='Reconnect Google') as caught:
        connections.google_credentials([connections.CALENDAR_SCOPE])
    assert 'private' not in str(caught.value)
    async def rows(*args):
        return [{'provider':'google','account':'qa@example.test','scopes':' '.join(connections.GOOGLE_SCOPES)}]
    monkeypatch.setattr(connections, 'sql', rows)
    monkeypatch.setattr(connections, 'pref', lambda *args: '')
    monkeypatch.setattr(connections, 'github_repo_mode', lambda: 'selected')
    status=asyncio.run(connections.list_connections(Response()))
    google=next(row for row in status['connections'] if row['provider']=='google')
    assert google['connected'] and google['reconnect_required']


def test_google_health_read_distinguishes_missing_scope_from_revocation(monkeypatch):
    async def scenario():
        monkeypatch.setattr(connections, 'google_credentials', lambda scopes: None)
        result=await connections.google_health(Response())
        assert result['ready'] is False and result['connected'] is False
        def expired(scopes):
            raise connections.ConnectionError_('Google access expired. Reconnect Google in Settings → Connections.')
        monkeypatch.setattr(connections, 'google_credentials', expired)
        result=await connections.google_health(Response())
        assert result['ready'] is False and result['reconnect_required'] is True
        monkeypatch.setattr(connections, 'google_credentials', lambda scopes: SimpleNamespace(valid=True))
        result=await connections.google_health(Response())
        assert result['ready'] is True and result['reconnect_required'] is False
    asyncio.run(scenario())
