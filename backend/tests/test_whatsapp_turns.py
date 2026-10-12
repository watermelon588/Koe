"""Phase 5: a WhatsApp message goes through the shared agent and gets a reply (Meta's API faked with respx)."""
import asyncio
import json
import os
from types import SimpleNamespace

os.environ.setdefault("GEMINI_API_KEY", "test")

import httpx  # noqa: E402
import pytest  # noqa: E402
import respx  # noqa: E402
from google.genai import types  # noqa: E402

from koe import whatsapp  # noqa: E402
from koe.config import settings  # noqa: E402

ME = "919876543210"
SEND = f"{whatsapp.GRAPH}/PHONE/messages"


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(settings, "allowed_whatsapp_numbers", ME)
    monkeypatch.setattr(settings, "whatsapp_token", "TOKEN")
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "PHONE")
    whatsapp.CHATS.clear()
    whatsapp._http = None  # each test runs its own event loop; a client can't cross loops
    async def no_store(*args, **kwargs):
        return None
    monkeypatch.setattr(whatsapp.store, "record_best_effort", no_store)
    yield
    whatsapp.CHATS.clear()
    whatsapp._http = None


def fake_agent(monkeypatch, reply):
    """Replaces the text agent; records what it was asked."""
    asked = []
    async def chat(text, history, context, client):
        asked.append(text)
        return reply(text) if callable(reply) else reply
    monkeypatch.setattr(whatsapp.text_agent, "chat", chat)
    return asked


def sent_messages(route):
    return [json.loads(call.request.content) for call in route.calls]


def text(body):
    return {"from": ME, "id": "wamid.1", "type": "text", "text": {"body": body}}


@respx.mock
def test_text_message_is_answered_through_the_agent(monkeypatch):
    asked = fake_agent(monkeypatch, {"text": "You're free from 7 to 8."})
    route = respx.post(SEND).mock(return_value=httpx.Response(200, json={"messages": [{"id": "wamid.r"}]}))
    asyncio.run(whatsapp.handle_message(text("am I free at 7?")))
    assert asked == ["am I free at 7?"]
    (sent,) = sent_messages(route)
    assert sent["to"] == ME and sent["type"] == "text" and sent["text"]["body"] == "You're free from 7 to 8."


@respx.mock
def test_a_proposal_comes_with_confirm_and_cancel_buttons(monkeypatch):
    fake_agent(monkeypatch, {"text": "Book 7:00 to 7:30 with Rahul. Confirm?", "pending_action": {"id": "act-1", "summary": "x"}})
    route = respx.post(SEND).mock(return_value=httpx.Response(200, json={"messages": [{"id": "wamid.r"}]}))
    asyncio.run(whatsapp.handle_message(text("book a call with rahul at 7")))
    (sent,) = sent_messages(route)
    assert sent["type"] == "interactive" and sent["interactive"]["type"] == "button"
    assert sent["interactive"]["body"]["text"].startswith("Book 7:00")
    buttons = [b["reply"] for b in sent["interactive"]["action"]["buttons"]]
    assert buttons == [{"id": "approve:act-1", "title": "Confirm"}, {"id": "reject:act-1", "title": "Cancel"}]


@respx.mock
def test_a_long_proposal_is_sent_in_full_before_the_buttons(monkeypatch):
    long = "Post comment to PR 42:\n" + "x" * 1500  # over the 1024-character button body limit
    fake_agent(monkeypatch, {"text": long, "pending_action": {"id": "act-2", "summary": "x"}})
    route = respx.post(SEND).mock(return_value=httpx.Response(200, json={"messages": [{"id": "wamid.r"}]}))
    asyncio.run(whatsapp.handle_message(text("comment on 42")))
    full, buttons = sent_messages(route)
    assert full["text"]["body"] == long  # nothing hidden before approving
    assert buttons["interactive"]["body"]["text"] == "Confirm or cancel the proposal above."


@respx.mock
def test_a_tapped_button_resolves_exactly_that_action(monkeypatch):
    decided = []
    async def confirm(context, approve, action_id=None):
        decided.append((approve, action_id))
        return {"status": "executed", "title": "Call with Rahul"}
    monkeypatch.setattr(whatsapp.agent, "confirm", confirm)
    route = respx.post(SEND).mock(return_value=httpx.Response(200, json={"messages": [{"id": "wamid.r"}]}))
    tap = {"from": ME, "id": "wamid.2", "type": "interactive",
           "interactive": {"type": "button_reply", "button_reply": {"id": "approve:act-1", "title": "Confirm"}}}
    asyncio.run(whatsapp.handle_message(tap))
    assert decided == [(True, "act-1")]
    assert sent_messages(route)[0]["text"]["body"].startswith("Saved: Call with Rahul")


@respx.mock
def test_a_voice_note_is_downloaded_transcribed_and_answered(monkeypatch):
    asked = fake_agent(monkeypatch, {"text": "Yes, 7 is free."})
    respx.get(f"{whatsapp.GRAPH}/media-1").mock(return_value=httpx.Response(200, json={
        "url": "https://lookaside.fbsbx.com/whatsapp_business/attachments/?mid=1", "mime_type": "audio/ogg; codecs=opus", "file_size": "5"}))
    download = respx.get("https://lookaside.fbsbx.com/whatsapp_business/attachments/?mid=1").mock(
        return_value=httpx.Response(200, content=b"OGGS!"))
    respx.post(SEND).mock(return_value=httpx.Response(200, json={"messages": [{"id": "wamid.r"}]}))
    heard = []
    async def generate_content(model, contents):
        heard.append(contents[0])
        return SimpleNamespace(text=" Am I free at seven? ")
    monkeypatch.setattr(whatsapp, "gemini", lambda: SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))))

    asyncio.run(whatsapp.handle_message({"from": ME, "id": "wamid.3", "type": "audio", "audio": {"id": "media-1"}}))

    assert download.calls[0].request.headers["authorization"] == "Bearer TOKEN"
    assert heard[0].inline_data.data == b"OGGS!" and heard[0].inline_data.mime_type == "audio/ogg"
    assert asked == ["Am I free at seven?"]


@respx.mock
def test_the_token_is_never_sent_to_a_media_url_off_meta(monkeypatch):
    fake_agent(monkeypatch, {"text": "unused"})
    respx.get(f"{whatsapp.GRAPH}/media-2").mock(return_value=httpx.Response(200, json={"url": "https://evil.example/a.ogg", "mime_type": "audio/ogg"}))
    evil = respx.get("https://evil.example/a.ogg")
    route = respx.post(SEND).mock(return_value=httpx.Response(200, json={"messages": [{"id": "wamid.r"}]}))
    asyncio.run(whatsapp.handle_message({"from": ME, "id": "wamid.4", "type": "audio", "audio": {"id": "media-2"}}))
    assert evil.call_count == 0
    assert "went wrong" in sent_messages(route)[0]["text"]["body"]


@respx.mock
def test_messages_from_one_sender_are_handled_one_at_a_time(monkeypatch):
    running, peak, order = 0, 0, []
    async def chat(text, history, context, client):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.02)
        order.append(text)
        running -= 1
        return {"text": "ok"}
    monkeypatch.setattr(whatsapp.text_agent, "chat", chat)
    respx.post(SEND).mock(return_value=httpx.Response(200, json={"messages": [{"id": "wamid.r"}]}))
    async def both():
        await asyncio.gather(whatsapp.handle_message(text("first")), whatsapp.handle_message(text("second")))
    asyncio.run(both())
    assert peak == 1 and order == ["first", "second"]


@respx.mock
def test_other_message_types_get_a_polite_reply(monkeypatch):
    asked = fake_agent(monkeypatch, {"text": "unused"})
    route = respx.post(SEND).mock(return_value=httpx.Response(200, json={"messages": [{"id": "wamid.r"}]}))
    asyncio.run(whatsapp.handle_message({"from": ME, "id": "wamid.5", "type": "image", "image": {"id": "i"}}))
    assert asked == [] and "text messages and voice notes" in sent_messages(route)[0]["text"]["body"]


def test_trimming_never_separates_a_tool_call_from_its_response(monkeypatch):
    monkeypatch.setattr(whatsapp, "HISTORY_ITEMS", 4)
    say = lambda role, t: types.Content(role=role, parts=[types.Part.from_text(text=t)])  # noqa: E731
    call = types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="github_my_prs", args={}))])
    answer = types.Content(role="user", parts=[types.Part(function_response=types.FunctionResponse(name="github_my_prs", response={}))])
    history = [say("user", "hi"), say("model", "hello"), say("user", "my prs?"), call, answer, say("model", "one PR")]
    whatsapp.trim(history)
    assert history[0].parts[0].text == "my prs?"  # cut at a user message, not between call and response
    assert len(history) == 4


@respx.mock
def test_a_busy_gemini_gets_a_plain_answer(monkeypatch):
    from google.genai import errors
    async def chat(text, history, context, client):
        raise errors.ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})
    monkeypatch.setattr(whatsapp.text_agent, "chat", chat)
    route = respx.post(SEND).mock(return_value=httpx.Response(200, json={"messages": [{"id": "wamid.r"}]}))
    asyncio.run(whatsapp.handle_message(text("hi")))
    assert sent_messages(route)[0]["text"]["body"].startswith("Gemini is busy")
