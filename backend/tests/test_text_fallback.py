"""Free text fallback must preserve tool identity and the shared approval boundary."""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
import respx
from google.genai import errors, types

from koe import agent, store, text_agent, text_fallback
from koe.config import settings

URL = 'https://openrouter.ai/api/v1/chat/completions'


@pytest.fixture(autouse=True)
def fallback_account(monkeypatch):
    monkeypatch.setattr(settings, 'openrouter_api_key', 'test-secret-never-print')
    monkeypatch.setattr(settings, 'openrouter_model', 'openrouter/free')
    monkeypatch.setattr(settings, 'notion_token', 'fake')
    monkeypatch.setattr(settings, 'notion_database_id', '')
    monkeypatch.setattr(settings, 'notion_data_source_id', '11111111-1111-1111-1111-111111111111')


def call(name='github_my_prs', args=None, call_id=None):
    return types.Part(function_call=types.FunctionCall(name=name, args=args or {}, id=call_id))


def answer(message):
    return {'choices': [{'message': message}]}


def client_from(sequence):
    calls = []

    async def generate_content(**kwargs):
        calls.append(kwargs)
        item = sequence.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(candidates=[SimpleNamespace(content=item)])

    return SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))), calls


def quota_error():
    return errors.ClientError(429, {'error': {
        'code': 429, 'message': 'quota exhausted', 'status': 'RESOURCE_EXHAUSTED'}})


def test_gemini_calls_without_ids_get_unique_matching_openai_response_ids():
    history = [
        types.Content(role='user', parts=[types.Part.from_text(text='Check my work')]),
        types.Content(role='model', parts=[call(), call('github_review_queue')]),
        types.Content(role='user', parts=[
            types.Part(function_response=types.FunctionResponse(name='github_my_prs', response={'count': 1})),
            types.Part(function_response=types.FunctionResponse(name='github_review_queue', response={'count': 2})),
        ]),
    ]
    messages = text_fallback.messages(history)
    calls = messages[2]['tool_calls']
    responses = messages[3:]
    assert len({tool['id'] for tool in calls}) == 2
    assert [response['tool_call_id'] for response in responses] == [tool['id'] for tool in calls]
    assert [json.loads(response['content']) for response in responses] == [{'count': 1}, {'count': 2}]


def test_repeated_tool_names_without_ids_keep_distinct_call_response_pairs():
    history = [types.Content(role='model', parts=[call(), call()]),
               types.Content(role='user', parts=[
                   types.Part(function_response=types.FunctionResponse(name='github_my_prs', response={'count': 1})),
                   types.Part(function_response=types.FunctionResponse(name='github_my_prs', response={'count': 2})),
               ])]
    messages = text_fallback.messages(history)
    calls = messages[1]['tool_calls']
    assert calls[0]['id'] != calls[1]['id']
    assert messages[2]['tool_call_id'] == calls[0]['id']
    assert messages[3]['tool_call_id'] == calls[1]['id']


def test_unmatched_tool_response_without_id_refuses_transfer():
    history = [types.Content(role='user', parts=[
        types.Part(function_response=types.FunctionResponse(name='github_my_prs', response={'count': 1}))])]
    with pytest.raises(text_fallback.FallbackError):
        text_fallback.messages(history)


@respx.mock
def test_openrouter_tool_answer_is_converted_to_gemini_content_without_execution(monkeypatch):
    executed = []

    async def tool(*args, **kwargs):
        executed.append(True)

    monkeypatch.setattr(agent, 'run_tool', tool)
    request = respx.post(URL).respond(200, json=answer({'content': 'Let me check.', 'tool_calls': [{
        'id': 'router-call-1', 'type': 'function',
        'function': {'name': 'github_my_prs', 'arguments': '{"state":"open"}'}}]}))
    response = asyncio.run(text_fallback.generate([]))
    content = response.candidates[0].content
    assert content.role == 'model'
    assert content.parts[0].text == 'Let me check.'
    assert content.parts[1].function_call.name == 'github_my_prs'
    assert content.parts[1].function_call.args == {'state': 'open'}
    assert content.parts[1].function_call.id == 'router-call-1'
    assert not executed
    payload = json.loads(request.calls[0].request.content)
    assert payload['model'] == 'openrouter/free'
    assert {tool['function']['name'] for tool in payload['tools']} == set(agent.TOOLS)


@pytest.mark.parametrize('name,arguments', [
    ('invented_write_tool', '{}'),
    ('github_my_prs', '{broken-json'),
    ('github_my_prs', '[]'),
])
@respx.mock
def test_unknown_tool_or_invalid_arguments_are_refused_without_execution(monkeypatch, name, arguments):
    executed = []

    async def tool(*args, **kwargs):
        executed.append(True)

    monkeypatch.setattr(agent, 'run_tool', tool)
    respx.post(URL).respond(200, json=answer({'tool_calls': [{
        'id': 'router-call-1', 'function': {'name': name, 'arguments': arguments}}]}))
    with pytest.raises(text_fallback.FallbackError):
        asyncio.run(text_fallback.generate([]))
    assert not executed


@respx.mock
def test_paid_backup_model_is_rejected_before_sending_any_request(monkeypatch):
    monkeypatch.setattr(settings, 'openrouter_model', 'openai/gpt-4.1')
    with pytest.raises(text_fallback.FallbackError, match='free backup'):
        asyncio.run(text_fallback.generate([]))
    assert not respx.calls


@respx.mock
def test_provider_timeout_is_sanitized_and_never_retried():
    request = respx.post(URL).mock(side_effect=httpx.ReadTimeout('test-secret-never-print'))
    with pytest.raises(text_fallback.FallbackError) as raised:
        asyncio.run(text_fallback.generate([]))
    assert 'test-secret-never-print' not in str(raised.value)
    assert 'No tools were replayed' in str(raised.value)
    assert request.call_count == 1


@respx.mock
def test_first_round_quota_failure_uses_backup_but_only_proposes_notion_write(monkeypatch):
    actual_writes = []
    proposals = []

    async def write(**kwargs):
        actual_writes.append(kwargs)
        return {'title': 'Saved'}

    async def propose(session, channel, name, args, summary):
        pending = {'id': 'approval-1', 'session_id': session, 'tool': name, 'args_json': args,
                   'summary': summary, 'expires_ts': '2099-01-01T00:00:00Z', 'status': 'pending'}
        proposals.append(pending)
        return pending

    monkeypatch.setitem(agent.TOOLS, 'notion_save', agent.TOOLS['notion_save']._replace(fn=write))
    monkeypatch.setattr(store, 'propose', propose)
    provider = respx.post(URL).mock(side_effect=[
        httpx.Response(200, json=answer({'tool_calls': [{
            'id': 'notion-call-1', 'function': {'name': 'notion_save', 'arguments': json.dumps({
                'title': 'Review project', 'date': '2026-10-13', 'kind': 'Task', 'body': 'Full task notes'})}}]})),
        httpx.Response(200, json=answer({'content': 'Please confirm the proposed task.'})),
    ])
    client, gemini_calls = client_from([quota_error()])
    context = agent.Conversation('cli')
    history = []
    result = asyncio.run(text_agent.chat('Save a task for today', history, context, client))
    assert len(gemini_calls) == 1 and provider.call_count == 2
    assert len(proposals) == 1 and not actual_writes
    assert result['pending_action']['id'] == 'approval-1'
    assert context.approval_ready is True
    assert 'Full task notes' in proposals[0]['summary']
    sent = json.loads(provider.calls[1].request.content)['messages']
    assert sent[-1]['role'] == 'tool' and sent[-1]['tool_call_id'] == 'notion-call-1'
    assert json.loads(sent[-1]['content'])['pending_action']['id'] == 'approval-1'


@respx.mock
def test_quota_failure_after_executed_tool_never_switches_provider_or_replays_write(monkeypatch):
    writes = []

    async def log_write(**kwargs):
        writes.append(kwargs)
        return {'added': 1, 'url': 'https://www.notion.so/daily-log'}

    monkeypatch.setitem(agent.TOOLS, 'notion_log', agent.TOOLS['notion_log']._replace(fn=log_write))
    content = types.Content(role='model', parts=[call('notion_log', {
        'date': '2026-10-13', 'entries': ['Reviewed project']})])
    client, gemini_calls = client_from([content, quota_error()])
    result = asyncio.run(text_agent.chat('Log my work', [], agent.Conversation('cli'), client))
    assert len(writes) == 1 and len(gemini_calls) == 2
    assert not respx.calls
    assert result['text'].startswith('Gemini is busy')


@respx.mock
def test_quota_failure_without_backup_key_never_contacts_another_provider(monkeypatch):
    monkeypatch.setattr(settings, 'openrouter_api_key', '')
    client, calls = client_from([quota_error()])
    result = asyncio.run(text_agent.chat('Hello', [], agent.Conversation('cli'), client))
    assert len(calls) == 1 and not respx.calls
    assert result['text'].startswith('Gemini is busy')
