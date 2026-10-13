"""Notion workspace HTTP contract: read safely, preview before writes, scope approval.

External Notion and Neon boundaries are faked; the application router, auth,
tool gate and approval transitions remain real. No owner data is touched.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from koe import agent, notion_service, store
from koe.config import settings
from koe.main import app

AUTH = {'Authorization': 'Bearer notion-test'}
PAGE = '22222222-2222-2222-2222-222222222222'
RECORD = {'title': 'Planning with Rahul', 'date': '2026-10-14', 'kind': 'Meeting',
          'body': 'Discuss milestones. This is a Notion record, not a calendar booking.'}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, 'koe_access_token', 'notion-test')
    # Explicitly ensure that an accidental provider call cannot use owner secrets.
    monkeypatch.setattr(settings, 'notion_token', '')
    with TestClient(app) as session:
        yield session


@pytest.mark.parametrize('method,path,body', [
    ('GET', '/api/notion/status', None),
    ('GET', '/api/notion/activity', None),
    ('GET', '/api/notion/records', None),
    ('GET', f'/api/notion/records/{PAGE}', None),
    ('GET', '/api/notion/pending', None),
    ('POST', '/api/notion/setup', {'confirm': True}),
    ('POST', '/api/notion/proposals', {'tool': 'notion_save', 'args': RECORD}),
    ('POST', '/api/notion/approvals/proposal', {'approve': True}),
])
def test_every_notion_route_authenticates_before_external_access(client, monkeypatch, method, path, body):
    async def forbidden(*args, **kwargs):
        pytest.fail('An unauthenticated request reached a provider or tool.')
    for name in ('status', 'setup', 'read', 'save', 'archive'):
        monkeypatch.setattr(notion_service, name, forbidden)
    monkeypatch.setattr(agent, 'run_tool', forbidden)
    monkeypatch.setattr(agent, 'confirm', forbidden)
    assert client.request(method, path, json=body).status_code == 401
    assert client.request(method, path, json=body,
                          headers={'Authorization': 'Bearer wrong'}).status_code == 401


def test_missing_owner_access_token_keeps_notion_closed(client, monkeypatch):
    monkeypatch.setattr(settings, 'koe_access_token', '')
    assert client.get('/api/notion/status', headers=AUTH).status_code == 401


def test_status_lists_and_detail_are_read_only_and_preserve_provider_result(client, monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail('A read endpoint attempted a write or an agent turn.')
    for name in ('setup', 'save', 'archive'):
        monkeypatch.setattr(notion_service, name, forbidden)
    monkeypatch.setattr(agent, 'run_tool', forbidden)
    status = {'connected': True, 'workflow_ready': False, 'missing_properties': ['Koe type']}
    listing = {'pages': [{'id': PAGE, 'title': 'Planning'}], 'next_cursor': 'next', 'has_more': True}
    detail = {'page': {'id': PAGE, 'title': 'Planning'}, 'blocks': [{'type': 'paragraph', 'text': 'Agenda'}],
              'truncated': False}
    async def connected():
        return status
    async def read(query='', kind='', cursor='', page_id=''):
        if page_id:
            assert page_id == PAGE
            return detail
        assert (query, kind, cursor) == ('Planning', 'Meeting', 'cursor-1')
        return listing
    monkeypatch.setattr(notion_service, 'status', connected)
    monkeypatch.setattr(notion_service, 'read', read)
    assert client.get('/api/notion/status', headers=AUTH).json() == status
    assert client.get('/api/notion/records', params={'query': 'Planning', 'kind': 'Meeting', 'cursor': 'cursor-1'},
                      headers=AUTH).json() == listing
    assert client.get(f'/api/notion/records/{PAGE}', headers=AUTH).json() == detail


@pytest.mark.parametrize('path,service', [('/api/notion/status', 'status'),
                                         ('/api/notion/records', 'read'),
                                         (f'/api/notion/records/{PAGE}', 'read')])
def test_provider_setup_errors_are_safe_actionable_http_errors(client, monkeypatch, path, service):
    async def unavailable(*args, **kwargs):
        raise notion_service.NotionError('Share this database with the integration.', 'notion_access',
                                        'Check Notion Connections, then refresh.')
    monkeypatch.setattr(notion_service, service, unavailable)
    response = client.get(path, headers=AUTH)
    assert response.status_code == 400
    assert 'Share this database' in response.text and 'notion_access' in response.text
    assert 'Traceback' not in response.text


def test_notion_activity_endpoint_returns_display_only_audit_rows(client, monkeypatch):
    async def audit():
        return [{'id': 'audit', 'ts': '2026-10-13T10:00:00Z', 'kind': 'approval', 'summary': 'executed', 'tool': 'notion_save'}]
    monkeypatch.setattr(store, 'notion_activity', audit)
    response = client.get('/api/notion/activity', headers=AUTH)
    assert response.status_code == 200
    assert response.json()['activity'][0]['summary'] == 'executed'
    assert 'args_json' not in response.text and 'payload_json' not in response.text


@pytest.mark.parametrize('body', [{}, {'confirm': False}, {'confirm': 'true'}, {'confirm': 1}])
def test_setup_requires_explicit_strict_boolean_confirmation(client, monkeypatch, body):
    async def forbidden():
        pytest.fail('Setup was performed without explicit boolean confirmation.')
    monkeypatch.setattr(notion_service, 'setup', forbidden)
    assert client.post('/api/notion/setup', json=body, headers=AUTH).status_code in (400, 422)


def test_explicit_setup_returns_only_the_preparation_result(client, monkeypatch):
    result = {'added': ['Koe type'], 'message': 'Existing records retained.'}
    async def setup():
        return result
    monkeypatch.setattr(notion_service, 'setup', setup)
    assert client.post('/api/notion/setup', json={'confirm': True}, headers=AUTH).json() == result


@pytest.mark.parametrize('tool', ['calendar_upsert_event', 'notion_log', 'unknown', 'notion_read'])
def test_workspace_cannot_propose_unrelated_or_unapproved_tools(client, monkeypatch, tool):
    async def forbidden(*args, **kwargs):
        pytest.fail('An unsupported workspace tool reached agent execution.')
    monkeypatch.setattr(agent, 'run_tool', forbidden)
    assert client.post('/api/notion/proposals', json={'tool': tool, 'args': RECORD},
                       headers=AUTH).status_code in (400, 422)


@pytest.fixture
def approvals(monkeypatch):
    actions, writes = {}, []
    async def propose(session, channel, tool, args, summary):
        action = {'id': str(uuid4()), 'session_id': session, 'channel': channel, 'tool': tool,
                  'args_json': args, 'summary': summary, 'status': 'pending',
                  'expires_ts': (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()}
        actions[action['id']] = action
        return dict(action)
    async def claim(action_id, session, approve):
        action = actions.get(action_id)
        if (not action or action['session_id'] != session or action['status'] != 'pending'
                or datetime.fromisoformat(action['expires_ts']) <= datetime.now(timezone.utc)):
            return None
        action['status'] = 'executing' if approve else 'rejected'
        return dict(action)
    async def finish(action_id, session, result):
        action = actions[action_id]
        assert action['session_id'] == session
        action['status'] = 'failed' if 'error' in result else 'executed'
        return dict(action)
    async def pending_for_session(session):
        matches = [action for action in actions.values()
                   if action['session_id'] == session and action['status'] == 'pending'
                   and datetime.fromisoformat(action['expires_ts']) > datetime.now(timezone.utc)]
        return dict(matches[-1]) if matches else None
    async def record(*args, **kwargs):
        pass
    async def write(**kwargs):
        writes.append(kwargs)
        return {'page_id': PAGE, 'title': 'Planning with Rahul', 'url': 'https://www.notion.so/' + PAGE}
    original_prepare = agent.prepare_write
    def prepare(name, args):
        if name in ('notion_save', 'notion_archive'):
            return dict(args), f'{name}: Planning with Rahul in the configured Notion workspace.'
        return original_prepare(name, args)
    monkeypatch.setattr(agent, 'prepare_write', prepare)
    monkeypatch.setattr(store, 'propose', propose)
    monkeypatch.setattr(store, 'claim', claim)
    monkeypatch.setattr(store, 'finish', finish)
    monkeypatch.setattr(store, 'pending_for_session', pending_for_session)
    monkeypatch.setattr(store, 'record_best_effort', record)
    # Absent tools deliberately fail: this contract requires both writers to be registered.
    for name in ('notion_save', 'notion_archive'):
        monkeypatch.setitem(agent.TOOLS, name, agent.TOOLS[name]._replace(fn=write))
    return actions, writes


def proposal(client, tool='notion_save'):
    result = client.post('/api/notion/proposals', json={'tool': tool, 'args': RECORD}, headers=AUTH)
    assert result.status_code == 200, result.text
    action = result.json()['pending_action']
    assert action['id'] and 'Planning with Rahul' in action['summary']
    return action


@pytest.mark.parametrize('tool', ['notion_save', 'notion_archive'])
def test_proposal_previews_without_writing_then_confirmation_executes_once(client, approvals, tool):
    action = proposal(client, tool)
    assert not approvals[1]
    pending = client.get('/api/notion/pending', headers=AUTH).json()['pending_action']
    assert pending['id'] == action['id']
    assert not approvals[1]
    endpoint = '/api/notion/approvals/' + action['id']
    result = client.post(endpoint, json={'approve': True}, headers=AUTH)
    assert result.status_code == 200, result.text
    assert result.json()['result']['status'] == 'executed'
    assert len(approvals[1]) == 1 and approvals[1][0]['request_id'] == action['id']
    client.post(endpoint, json={'approve': True}, headers=AUTH)
    assert len(approvals[1]) == 1
    assert client.get('/api/notion/pending', headers=AUTH).json()['pending_action'] is None


def test_rejecting_workspace_proposal_never_writes_and_cannot_be_replayed(client, approvals):
    action = proposal(client)
    endpoint = '/api/notion/approvals/' + action['id']
    result = client.post(endpoint, json={'approve': False}, headers=AUTH)
    assert result.status_code == 200, result.text
    assert result.json()['result']['status'] == 'rejected'
    client.post(endpoint, json={'approve': True}, headers=AUTH)
    assert not approvals[1]


def test_provider_record_status_cannot_override_authoritative_approval_status(client, approvals, monkeypatch):
    async def save_record(**kwargs):
        return {'id': PAGE, 'title': 'Task', 'status': 'Open'}
    monkeypatch.setitem(agent.TOOLS, 'notion_save', agent.TOOLS['notion_save']._replace(fn=save_record))
    action = proposal(client)
    response = client.post('/api/notion/approvals/' + action['id'], json={'approve': True}, headers=AUTH)
    assert response.status_code == 200
    assert response.json()['result']['status'] == 'executed'
    assert approvals[0][action['id']]['status'] == 'executed'


@pytest.mark.parametrize('approve', ['false', 'true', 0, 1, None])
def test_workspace_approval_requires_a_strict_boolean(client, approvals, approve):
    action = proposal(client)
    assert client.post('/api/notion/approvals/' + action['id'], json={'approve': approve},
                       headers=AUTH).status_code == 422
    assert not approvals[1]


def test_expired_workspace_proposal_cannot_execute(client, approvals):
    action = proposal(client)
    approvals[0][action['id']]['expires_ts'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    result = client.post('/api/notion/approvals/' + action['id'], json={'approve': True}, headers=AUTH)
    assert any(code in result.text for code in ('approval_unavailable', 'no_pending_action'))
    assert not approvals[1]


def test_foreign_action_id_cannot_resolve_or_discard_current_workspace_proposal(client, approvals):
    action = proposal(client)
    response = client.post('/api/notion/approvals/another-conversation', json={'approve': True}, headers=AUTH)
    assert 'no_pending_action' in response.text
    assert not approvals[1]
    assert client.get('/api/notion/pending', headers=AUTH).json()['pending_action']['id'] == action['id']
    result = client.post('/api/notion/approvals/' + action['id'], json={'approve': True}, headers=AUTH)
    assert result.json()['result']['status'] == 'executed'
    assert len(approvals[1]) == 1


def test_app_chat_cannot_confirm_a_workspace_proposal(client, approvals):
    action = proposal(client)
    result = client.post('/api/app/approvals/' + action['id'], json={'approve': True}, headers=AUTH)
    assert result.json()['action']['status'] != 'executed'
    assert not approvals[1]
    assert client.get('/api/notion/pending', headers=AUTH).json()['pending_action']['id'] == action['id']
