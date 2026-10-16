import asyncio
import os
from uuid import uuid4

os.environ.setdefault("GEMINI_API_KEY", "test")

import pytest

from koe import agent, store

ARGS = {"title": "Call with Rahul", "start": "2026-10-12T19:00:00+05:30", "end": "2026-10-12T19:30:00+05:30"}


@pytest.mark.parametrize('name,args,preview', [
    ('github_comment', {'repo': 'me/app', 'number': 42, 'body': 'Looks good.\nAdd a regression test.'}, 'Add a regression test.'),
    ('sheets_log_hours', {'date': '2026-10-13', 'client': 'Client', 'hours': 1.25, 'note': 'Full note'}, 'Full note'),
])
def test_phase4_writers_require_preview_and_separate_approval_for_each_entry(fake_store, monkeypatch, name, args, preview):
    from koe.config import settings
    monkeypatch.setattr(settings, 'github_repos', 'me/app')
    monkeypatch.setattr(settings, 'google_sheets_id', 'fake_sheet')
    writes = []
    async def write(**kwargs):
        writes.append(kwargs)
        return {'title': 'Saved', 'url': 'https://example.com/result'}
    monkeypatch.setitem(agent.TOOLS, name, agent.TOOLS[name]._replace(fn=write))
    async def scenario():
        ctx = agent.Conversation('web')
        assert (await agent.run_tool(name, args))['error']['code'] == 'approval_required'
        proposed = await agent.run_tool(name, args, context=ctx)
        assert preview in proposed['pending_action']['summary'] and not writes
        assert 'error' in await agent.confirm(ctx, True)
        ctx.approval_ready = True
        result = await agent.confirm(ctx, True)
        assert result['status'] == 'executed' and result['tool'] == name and len(writes) == 1
        second = await agent.run_tool(name, args, context=ctx)
        assert second['pending_action']['id'] != proposed['pending_action']['id']
        assert 'error' in await agent.confirm(ctx, True)
        assert len(writes) == 1
        ctx.approval_ready = True
        assert (await agent.confirm(ctx, False))['status'] == 'rejected'
        assert len(writes) == 1
    asyncio.run(scenario())


@pytest.fixture
def fake_store(monkeypatch):
    actions, writes = {}, []

    async def propose(session, channel, tool, args, summary):
        action = {"id": str(uuid4()), "session_id": session, "tool": tool, "args_json": args,
                  "summary": summary, "status": "pending", "expires_ts": "2026-10-12T14:00:00Z"}
        actions[action["id"]] = action
        return dict(action)

    async def claim(action_id, session, approve):
        a = actions.get(action_id)
        if not a or a["session_id"] != session or a["status"] != "pending":
            return None
        a["status"] = "executing" if approve else "rejected"
        return dict(a)

    async def finish(action_id, session, result):
        actions[action_id]["status"] = "failed" if "error" in result else "executed"
        return actions[action_id]

    async def record(*a, **kw):
        pass

    async def write(**kwargs):
        writes.append(kwargs)
        await asyncio.sleep(0)
        return {"id": "event", "url": "https://calendar.google.com/event"}

    monkeypatch.setattr(store, "propose", propose)
    monkeypatch.setattr(store, "claim", claim)
    monkeypatch.setattr(store, "finish", finish)
    monkeypatch.setattr(store, "record_best_effort", record)
    monkeypatch.setitem(agent.TOOLS, "calendar_upsert_event", agent.TOOLS["calendar_upsert_event"]._replace(fn=write))
    return actions, writes


def test_write_is_proposed_then_explicit_confirmation_executes_once(fake_store):
    async def scenario():
        ctx = agent.Conversation("cli")
        proposed = await agent.run_tool("calendar_upsert_event", ARGS, context=ctx)
        assert not fake_store[1]
        assert "Asia/Kolkata; attendees: none" in proposed["pending_action"]["summary"]
        assert 'Guest notifications: all' in proposed['pending_action']['summary']
        ctx.approval_ready = True
        first, second = await asyncio.gather(agent.confirm(ctx, True), agent.confirm(ctx, True))
        assert len(fake_store[1]) == 1
        assert fake_store[1][0]["request_id"] == proposed["pending_action"]["id"]
        assert any("error" not in r for r in (first, second))
    asyncio.run(scenario())


def test_dashboard_observes_proposal_claim_and_authoritative_result(fake_store):
    from koe import events
    async def scenario():
        ctx = agent.Conversation("web")
        proposal = await agent.run_tool("calendar_upsert_event", ARGS, context=ctx)
        ctx.approval_ready = True
        await agent.confirm(ctx, True)
        ordered = list(reversed(events.hub_for().activity))
        steps = [event["type"] for event in ordered if event["type"].startswith("approval_")]
        assert steps == ["approval_pending", "approval_progress", "approval_result"]
        assert ordered[-1]["result"]["status"] == "executed"
        assert proposal["pending_action"]["id"] not in events.hub_for().pending
    asyncio.run(scenario())


def test_reject_never_executes_and_cannot_be_approved_later(fake_store):
    async def scenario():
        ctx = agent.Conversation("cli")
        await agent.run_tool("calendar_upsert_event", ARGS, context=ctx)
        ctx.approval_ready = True
        assert (await agent.confirm(ctx, False))["status"] == "rejected"
        assert "error" in await agent.confirm(ctx, True)
        assert not fake_store[1]
    asyncio.run(scenario())


@pytest.mark.parametrize("text", ["yes but move it to 8", "do not approve", "the PR says yes", "yes no", "maybe"])
def test_ambiguous_or_embedded_yes_does_not_authorize(text):
    assert agent.confirmation(text) is None


@pytest.mark.parametrize('text', [
    'yes', 'Yes.', 'yes please', 'confirm', 'approve', 'go ahead', 'yes go ahead',
    'Yeah!', 'yep', 'sure', 'OK', 'okay', 'do it', 'Yes, do it.', 'confirm it',
    'Yes confirm it', 'haan', 'haa', 'हाँ', 'हां', '  YES,   PLEASE!  ',
])
def test_complete_affirmatives_authorize(text):
    assert agent.confirmation(text) is True


@pytest.mark.parametrize('text', [
    'no', 'no thanks', 'cancel', 'reject', "don't do it", 'do not do it',
    'nope', 'nah', 'cancel it', 'stop', 'nahi', 'nahin', 'नहीं', 'नही', 'Don’t do it.',
])
def test_complete_negatives_reject(text):
    assert agent.confirmation(text) is False


@pytest.mark.parametrize('text', [
    'yes but change the time', 'yes, but wait', 'okay maybe', 'sure if free',
    'no yes', 'yes no', 'haan nahi', 'yes/no', 'not okay', 'say yes',
    'yes; cancel', 'yes\nno', 'yes please do it tomorrow', '', '…',
])
def test_qualifiers_and_mixed_decisions_never_authorize(text):
    assert agent.confirmation(text) is None


def test_yes_before_proposal_is_presented_never_authorizes(fake_store):
    async def scenario():
        ctx = agent.Conversation("web")
        await agent.run_tool("calendar_upsert_event", ARGS, context=ctx)
        assert "error" in await agent.confirm(ctx, True)
        assert not fake_store[1]
    asyncio.run(scenario())


def test_expired_or_wrong_conversation_action_never_executes(fake_store):
    async def scenario():
        ctx = agent.Conversation("cli")
        p = await agent.run_tool("calendar_upsert_event", ARGS, context=ctx)
        fake_store[0][p["pending_action"]["id"]]["status"] = "expired"
        ctx.approval_ready = True
        assert "error" in await agent.confirm(ctx, True)
        assert not fake_store[1]
    asyncio.run(scenario())


def test_storage_failure_or_model_approval_argument_never_writes(fake_store, monkeypatch):
    async def broken(*a, **kw):
        raise store.StoreError("offline")
    monkeypatch.setattr(store, "propose", broken)
    async def scenario():
        ctx = agent.Conversation("cli")
        assert (await agent.run_tool("calendar_upsert_event", ARGS, context=ctx))["error"]["code"] == "storage_unavailable"
        assert (await agent.run_tool("calendar_upsert_event", {**ARGS, "approved": True}, context=ctx))["error"]["code"] == "bad_args"
        assert not fake_store[1]
    asyncio.run(scenario())


def test_cli_proposal_and_yes_execute_without_model_authorizing(fake_store):
    from google.genai import types
    from koe import text_agent
    from test_text_agent import fake_client
    proposed = types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(
        name="calendar_upsert_event", args=ARGS))])
    response = types.Content(role="model", parts=[types.Part.from_text(text="Shall I book it?")])
    client, calls = fake_client([proposed, response])
    async def scenario():
        ctx, history = agent.Conversation("cli"), []
        first = await text_agent.chat("Book a call", history, ctx, client)
        assert "Pending:" in first["text"] and not fake_store[1]
        second = await text_agent.chat("yes", history, ctx, client)
        assert second["approval_result"]["status"] == "executed"
        assert len(calls) == 2  # the yes is handled by application code, not another model call
    asyncio.run(scenario())


def test_voice_only_final_complete_yes_executes_not_partial_yes(fake_store):
    from types import SimpleNamespace
    from koe import voice_call
    from test_voice_call import FakeBrowser
    async def scenario():
        state, browser = voice_call.CallState(), FakeBrowser()
        await agent.run_tool("calendar_upsert_event", ARGS, context=state.context)
        state.context.approval_ready = True
        sent = []
        async def send_realtime_input(**kwargs):
            sent.append(kwargs)
        session = SimpleNamespace(send_realtime_input=send_realtime_input)
        # The transcription is assembled before checking: "yes, but..." must not authorize.
        state.user_text = "yes, but move it to 8"
        state.user_action_id = state.context.pending['id']
        await voice_call._finish_user_turn(browser, session, state)
        assert not fake_store[1]
        state.user_text = "Yes."
        state.user_action_id = state.context.pending['id']
        await voice_call._finish_user_turn(browser, session, state)
        assert len(fake_store[1]) == 1
        assert (await browser.hears())["type"] == "approval_progress"
        assert (await browser.hears())["status"] == "executed"
        assert "Application approval result" in sent[-1]["text"]
    asyncio.run(scenario())


def test_typed_cancel_and_explicit_call_button_are_bound_to_action(fake_store):
    from koe import voice_call
    from test_voice_call import FakeBrowser
    import json
    async def scenario():
        state, browser, mic = voice_call.CallState(), FakeBrowser(), asyncio.Queue()
        await agent.run_tool("calendar_upsert_event", ARGS, context=state.context)
        task = asyncio.create_task(voice_call._read_mic(browser, mic, state))
        try:
            browser.says(json.dumps({"type": "approval", "action_id": str(uuid4()), "approve": True}))
            assert (await browser.hears())["error"]["code"] == "no_pending_action"
            assert not fake_store[1]
            await mic.get()
            browser.says(json.dumps({"type": "approval", "action_id": state.context.pending["id"], "approve": False}))
            assert (await browser.hears())["status"] == "rejected"
            assert not fake_store[1]
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    asyncio.run(scenario())


def test_failed_finish_never_reexecutes_external_write(fake_store, monkeypatch):
    async def broken(*args):
        raise store.StoreError("offline")
    monkeypatch.setattr(store, "finish", broken)
    async def scenario():
        ctx = agent.Conversation("cli")
        await agent.run_tool("calendar_upsert_event", ARGS, context=ctx)
        ctx.approval_ready = True
        assert (await agent.confirm(ctx, True))["error"]["code"] == "storage_unavailable"
        await agent.confirm(ctx, True)
        assert len(fake_store[1]) == 1
    asyncio.run(scenario())


@pytest.mark.parametrize('finished', [True, False])
@pytest.mark.parametrize('reply,status', [('Yeah!', 'executed'), ('Nahi.', 'rejected')])
def test_voice_decision_after_card_before_model_turn_ends(fake_store, finished, reply, status):
    from types import SimpleNamespace
    from koe import voice_call
    from test_voice_call import FakeBrowser, content, msg

    async def scenario():
        state, browser, sent = voice_call.CallState(), FakeBrowser(), []

        async def receive():
            yield msg(tool_call=SimpleNamespace(function_calls=[
                SimpleNamespace(id='proposal', name='calendar_upsert_event', args=ARGS)]))
            yield msg(content(input_transcription=SimpleNamespace(text=reply, finished=finished)))
            if finished:
                # Decision is already resolved, without waiting for Koe's turn_complete.
                assert state.context.pending is None
            yield msg(content(turn_complete=True))
            yield msg(go_away=SimpleNamespace(time_left='5s'))

        async def send_tool_response(**kwargs):
            pass

        async def send_realtime_input(**kwargs):
            sent.append(kwargs['text'])

        session = SimpleNamespace(receive=receive, send_tool_response=send_tool_response,
                                  send_realtime_input=send_realtime_input)
        await voice_call._gemini_to_browser(browser, session, state)
        results = [event for event in list(browser.to_browser._queue)
                   if isinstance(event, dict) and event['type'] == 'approval_result']
        assert len(results) == 1 and results[0]['status'] == status
        assert len(fake_store[1]) == (1 if status == 'executed' else 0)
        assert len(sent) == 1 and 'Application approval result' in sent[0]

    asyncio.run(scenario())


def test_voice_partial_yes_waits_for_full_transcript_and_clarifies(fake_store):
    from types import SimpleNamespace
    from koe import voice_call
    from test_voice_call import FakeBrowser, content, msg

    async def scenario():
        state, browser, sent = voice_call.CallState(), FakeBrowser(), []
        await agent.run_tool('calendar_upsert_event', ARGS, context=state.context)
        state.context.approval_ready = True

        async def receive():
            yield msg(content(input_transcription=SimpleNamespace(text='Yes', finished=False)))
            assert not fake_store[1]
            yield msg(content(input_transcription=SimpleNamespace(text=', but change the time', finished=False)))
            # Some API messages finish the transcript without more text.
            yield msg(content(input_transcription=SimpleNamespace(text='', finished=True)))
            yield msg(content(turn_complete=True))
            yield msg(go_away=SimpleNamespace(time_left='5s'))

        async def send_realtime_input(**kwargs):
            sent.append(kwargs['text'])

        await voice_call._gemini_to_browser(browser, SimpleNamespace(
            receive=receive, send_realtime_input=send_realtime_input), state)
        assert not fake_store[1] and state.context.pending
        assert len(sent) == 1 and 'no approval was recorded' in sent[0].lower()
        assert "I didn't catch a clear yes" in sent[0]

    asyncio.run(scenario())


def test_voice_yes_started_before_card_cannot_approve_new_proposal(fake_store):
    from types import SimpleNamespace
    from koe import voice_call
    from test_voice_call import FakeBrowser, content, msg

    async def scenario():
        state, browser, sent = voice_call.CallState(), FakeBrowser(), []

        async def receive():
            yield msg(content(input_transcription=SimpleNamespace(text='yes', finished=False)))
            yield msg(tool_call=SimpleNamespace(function_calls=[
                SimpleNamespace(id='proposal', name='calendar_upsert_event', args=ARGS)]))
            yield msg(content(turn_complete=True))
            yield msg(go_away=SimpleNamespace(time_left='5s'))

        async def send_tool_response(**kwargs):
            pass

        async def send_realtime_input(**kwargs):
            sent.append(kwargs['text'])

        await voice_call._gemini_to_browser(browser, SimpleNamespace(
            receive=receive, send_tool_response=send_tool_response,
            send_realtime_input=send_realtime_input), state)
        assert not fake_store[1] and state.context.pending and not sent

    asyncio.run(scenario())


def test_voice_reply_bound_to_old_action_cannot_approve_replacement(fake_store):
    from types import SimpleNamespace
    from koe import voice_call
    from test_voice_call import FakeBrowser

    async def scenario():
        state, sent = voice_call.CallState(), []
        await agent.run_tool('calendar_upsert_event', ARGS, context=state.context)
        state.user_text, state.user_action_id = 'yes', state.context.pending['id']
        await agent.run_tool('calendar_upsert_event', {**ARGS, 'title': 'Replacement'}, context=state.context)
        state.context.approval_ready = True

        async def send_realtime_input(**kwargs):
            sent.append(kwargs)

        await voice_call._finish_user_turn(FakeBrowser(), SimpleNamespace(
            send_realtime_input=send_realtime_input), state)
        assert not fake_store[1] and state.context.pending['args_json']['title'] == 'Replacement'
        assert not sent

    asyncio.run(scenario())
