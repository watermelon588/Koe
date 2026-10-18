"""Connection UI contracts and scoped GitHub evidence; no live credentials or writes."""
import asyncio
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from koe import agent, auth, connections, identity
from koe.config import settings
from koe.tools import github, github_work
from test_auth import ADMIN, SITE, sign_in


@pytest.fixture
def client(monkeypatch):
    for k, v in {'google_web_client_id': 'client', 'google_web_client_secret': 'secret',
                 'koe_secret_key': 'synthetic-secret-for-connection-repair-tests',
                 'koe_public_url': SITE, 'koe_admin_email': ADMIN,
                 'github_client_id': '', 'github_client_secret': '',
                 'github_token': '', 'github_login': '', 'github_repos': ''}.items():
        monkeypatch.setattr(settings, k, v)
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(connections.api)
    c = TestClient(app, follow_redirects=False, headers={'Origin': SITE})
    sign_in(c, monkeypatch, ADMIN)
    return c


def test_existing_owner_services_are_visible_without_oauth(client, monkeypatch):
    monkeypatch.setattr(settings, 'github_token', 'synthetic-legacy-token')
    monkeypatch.setattr(settings, 'github_login', 'owner')
    monkeypatch.setattr(settings, 'notion_token', 'synthetic-notion')
    monkeypatch.setattr(settings, 'notion_database_id', 'database')
    r = client.get('/api/connections')
    assert r.headers['cache-control'] == 'no-store'
    d = r.json()
    assert not d['github_ready'] and d['github_token_ready']
    assert d['features']['docs'] and d['features']['github_scope']
    assert {x['provider'] for x in d['connections'] if x['connected']} >= {'github', 'notion'}
    assert d['sources']['github'] == 'server'
    assert 'synthetic-legacy-token' not in r.text


@respx.mock
def test_token_connect_picker_all_mode_and_disconnect_do_not_fall_back(client, monkeypatch):
    monkeypatch.setattr(settings, 'github_token', 'owner-legacy-token')
    respx.get('https://api.github.com/user').respond(200, json={'login': 'personal-account'})
    respx.get('https://api.github.com/user/repos').respond(200, json=[{'full_name': 'personal-account/app'}])
    r = client.put('/api/connections/github/token', json={'token': 'new-personal-token'})
    assert r.status_code == 200 and r.json()['account'] == 'personal-account'
    assert connections.github_account()['login'] == 'personal-account'
    assert connections.github_repos() == []
    assert client.get('/api/connections/github/repos').json()['repos'] == ['personal-account/app']
    assert client.put('/api/connections/github/repos', json={'repos': [], 'mode': 'all'}).status_code == 204
    assert asyncio.run(connections.github_scope())['repos'] == ['personal-account/app']
    assert connections.github_repo_allowed('personal-account/new')
    assert client.delete('/api/connections/github').status_code == 204
    assert not connections.github_account()['token']
    assert not next(x for x in client.get('/api/connections').json()['connections'] if x['provider'] == 'github')['connected']


@respx.mock
def test_invalid_token_does_not_replace_connection_and_requires_same_origin(client):
    respx.get('https://api.github.com/user').respond(401, json={'message': 'Bad credentials'})
    assert client.put('/api/connections/github/token', json={'token': 'synthetic-bad-token'}).status_code == 400
    assert connections.load(settings.koe_owner_id, 'github') is None
    assert client.put('/api/connections/github/token', json={'token': 'synthetic-bad-token'}, headers={'Origin': 'https://elsewhere.test'}).status_code == 403


def test_docs_grant_does_not_require_regranting_unrelated_services(client, monkeypatch):
    r = client.get('/auth/google/connect?docs=true&next=/app/settings')
    q = parse_qs(urlparse(r.headers['location']).query)
    monkeypatch.setattr(auth, 'verify_id_token', lambda token: {'sub': 'google-sub-1', 'email': ADMIN, 'email_verified': True, 'nonce': q['nonce'][0]})
    with respx.mock:
        respx.post(auth.TOKEN).respond(200, json={'id_token': 'jwt', 'access_token': 'doc-access', 'refresh_token': 'doc-refresh',
            'scope': ' '.join(['openid', connections.DOCS_SCOPE, connections.DRIVE_FILE_SCOPE])})
        done = client.get('/auth/google/callback', params={'code': 'code', 'state': q['state'][0]})
    assert done.headers['location'] == '/app/settings?connected=docs'
    assert client.get('/api/connections').json()['docs_ready']
    state = asyncio.run(agent.connection_status())
    assert state['docs_permission_granted'] and 'docs_permission_granted' in agent.system_prompt(state)
    assert 'doc-access' not in str(state)
    again = client.get('/auth/google/connect')
    scopes = parse_qs(urlparse(again.headers['location']).query)['scope'][0]
    assert connections.DOCS_SCOPE in scopes


def commit(sha):
    return {'sha': sha, 'html_url': f'https://github.com/actual/app/commit/{sha}',
            'commit': {'message': 'Work on feature branch', 'committer': {'date': '2026-10-17T10:00:00Z'}}}


@respx.mock
def test_actual_token_identity_and_feature_branch_commits_are_counted_once(monkeypatch):
    monkeypatch.setattr(settings, 'github_token', 'legacy-token')
    monkeypatch.setattr(settings, 'github_login', 'wrong-configured-login')
    monkeypatch.setattr(settings, 'github_repos', 'actual/app')
    respx.get('https://api.github.com/user').respond(200, json={'login': 'actual'})
    respx.get('https://api.github.com/search/issues').respond(200, json={'items': [], 'total_count': 0})
    respx.get('https://api.github.com/repos/actual/app/branches').respond(200, json=[{'name': 'feature'}, {'name': 'other'}])
    def history(request):
        assert request.url.params['author'] == 'actual'
        return httpx.Response(200, json=[commit('abcdef1')] if request.url.params.get('sha') else [])
    respx.get('https://api.github.com/repos/actual/app/commits').mock(side_effect=history)
    result = asyncio.run(github_work.github_shipped('yesterday', now=datetime(2026, 10, 18, 1, tzinfo=timezone.utc)))
    assert result['author_login'] == 'actual' and not result['partial']
    assert len(result['commits']) == 1


def test_empty_selection_and_unselected_repo_are_errors_not_zero(monkeypatch):
    monkeypatch.setattr(settings, 'github_repos', '')
    result = asyncio.run(github_work.github_shipped())
    assert result['error']['code'] == 'github_scope' and 'commits' not in result
    result = asyncio.run(github.github_review_queue(repo='someone/other'))
    assert result['error']['code'] == 'github_scope'
    result = asyncio.run(github_work.github_pr_summary('someone/other', 1))
    assert 'error' in result


@respx.mock
def test_all_repo_scan_discloses_truncated_account_scope(monkeypatch):
    monkeypatch.setattr(settings, 'github_token', 'legacy-token')
    asyncio.run(connections.set_pref('github_repo_mode', 'all'))
    respx.get('https://api.github.com/user/repos').respond(200, json=[{'full_name': 'actual/app'}], headers={'Link': '<https://api.github.com/user/repos?page=2>; rel="next"'})
    scope = asyncio.run(connections.github_scope())
    assert scope['partial'] and scope['mode'] == 'all'


def test_friend_cannot_inherit_owner_service_state(client, monkeypatch):
    monkeypatch.setattr(settings, 'github_token', 'owner-token')
    monkeypatch.setattr(settings, 'notion_token', 'owner-notion')
    monkeypatch.setattr(settings, 'notion_database_id', 'owner-database')
    token = identity.OWNER.set('friend')
    try:
        result = asyncio.run(agent.connection_status())
        assert not any(c['connected'] for c in result['connections'] if c['provider'] in ('github', 'notion'))
    finally:
        identity.OWNER.reset(token)
