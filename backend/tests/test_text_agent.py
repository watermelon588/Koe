import asyncio
from types import SimpleNamespace

from google.genai import types

from koe import agent, text_agent


def fake_client(responses):
    calls = []
    async def generate_content(**kwargs):
        calls.append(kwargs)
        content = responses.pop(0)
        return SimpleNamespace(candidates=[SimpleNamespace(content=content)])
    return SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))), calls


def test_text_loop_runs_read_tool_and_preserves_actual_model_content(monkeypatch):
    content = types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="github_my_prs", args={}))])
    answer = types.Content(role="model", parts=[types.Part.from_text(text="One PR needs attention.")])
    client, calls = fake_client([content, answer])
    async def prs(**kwargs):
        return {"count": 1}
    monkeypatch.setitem(agent.TOOLS, "github_my_prs", agent.TOOLS["github_my_prs"]._replace(fn=prs))
    history = []
    result = asyncio.run(text_agent.chat("My PRs?", history, agent.Conversation("cli"), client))
    assert result["text"] == "One PR needs attention."
    assert history[1] is content
    assert history[2].parts[0].function_response.response == {"count": 1}
    assert len(calls) == 2


def test_text_loop_is_bounded_even_if_model_keeps_requesting_tools(monkeypatch):
    tool_content = types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="missing", args={}))])
    client, calls = fake_client([tool_content] * text_agent.MAX_TOOL_ROUNDS)
    result = asyncio.run(text_agent.chat("Check", [], agent.Conversation("cli"), client))
    assert "eight tool rounds" in result["text"]
    assert len(calls) == text_agent.MAX_TOOL_ROUNDS


def test_shipped_then_log_sequence_returns_actual_tool_results(monkeypatch):
    shipped = types.Content(role='model', parts=[types.Part(function_call=types.FunctionCall(name='github_shipped', args={'since': 'today'}))])
    log = types.Content(role='model', parts=[types.Part(function_call=types.FunctionCall(name='notion_log', args={
        'date': '2026-10-13', 'entries': ['Merged me/app#42 https://github.com/me/app/pull/42']}))])
    answer = types.Content(role='model', parts=[types.Part.from_text(text='Shipped #42; added to the daily log.')])
    client, calls = fake_client([shipped, log, answer])
    logged = []
    async def read(**kw):
        return {'prs': [{'number': 42}], 'commits': [], 'partial': False}
    async def write(**kw):
        logged.append(kw)
        return {'added': 1}
    monkeypatch.setitem(agent.TOOLS, 'github_shipped', agent.TOOLS['github_shipped']._replace(fn=read))
    monkeypatch.setitem(agent.TOOLS, 'notion_log', agent.TOOLS['notion_log']._replace(fn=write))
    history = []
    result = asyncio.run(text_agent.chat('What did I ship today?', history, agent.Conversation('cli'), client))
    assert len(calls) == 3 and logged[0]['date'] == '2026-10-13'
    assert history[2].parts[0].function_response.response['prs'] == [{'number': 42}]
    assert 'added' in result['text']


def test_approval_result_copy_covers_non_calendar_writes():
    assert text_agent.approval_text({'status': 'executed', 'tool': 'github_comment', 'title': 'Comment on me/app#42'}).startswith('Saved: Comment')
    assert text_agent.approval_text({'status': 'rejected'}) == 'Cancelled. Nothing was changed.'


def test_a_busy_model_is_reported_as_busy_not_as_a_failure():
    from google.genai import errors
    async def generate_content(**kwargs):
        raise errors.ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})
    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    result = asyncio.run(text_agent.chat("hi", [], agent.Conversation("cli"), client))
    assert result["text"].startswith("Gemini is busy")
