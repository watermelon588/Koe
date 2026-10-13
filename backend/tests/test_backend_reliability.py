import asyncio
import io
import wave
from contextlib import asynccontextmanager
from types import SimpleNamespace

from fastapi.testclient import TestClient
from google.genai import errors

from koe import app_channel, auth, store
from koe.config import settings
from koe.main import app


def test_voice_retry_discards_incomplete_audio(monkeypatch):
    attempt, saved = [], []
    @asynccontextmanager
    async def connect(**kwargs):
        number = len(attempt)
        attempt.append(number)
        async def receive():
            audio = b'\x01\x00' if number == 0 else b'\x02\x00\x03\x00'
            yield SimpleNamespace(server_content=SimpleNamespace(model_turn=SimpleNamespace(parts=[
                SimpleNamespace(inline_data=SimpleNamespace(data=audio))]), turn_complete=number == 1))
            if number == 0:
                raise errors.ClientError(429, {'error': {'message': 'quota'}})
        async def send_realtime_input(**kwargs): pass
        yield SimpleNamespace(receive=receive, send_realtime_input=send_realtime_input)
    async def save(audio):
        saved.append(audio)
        return 'synthetic.wav'
    live = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
    monkeypatch.setattr(app_channel.gemini, 'live_client', lambda: live)
    monkeypatch.setattr(app_channel.gemini, 'rest_client', lambda client: None)
    monkeypatch.setattr(app_channel, 'save_voice', save)
    assert asyncio.run(app_channel.speak('Synthetic answer.')) == 'synthetic.wav'
    with wave.open(io.BytesIO(saved[0]), 'rb') as audio:
        assert audio.readframes(10) == b'\x02\x00\x03\x00'


def test_background_audit_is_bounded_and_drains_with_the_original_owner(monkeypatch):
    from koe import identity
    seen = []
    monkeypatch.setattr(settings, 'database_url', 'configured-for-mock')
    monkeypatch.setattr(store, 'MAX_BACKGROUND', 2, raising=False)
    async def scenario():
        gate = asyncio.Event()
        async def record(*args, **kwargs):
            await gate.wait()
            seen.append(identity.owner_id())
        monkeypatch.setattr(store, 'record_best_effort', record)
        token = identity.OWNER.set('synthetic-owner')
        try:
            assert store.record_later('app', 's', 'message', 'one') is True
            assert store.record_later('app', 's', 'message', 'two') is True
            assert store.record_later('app', 's', 'message', 'three') is False
        finally:
            identity.OWNER.reset(token)
        gate.set()
        assert await store.drain_background(timeout=1) == 0
        assert not store._background
    asyncio.run(scenario())
    assert seen == ['synthetic-owner', 'synthetic-owner']


def test_shutdown_drain_is_bounded_and_sanitizes_failed_audit_tasks(monkeypatch, caplog):
    monkeypatch.setattr(settings, 'database_url', 'configured-for-mock')
    async def scenario():
        async def stalled(*args, **kwargs): await asyncio.Event().wait()
        monkeypatch.setattr(store, 'record_best_effort', stalled)
        store.record_later('app', 's', 'message', 'one')
        assert await store.drain_background(timeout=.01) == 1
        async def failed(*args, **kwargs): raise ValueError('private-provider-details')
        monkeypatch.setattr(store, 'record_best_effort', failed)
        store.record_later('app', 's', 'message', 'two')
        await store.drain_background(timeout=1)
    asyncio.run(scenario())
    assert 'private-provider-details' not in caplog.text


def test_deployment_diagnostics_are_authenticated_and_never_return_secret_values(monkeypatch):
    monkeypatch.setattr(settings, 'koe_access_token', 'synthetic-access-secret')
    monkeypatch.setattr(settings, 'gemini_api_key_2', 'synthetic-gemini-secret')
    monkeypatch.setattr(settings, 'openrouter_api_key', 'synthetic-router-secret')
    monkeypatch.setenv('RENDER_GIT_COMMIT', 'a' * 40)
    with TestClient(app) as client:
        health = client.get('/health')
        assert health.json() == {'ok': True}
        assert health.headers['x-koe-revision'] == 'a' * 40
        assert client.get('/api/backend/status').status_code == 401
        r = client.get('/api/backend/status', headers={'Authorization': 'Bearer synthetic-access-secret'})
        assert r.status_code == 200
        assert r.headers['cache-control'] == 'no-store'
        assert r.json()['configuration']['gemini_secondary_configured'] is True
        assert 'synthetic-' not in r.text
        monkeypatch.setenv('RENDER_GIT_COMMIT', 'not-a-revision\nprivate')
        assert client.get('/health').headers['x-koe-revision'] == 'unknown'


def test_a_friend_cannot_read_backend_configuration(monkeypatch):
    async def friend(request): return {'id': 'friend', 'is_admin': False}
    monkeypatch.setattr(auth, 'signed_in_user', friend)
    with TestClient(app) as client:
        assert client.get('/api/backend/status').status_code == 403
