"""Google is mocked; real shared tool/approval/projection code is exercised."""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
import respx

from koe import agent, call_work, connections, identity, voice_call
from koe.tools import docs
from test_approvals import fake_store

REAL_AUTH_CONTEXT = docs.auth_context


@pytest.fixture(autouse=True)
def google(monkeypatch):
    monkeypatch.setattr(docs, 'auth_context', lambda scopes: (SimpleNamespace(token='synthetic-google-token'), 'person@example.test'))


def document(content='Hello world\n', revision='r1', tabs=None):
    return {'documentId': 'doc-123', 'title': 'Weekly update', 'revisionId': revision,
            'tabs': tabs or [{'tabProperties': {'tabId': 't1', 'title': 'Notes'}, 'documentTab': {
                'body': {'content': [{'paragraph': {'elements': [{'startIndex': 1, 'textRun': {'content': content}}]}}]}}}]}


def edit(**kwargs):
    return dict(document='doc-123', tab_id='t1', revision_id='r1', mode='replace', body='Koe', old_text='world', **kwargs)


@respx.mock
def test_read_nested_tabs_and_bounded_plain_text():
    root = document()
    root['tabs'][0]['childTabs'] = document('x' * 30000)['tabs']
    root['tabs'][0]['childTabs'][0]['tabProperties'] = {'tabId': 't2', 'title': 'Second'}
    route = respx.get(docs.ROOT + '/doc-123').respond(200, json=root)
    result = asyncio.run(docs.docs_read('https://docs.google.com/document/d/doc-123/edit?tab=t1'))
    assert result['revision_id'] == 'r1' and result['truncated']
    assert sum(len(t['text']) for t in result['tabs']) == docs.MAX_READ
    assert result['tabs'][1]['tab_id'] == 't2' and '_runs' not in str(result)
    assert route.calls[0].request.url.params['includeTabsContent'] == 'true'
    assert route.calls[0].request.headers['authorization'] == 'Bearer synthetic-google-token'


@pytest.mark.parametrize('value', ['https://evil.test/document/d/id/edit', '../secret', 'id?token=x', 'https://docs.google.com@evil.test/document/d/id/edit'])
def test_reject_invalid_document_destinations(value):
    assert 'error' in asyncio.run(docs.docs_read(value))


@respx.mock
def test_find_is_paginated_escaped_and_does_not_claim_all_drive():
    route = respx.get(docs.DRIVE).respond(200, json={'files': [{'id': 'doc-123', 'name': 'Notes'}], 'nextPageToken': 'next'})
    result = asyncio.run(docs.docs_find("Rohit's", 'page1'))
    params = route.calls[0].request.url.params
    assert params['pageToken'] == 'page1' and "Rohit\\'s" in params['q']
    assert result['next_page_token'] == 'next' and 'drive.file' in result['scope']


@respx.mock
def test_create_approval_then_confirm_once(fake_store):
    create = respx.post(docs.ROOT).respond(200, json={'documentId': 'doc-123', 'title': 'Weekly update'})
    respx.get(docs.ROOT + '/doc-123').respond(200, json=document('\n'))
    write = respx.post(docs.ROOT + '/doc-123:batchUpdate').respond(200, json={'documentId': 'doc-123', 'replies': [{}]})
    async def run():
        ctx = agent.Conversation('web')
        args = {'title': 'Weekly update', 'body': 'Hello world'}
        assert (await agent.run_tool('docs_create', args))['error']['code'] == 'approval_required'
        result = await agent.run_tool('docs_create', args, context=ctx)
        assert 'Hello world' in result['pending_action']['summary'] and not create.called
        assert (await agent.confirm(ctx, True))['error']['code'] == 'approval_not_ready'
        ctx.approval_ready = True
        a, b = await asyncio.gather(agent.confirm(ctx, True), agent.confirm(ctx, True))
        assert any(r.get('status') == 'executed' for r in (a, b))
        assert create.call_count == write.call_count == 1
        payload = json.loads(write.calls[0].request.content)
        assert payload['writeControl'] == {'requiredRevisionId': 'r1'}
        assert payload['requests'][0]['insertText']['endOfSegmentLocation']['tabId'] == 't1'
    asyncio.run(run())


@respx.mock
def test_create_partial_failure_returns_created_link_no_retry(fake_store):
    create = respx.post(docs.ROOT).respond(200, json={'documentId': 'doc-123'})
    respx.get(docs.ROOT + '/doc-123').respond(200, json=document('\n'))
    write = respx.post(docs.ROOT + '/doc-123:batchUpdate').mock(side_effect=httpx.ReadTimeout('secret provider payload'))
    async def run():
        ctx = agent.Conversation('web')
        await agent.run_tool('docs_create', {'title': 'Notes', 'body': 'Text'}, context=ctx)
        ctx.approval_ready = True
        result = await agent.confirm(ctx, True)
        assert result['status'] == 'failed' and result['partial']
        assert result['url'].endswith('/doc-123/edit') and 'secret' not in str(result)
        assert write.call_count == create.call_count == 1
        assert 'error' in await agent.confirm(ctx, True)
    asyncio.run(run())


@respx.mock
def test_exact_edit_freezes_utf16_range_and_revision(fake_store):
    respx.get(docs.ROOT + '/doc-123').respond(200, json=document('😀 Hello world\n'))
    write = respx.post(docs.ROOT + '/doc-123:batchUpdate').respond(200, json={'documentId': 'doc-123', 'replies': [{}, {}]})
    async def run():
        ctx = agent.Conversation('app')
        result = await agent.run_tool('docs_edit', edit(), context=ctx)
        assert not write.called and 'Replace exactly:\nworld\nWith:\nKoe' in result['pending_action']['summary']
        ctx.approval_ready = True
        assert (await agent.confirm(ctx, True))['status'] == 'executed'
        payload = json.loads(write.calls[0].request.content)
        assert payload['writeControl'] == {'requiredRevisionId': 'r1'}
        assert payload['requests'][0]['deleteContentRange']['range'] == {'tabId': 't1', 'startIndex': 10, 'endIndex': 15}
        assert payload['requests'][1]['insertText']['text'] == 'Koe'
    asyncio.run(run())


@pytest.mark.parametrize('content,revision', [('world world\n', 'r1'), ('Hello world\n', 'r2'), ('a' * 25000, 'r1')])
@respx.mock
def test_stale_ambiguous_or_truncated_proposal_is_rejected(fake_store, content, revision):
    respx.get(docs.ROOT + '/doc-123').respond(200, json=document(content, revision))
    ctx = agent.Conversation('web')
    assert 'error' in asyncio.run(agent.run_tool('docs_edit', edit(), context=ctx))
    assert ctx.pending is None and not fake_store[0]


@respx.mock
def test_provider_stale_revision_after_approval_never_retries(fake_store):
    respx.get(docs.ROOT + '/doc-123').respond(200, json=document())
    write = respx.post(docs.ROOT + '/doc-123:batchUpdate').respond(400, json={'error': {'message': 'secret error'}})
    async def run():
        ctx = agent.Conversation('web')
        await agent.run_tool('docs_edit', edit(), context=ctx)
        ctx.approval_ready = True
        result = await agent.confirm(ctx, True)
        assert result['status'] == 'failed' and 'stale' in result['error']['message']
        assert write.call_count == 1 and 'secret' not in str(result)
    asyncio.run(run())


@respx.mock
def test_account_change_rejects_approved_write(fake_store, monkeypatch):
    async def run():
        ctx = agent.Conversation('web')
        await agent.run_tool('docs_create', {'title': 'Notes', 'body': 'Text'}, context=ctx)
        monkeypatch.setattr(docs, 'auth_context', lambda scopes: (SimpleNamespace(token='other'), 'other@example.test'))
        ctx.approval_ready = True
        result = await agent.confirm(ctx, True)
        assert result['status'] == 'failed' and 'account changed' in result['error']['message']
    asyncio.run(run())


def test_connected_mode_never_falls_back_to_owner_after_disconnect(monkeypatch):
    from koe.config import settings
    monkeypatch.setattr(docs, 'auth_context', REAL_AUTH_CONTEXT)
    monkeypatch.setattr(settings, 'koe_secret_key', 'x' * 40)
    monkeypatch.setattr(connections, 'load', lambda *a: None)
    assert 'error' in asyncio.run(docs.docs_read('doc-123'))


@respx.mock
def test_voice_read_reaches_workspace_and_model(monkeypatch):
    respx.get(docs.ROOT + '/doc-123').respond(200, json=document())
    sent, responses = [], []
    async def send_json(event): sent.append(event)
    async def send_tool_response(**kwargs): responses.append(kwargs)
    asyncio.run(voice_call._run_tools(SimpleNamespace(send_json=send_json), SimpleNamespace(send_tool_response=send_tool_response),
        [SimpleNamespace(id='docs-call', name='docs_read', args={'document': 'doc-123'})], voice_call.CallState()))
    assert sent[-1]['work']['service'] == 'docs'
    assert sent[-1]['work']['tabs'][0]['text'] == 'Hello world\n' and responses
    assert 'synthetic-google-token' not in str(sent)


def test_projection_preserves_exact_preview_but_hides_credentials():
    p = call_work.project('docs_edit', {'title': 'Notes', 'body': 'x' * 12000, 'expected_account': 'private', 'edit_range': {'startIndex': 1}},
                          {'url': 'https://evil.test', 'access_token': 'private'})
    assert len(p['details']['body']) == 12000 and p['url'] == ''
    assert 'private' not in str(p) and 'edit_range' not in str(p)


@respx.mock
def test_preview_timeout_is_sanitized_without_proposal(fake_store):
    respx.get(docs.ROOT + '/doc-123').mock(side_effect=httpx.ReadTimeout('private provider detail'))
    ctx = agent.Conversation('web')
    result = asyncio.run(agent.run_tool('docs_edit', edit(), context=ctx))
    assert 'error' in result and 'private' not in str(result) and ctx.pending is None


@respx.mock
def test_pending_suggestions_are_not_edited(fake_store):
    data = document()
    data['tabs'][0]['documentTab']['body']['content'][0]['paragraph']['elements'][0]['suggestedInsertionIds'] = ['suggestion']
    respx.get(docs.ROOT + '/doc-123').respond(200, json=data)
    result = asyncio.run(agent.run_tool('docs_edit', edit(), context=agent.Conversation('web')))
    assert 'suggestions' in result['error']['message']


@respx.mock
def test_overlapping_matches_are_ambiguous(fake_store):
    respx.get(docs.ROOT + '/doc-123').respond(200, json=document('aaaa\n'))
    result = asyncio.run(agent.run_tool('docs_edit', {**edit(), 'old_text': 'aaa'}, context=agent.Conversation('web')))
    assert 'unique passage' in result['error']['message'] and not fake_store[0]


@pytest.mark.parametrize('bad', ['\x00', '\ue123', '\ud800'])
def test_google_stripped_characters_never_reach_preview(fake_store, bad):
    result = asyncio.run(agent.run_tool('docs_create', {'title': 'Notes', 'body': bad}, context=agent.Conversation('web')))
    assert 'error' in result and not fake_store[0]


@respx.mock
def test_append_and_cancel_use_shared_voice_approval(fake_store):
    respx.get(docs.ROOT + '/doc-123').respond(200, json=document())
    write = respx.post(docs.ROOT + '/doc-123:batchUpdate').respond(200, json={'documentId': 'doc-123', 'replies': [{}]})
    state, sent = voice_call.CallState(), []
    async def send_json(event): sent.append(event)
    async def run():
        args = {**edit(), 'mode': 'append', 'old_text': '', 'body': '\nNext week'}
        await agent.run_tool('docs_edit', args, context=state.context)
        state.context.approval_ready = True
        await voice_call._approval_result(SimpleNamespace(send_json=send_json), state, False, state.context.pending['id'])
        assert not write.called and sent[-1]['status'] == 'rejected'
        await agent.run_tool('docs_edit', args, context=state.context)
        state.context.approval_ready = True
        await voice_call._approval_result(SimpleNamespace(send_json=send_json), state, True, state.context.pending['id'])
        assert sent[-1]['status'] == 'executed' and sent[-1]['work']['service'] == 'docs'
        assert json.loads(write.calls[0].request.content)['requests'] == [
            {'insertText': {'endOfSegmentLocation': {'tabId': 't1'}, 'text': '\nNext week'}}]
    asyncio.run(run())
