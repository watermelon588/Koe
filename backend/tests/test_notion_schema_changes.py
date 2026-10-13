import asyncio
import copy
import json

import httpx
import pytest
import respx

from koe import agent, identity
from koe.config import settings
from test_approvals import fake_store
from test_notion_fields import SOURCE, ROOT, schema


@pytest.fixture(autouse=True)
def account(monkeypatch):
    monkeypatch.setattr(settings, 'notion_token', 'synthetic')
    monkeypatch.setattr(settings, 'notion_data_source_id', SOURCE)


@pytest.fixture
def notion_schema():
    with respx.mock:
        state, writes = schema(), []
        respx.get(f'{ROOT}/data_sources/{SOURCE}').mock(side_effect=lambda request: httpx.Response(200, json=state))
        def patch(request):
            body = json.loads(request.content)
            writes.append(body)
            for name, definition in body['properties'].items():
                kind = next(iter(definition))
                value = copy.deepcopy(definition[kind])
                if kind in ('select', 'multi_select'):
                    for i, option in enumerate(value['options']): option['id'] = f'new-{i}'
                state['properties'][name] = {'id': 'new-' + name, 'type': kind, kind: value}
            return httpx.Response(200, json=state)
        respx.patch(f'{ROOT}/data_sources/{SOURCE}').mock(side_effect=patch)
        yield state, writes


def test_new_properties_are_additive_typed_and_verified(notion_schema):
    from koe import notion_schema as schema_ops
    state, writes = notion_schema
    original = copy.deepcopy(state['properties'])
    properties = [{'name': 'Owner note', 'type': 'rich_text'}, {'name': 'Effort', 'type': 'number'},
        {'name': 'Category', 'type': 'select', 'options': ['Work', 'Personal']}]
    async def scenario():
        args, summary = await schema_ops.prepare_proposal(schema_ops.prepare_write(properties))
        assert 'Work' in summary and 'rich_text' in summary and not writes
        return await schema_ops.add_properties(**args, request_id='action')
    result = asyncio.run(scenario())
    assert result['added_properties'] == [p['name'] for p in properties]
    assert len(writes) == 1 and set(writes[0]['properties']) == {'Owner note', 'Effort', 'Category'}
    assert all(state['properties'][name] == value for name, value in original.items())
    assert writes[0]['properties']['Category'] == {'select': {'options': [{'name': 'Work'}, {'name': 'Personal'}]}}


@pytest.mark.parametrize('properties', [
    [{'name': 'Koe action ID', 'type': 'rich_text'}], [{'name': 'Project', 'type': 'rich_text'}],
    [{'name': 'X', 'type': 'formula'}], [{'name': 'X', 'type': 'status'}], [{'name': 'X', 'type': 'select'}],
    [{'name': 'X', 'type': 'select', 'options': ['High', 'high']}], [{'name': 'X', 'type': 'checkbox', 'options': ['No']}],
    [{'name': 'X', 'type': 'date', 'id': 'spoof'}], [{'name': ' bad ', 'type': 'date'}],
])
def test_invalid_or_existing_properties_never_patch(notion_schema, properties):
    from koe import notion_schema as schema_ops
    async def scenario(): await schema_ops.prepare_proposal(schema_ops.prepare_write(properties))
    with pytest.raises((ValueError, schema_ops.service.NotionError)): asyncio.run(scenario())
    assert not notion_schema[1]


def test_changed_schema_or_source_invalidates_proposal(notion_schema, monkeypatch):
    from koe import notion_schema as schema_ops
    async def scenario():
        args, _ = await schema_ops.prepare_proposal(schema_ops.prepare_write([{'name': 'New', 'type': 'date'}]))
        notion_schema[0]['properties']['Project']['id'] = 'changed-id'
        with pytest.raises(schema_ops.service.NotionError): await schema_ops.add_properties(**args, request_id='action')
        monkeypatch.setattr(settings, 'notion_data_source_id', '33333333-3333-3333-3333-333333333333')
        with pytest.raises(schema_ops.service.NotionError): await schema_ops.add_properties(**args, request_id='action')
    asyncio.run(scenario())
    assert not notion_schema[1]


def test_property_creation_requires_separate_approval_and_no_replay(notion_schema, fake_store):
    async def scenario():
        ctx = agent.Conversation('cli')
        proposal = await agent.run_tool('notion_add_properties', {'properties': [{'name': 'New', 'type': 'checkbox'}]}, context=ctx)
        assert 'pending_action' in proposal and not notion_schema[1]
        stored = fake_store[0][proposal['pending_action']['id']]
        stored['args_json'] = json.loads(json.dumps(stored['args_json']))
        assert 'error' in await agent.confirm(ctx, True)
        ctx.approval_ready = True
        assert (await agent.confirm(ctx, True))['status'] == 'executed'
        assert 'error' in await agent.confirm(ctx, True)
    asyncio.run(scenario())
    assert len(notion_schema[1]) == 1


def test_friend_cannot_propose_owner_schema_changes(notion_schema):
    token = identity.OWNER.set('friend')
    try:
        result = asyncio.run(agent.run_tool('notion_add_properties', {'properties': [{'name': 'New', 'type': 'date'}]},
                                           context=agent.Conversation('cli')))
        assert 'error' in result and not notion_schema[1]
    finally:
        identity.OWNER.reset(token)
