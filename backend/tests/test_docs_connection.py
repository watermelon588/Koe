"""OAuth -> encrypted account -> chat tools -> approval -> Google -> workspace.
Only provider/model responses and approval persistence are synthetic.
"""
import asyncio
import json
from urllib.parse import parse_qs, urlparse
from types import SimpleNamespace

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.genai import types

from koe import auth, connections, app_channel, gemini
from koe.config import settings
from koe.db import sql
from koe.tools import docs
from test_auth import ADMIN, SITE, sign_in
from test_approvals import fake_store
from test_docs import document


@pytest.fixture
def client(monkeypatch):
    for key, value in {'google_web_client_id': 'client-id', 'google_web_client_secret': 'secret',
                       'koe_secret_key': 'synthetic-encryption-key-for-docs-tests', 'koe_admin_email': ADMIN,
                       'koe_public_url': SITE}.items():
        monkeypatch.setattr(settings, key, value)
    async def notify(*a, **kw): pass
    monkeypatch.setattr(app_channel, 'notify', notify)
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(connections.api)
    app.include_router(app_channel.router)
    return TestClient(app, follow_redirects=False)


def connect(client, monkeypatch, grant_docs=True, refresh='synthetic-refresh'):
    response = client.get('/auth/google/connect?docs=true&next=/app/settings')
    query = parse_qs(urlparse(response.headers['location']).query)
    assert {connections.DOCS_SCOPE, connections.DRIVE_FILE_SCOPE} <= set(query['scope'][0].split())
    monkeypatch.setattr(auth, 'verify_id_token', lambda token: {
        'sub': 'google-sub-1', 'email': ADMIN, 'email_verified': True, 'nonce': query['nonce'][0]})
    scopes = connections.GOOGLE_SCOPES + ([connections.DOCS_SCOPE, connections.DRIVE_FILE_SCOPE] if grant_docs else [])
    with respx.mock:
        respx.post(auth.TOKEN).respond(200, json={'id_token': 'jwt', 'access_token': 'synthetic-docs-token',
            'refresh_token': refresh, 'expires_in': 3600, 'scope': ' '.join(scopes)})
        return client.get('/auth/google/callback', params={'state': query['state'][0], 'code': 'c'})


def test_docs_consent_is_optional_and_decline_preserves_connection(client, monkeypatch):
    assert client.get('/auth/google/connect?docs=true').status_code == 401
    sign_in(client, monkeypatch, ADMIN)
    basic = parse_qs(urlparse(client.get('/auth/google/connect').headers['location']).query)
    assert connections.DOCS_SCOPE not in basic['scope'][0]
    connect(client, monkeypatch)
    assert client.get('/api/connections').json()['docs_ready']
    before = asyncio.run(sql("select token_enc from koe_connections where provider = 'google'"))[0]['token_enc']
    response = connect(client, monkeypatch, grant_docs=False)
    assert 'missing-scopes' in response.headers['location']
    assert asyncio.run(sql("select token_enc from koe_connections where provider = 'google'"))[0]['token_enc'] == before
    assert 'synthetic' not in before


def test_consent_without_new_refresh_retains_same_account_refresh(client, monkeypatch):
    sign_in(client, monkeypatch, ADMIN)
    connect(client, monkeypatch)
    connect(client, monkeypatch, refresh=None)
    row = asyncio.run(sql("select token_enc from koe_connections where provider = 'google'"))[0]
    assert connections.decrypt(row['token_enc'])['refresh_token'] == 'synthetic-refresh'


def test_google_account_switch_between_reads_is_refused(monkeypatch):
    monkeypatch.setattr(connections, 'load', lambda *args: {'account': 'other@example.test', 'scopes': [], 'token': {}})
    with pytest.raises(connections.ConnectionError_, match='account changed'):
        connections.google_credentials([connections.DOCS_SCOPE], expected_account='original@example.test')


@respx.mock
def test_connected_chat_creates_approved_doc_and_rereads_it(client, monkeypatch, fake_store):
    sign_in(client, monkeypatch, ADMIN)
    connect(client, monkeypatch)
    created = respx.post(docs.ROOT).respond(200, json={'documentId': 'doc-123'})
    read = respx.get(docs.ROOT + '/doc-123').respond(200, json=document())
    write = respx.post(docs.ROOT + '/doc-123:batchUpdate').respond(200, json={'documentId': 'doc-123', 'replies': [{}]})
    responses = [types.Content(role='model', parts=[types.Part(function_call=types.FunctionCall(
        name='docs_create', args={'title': 'Weekly update', 'body': 'Hello world'}))]),
        types.Content(role='model', parts=[types.Part.from_text(text='Review this document.')]),
        types.Content(role='model', parts=[types.Part(function_call=types.FunctionCall(name='docs_read', args={'document': 'doc-123'}))]),
        types.Content(role='model', parts=[types.Part.from_text(text='Your document contains Hello world.')])]
    async def generate(**kwargs):
        assert 'docs_create' in str(kwargs['config']['tools'])
        assert '"docs_permission_granted": true' in kwargs['config']['system_instruction']
        return SimpleNamespace(candidates=[SimpleNamespace(content=responses.pop(0))]), settings.gemini_text_model
    monkeypatch.setattr(gemini, 'generate', generate)
    reply = client.post('/api/app/messages', json={'text': 'Create a Google Doc called Weekly update saying Hello world.'})
    assert reply.status_code == 200
    body = reply.json()
    pending = next(e for e in body['workspace'] if e['type'] == 'approval_pending')
    assert pending['work']['service'] == 'docs' and not created.called
    action = pending['work']['action_id']
    result = client.post('/api/app/approvals/' + action, json={'approve': True}).json()
    assert result['action']['status'] == 'executed'
    assert result['workspace'][-1]['work']['url'].endswith('/doc-123/edit')
    assert created.call_count == write.call_count == 1
    assert created.calls[0].request.headers['authorization'] == 'Bearer synthetic-docs-token'
    again = client.post('/api/app/approvals/' + action, json={'approve': True})
    assert write.call_count == 1
    result = client.post('/api/app/messages', json={'text': 'Read that document.'}).json()
    assert result['workspace'][-1]['work']['tabs'][0]['text'] == 'Hello world\n'
    assert 'synthetic-docs-token' not in json.dumps(body) + json.dumps(result)
