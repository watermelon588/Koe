import asyncio
import json

import pytest
import respx

from koe import agent, identity, notion_service as service, store
from koe.config import settings

SOURCE = '11111111-1111-1111-1111-111111111111'
PAGE = '22222222-2222-2222-2222-222222222222'
ROOT = 'https://api.notion.com/v1'


@pytest.fixture(autouse=True)
def account(monkeypatch):
    monkeypatch.setattr(settings, 'notion_token', 'synthetic')
    monkeypatch.setattr(settings, 'notion_data_source_id', SOURCE)


def schema():
    props = {'Name': {'id': 'title', 'type': 'title'}, 'Date': {'id': 'date', 'type': 'date'},
        'Koe type': {'id': 'kind', 'type': 'select'}, 'Koe status': {'id': 'status', 'type': 'select'},
        'Koe action ID': {'id': 'action', 'type': 'rich_text'}}
    props.update({name: {'id': name.lower(), 'type': kind} for name, kind in [
        ('Project', 'rich_text'), ('Estimate', 'number'), ('Billable', 'checkbox'), ('Deadline', 'date'),
        ('Link', 'url'), ('Email', 'email'), ('Computed', 'formula')]})
    props['Priority'] = {'id': 'priority', 'type': 'select', 'select': {'options': [{'id': 'high', 'name': 'High'}]}}
    props['Tags'] = {'id': 'tags', 'type': 'multi_select', 'multi_select': {'options': [{'id': 'work', 'name': 'Work'}]}}
    return {'properties': props, 'id': SOURCE}


def mock_source():
    return respx.get(f'{ROOT}/data_sources/{SOURCE}').respond(200, json=schema())


@respx.mock
def test_typed_properties_use_verified_ids_and_never_create_options():
    mock_source()
    respx.post(f'{ROOT}/data_sources/{SOURCE}/query').respond(200, json={'results': [], 'has_more': False})
    created = respx.post(f'{ROOT}/pages').respond(200, json={'id': PAGE, 'properties': {}, 'url': ''})
    fields = {'Project': 'Koe', 'Estimate': 2.5, 'Billable': True, 'Deadline': '2026-10-20',
              'Priority': 'High', 'Tags': ['Work'], 'Link': 'https://example.com', 'Email': 'user@example.com'}
    async def scenario():
        args = await service.freeze_fields(service.prepare_save('Review', '2026-10-14', fields=fields))
        return await service.save(**args, request_id='action')
    result = asyncio.run(scenario())
    assert result['id'] == PAGE
    props = json.loads(created.calls[0].request.content)['properties']
    assert props['priority'] == {'select': {'id': 'high'}}
    assert props['tags'] == {'multi_select': [{'id': 'work'}]}
    assert props['estimate'] == {'number': 2.5} and props['billable'] == {'checkbox': True}
    assert props['deadline'] == {'date': {'start': '2026-10-20'}}


@pytest.mark.parametrize('fields', [{'Unknown': 'x'}, {'Computed': 1}, {'Koe action ID': 'spoof'},
    {'Priority': 'Invented'}, {'Estimate': True}, {'Estimate': float('inf')}, {'Billable': 'yes'},
    {'Deadline': 'next Tuesday'}, {'Link': 'javascript:alert(1)'}, {'Email': 'a name'}, {'Tags': ['Unknown']}])
@respx.mock
def test_invalid_properties_never_write(fields):
    mock_source()
    async def scenario():
        await service.freeze_fields(service.prepare_save('Review', '2026-10-14', fields=fields))
    with pytest.raises((ValueError, service.NotionError)): asyncio.run(scenario())
    assert all(c.request.method == 'GET' for c in respx.calls)


@respx.mock
def test_schema_change_blocks_a_previously_approved_property():
    route = mock_source()
    async def scenario():
        args = await service.freeze_fields(service.prepare_save('Review', '2026-10-14', fields={'Project': 'Koe'}))
        changed = schema()
        changed['properties']['Project']['id'] = 'recreated-property'
        route.respond(200, json=changed)
        await service.save(**args, request_id='action')
    with pytest.raises(service.NotionError): asyncio.run(scenario())
    assert all(c.request.method == 'GET' for c in respx.calls)


@respx.mock
def test_agent_proposal_freezes_properties_and_shows_values(monkeypatch):
    mock_source()
    seen = []
    async def propose(session, channel, tool, args, summary):
        seen.append((args, summary))
        return {'id': 'action', 'summary': summary, 'expires_ts': 1}
    monkeypatch.setattr(store, 'propose', propose)
    result = asyncio.run(agent.run_tool('notion_save', {'title': 'Review', 'date': '2026-10-14',
        'fields': {'Priority': 'High'}}, context=agent.Conversation('cli')))
    assert 'pending_action' in result
    assert seen[0][0]['expected_properties']['Priority']['id'] == 'priority'
    assert 'Priority' in seen[0][1] and 'High' in seen[0][1]


@respx.mock
def test_schema_discovery_marks_computed_fields_read_only():
    mock_source()
    from koe.tools import notion
    result = asyncio.run(notion.notion_schema())
    assert any(p['name'] == 'Priority' and p['options'] == ['High'] for p in result['editable'])
    assert 'Computed' in result['read_only_or_reserved']


def test_friend_cannot_read_owner_notion_schema(monkeypatch):
    from koe.tools import notion
    token = identity.OWNER.set('synthetic-friend')
    try:
        assert 'error' in asyncio.run(notion.notion_schema())
    finally:
        identity.OWNER.reset(token)
