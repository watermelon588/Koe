import asyncio
import json
from types import SimpleNamespace

import pytest
import respx

from koe import agent, google_auth, store
from koe.config import settings
from koe.tools import sheets
from test_approvals import fake_store


@pytest.fixture(autouse=True)
def account(monkeypatch):
    monkeypatch.setattr(settings, 'google_sheets_id', 'synthetic-sheet')
    monkeypatch.setattr(settings, 'google_sheets_tab', 'Hours')
    monkeypatch.setattr(google_auth, 'credentials', lambda **kwargs: SimpleNamespace(token='synthetic'))


@respx.mock
def test_optional_fields_map_actual_headers_and_remain_literal():
    headers = sheets.HEADERS + ['Project', 'Billable', 'Amount']
    respx.get(url__regex=r'https://sheets.googleapis.com/.*/values/.*').respond(200, json={'values': [headers]})
    route = respx.post(url__regex=r'https://sheets.googleapis.com/.*/values/.*:append').respond(200,
        json={'updates': {'updatedRange': 'Hours!A3:H3'}})
    prepared = sheets.prepare_hours('2026-10-14', 'Client', 1, fields={'Amount': 100, 'Project': '=literal', 'Billable': True})
    async def scenario():
        frozen = await sheets.freeze_fields(prepared)
        return await sheets.sheets_log_hours(**frozen, request_id='action')
    result = asyncio.run(scenario())
    assert result['row'] == 3
    body = json.loads(route.calls[0].request.content)
    assert body['values'][0] == ['2026-10-14', 'Client', 1, '', 'action', '=literal', True, 100]
    assert route.calls[0].request.url.params['valueInputOption'] == 'RAW'


@pytest.mark.parametrize('fields', [{'Unknown': 'x'}, {'Koe action ID': 'spoof'}, {'Project': float('nan')}, {'Project': {'nested': 'x'}}])
@respx.mock
def test_unknown_reserved_or_invalid_fields_never_append(fields):
    respx.get(url__regex=r'https://sheets.googleapis.com/.*/values/.*').respond(200,
        json={'values': [sheets.HEADERS + ['Project']]})
    async def scenario():
        return await sheets.freeze_fields(sheets.prepare_hours('2026-10-14', 'Client', 1, fields=fields))
    with pytest.raises(ValueError): asyncio.run(scenario())
    assert all(c.request.method == 'GET' for c in respx.calls)


@respx.mock
def test_schema_change_after_proposal_blocks_append():
    headers = sheets.HEADERS + ['Project']
    route = respx.get(url__regex=r'https://sheets.googleapis.com/.*/values/.*').respond(200, json={'values': [headers]})
    async def scenario():
        args = await sheets.freeze_fields(sheets.prepare_hours('2026-10-14', 'Client', 1, fields={'Project': 'Koe'}))
        route.respond(200, json={'values': [sheets.HEADERS + ['Customer']]})
        return await sheets.sheets_log_hours(**args, request_id='action')
    result = asyncio.run(scenario())
    assert 'error' in result and all(c.request.method == 'GET' for c in respx.calls)


@respx.mock
def test_agent_freezes_schema_and_previews_every_optional_field(monkeypatch):
    respx.get(url__regex=r'https://sheets.googleapis.com/.*/values/.*').respond(200,
        json={'values': [sheets.HEADERS + ['Project']]})
    seen = []
    async def propose(session, channel, tool, args, summary):
        seen.append((args, summary))
        return {'id': 'a', 'summary': summary, 'expires_ts': 1}
    monkeypatch.setattr(store, 'propose', propose)
    result = asyncio.run(agent.run_tool('sheets_log_hours', {'date': '2026-10-14', 'client': 'Client',
        'hours': 1, 'fields': {'Project': 'Koe'}}, context=agent.Conversation('cli')))
    assert 'pending_action' in result
    assert seen[0][0]['expected_headers'][-1] == 'Project'
    assert 'Project' in seen[0][1] and 'Koe' in seen[0][1]


@respx.mock
def test_duplicate_headers_rejected_by_discovery():
    respx.get(url__regex=r'https://sheets.googleapis.com/.*/values/.*').respond(200,
        json={'values': [sheets.HEADERS + ['Project', 'project']]})
    assert 'error' in asyncio.run(sheets.sheets_schema())


def test_extreme_integer_is_a_validation_error():
    with pytest.raises(ValueError): sheets.prepare_hours('2026-10-14', 'Client', 1, fields={'Amount': 10 ** 400})


@respx.mock
def test_optional_columns_execute_once_only_after_explicit_approval(fake_store):
    respx.get(url__regex=r'https://sheets.googleapis.com/.*/values/.*').respond(200,
        json={'values': [sheets.HEADERS + ['Project']]})
    append = respx.post(url__regex=r'https://sheets.googleapis.com/.*/values/.*:append').respond(200,
        json={'updates': {'updatedRange': 'Hours!A3:F3'}})
    async def scenario():
        ctx = agent.Conversation('cli')
        proposal = await agent.run_tool('sheets_log_hours', {'date': '2026-10-14', 'client': 'Client',
            'hours': 1, 'fields': {'Project': 'Koe'}}, context=ctx)
        assert 'pending_action' in proposal and append.call_count == 0
        assert 'error' in await agent.confirm(ctx, True)
        # The frozen contract also survives the JSON storage boundary.
        action = fake_store[0][proposal['pending_action']['id']]
        action['args_json'] = json.loads(json.dumps(action['args_json']))
        ctx.approval_ready = True
        assert (await agent.confirm(ctx, True))['status'] == 'executed'
        assert 'error' in await agent.confirm(ctx, True)
    asyncio.run(scenario())
    assert append.call_count == 1 and json.loads(append.calls[0].request.content)['values'][0][-1] == 'Koe'
