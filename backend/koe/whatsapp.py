"""WhatsApp channel (SPEC §2, §5, §9): Meta webhook in, Send API out.

Webhooks: https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks
  GET  = one-time verification handshake (echo hub.challenge if hub.verify_token matches).
  POST = events, signed with X-Hub-Signature-256 = "sha256=" + HMAC-SHA256(app secret, raw body).
Send API: POST graph.facebook.com/<ver>/<phone-number-id>/messages (same version as scripts/smoke.py).

A message's journey: webhook (200 at once) → background: one message at a time per sender →
text, or voice note (download → Gemini transcribes) → the shared text agent (tools + approval gate) →
reply, with Confirm / Cancel buttons when Koe proposes a write. A tapped button resolves that exact action.
"""
import asyncio
import contextlib
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse
from google import genai
from google.genai import errors, types

from koe import agent, store, text_agent
from koe.config import settings

log = logging.getLogger("koe.whatsapp")
router = APIRouter()
GRAPH = "https://graph.facebook.com/v25.0"
MAX_AUDIO_BYTES = 16 * 1024 * 1024  # WhatsApp's own audio limit ("Supported media types", Media API docs)
MAX_TEXT = 4096  # WhatsApp text message body limit
MAX_BUTTON_BODY = 1024  # interactive reply-buttons body limit
HISTORY_ITEMS = 40  # model Contents kept per sender, so a long chat can't grow the prompt forever
# Media URLs come from Meta's API; our token is only ever sent to Meta's own hosts.
MEDIA_HOSTS = ("fbsbx.com", "facebook.com", "fbcdn.net", "whatsapp.net")


def valid_signature(secret: str, body: bytes, header: str | None) -> bool:
    """GitHub and Meta sign webhooks the same way. No secret configured = reject (fail closed),
    because anyone can compute an HMAC with an empty key."""
    if not secret or not header:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)  # constant time: no timing leak


def allowed_numbers() -> list[str]:
    return [n.strip() for n in settings.allowed_whatsapp_numbers.split(",") if n.strip()]


@router.get("/webhooks/whatsapp")
def verify(request: Request):
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and settings.whatsapp_verify_token and \
            hmac.compare_digest(q.get("hub.verify_token", ""), settings.whatsapp_verify_token):
        return PlainTextResponse(q.get("hub.challenge", ""))
    raise HTTPException(403, "verify token mismatch")


def inbound_messages(payload: dict) -> list[dict]:
    """Flatten Meta's entry[].changes[].value.messages[] and drop senders outside the allow-list.
    Delivery receipts (value.statuses) carry no messages, so they fall out here too."""
    allowed = allowed_numbers()
    msgs = [m for e in payload.get("entry", []) for c in e.get("changes", [])
            for m in c.get("value", {}).get("messages", [])]
    for m in msgs:
        if m.get("from") not in allowed:
            log.warning("ignored WhatsApp message from non-allow-listed sender")
    return [m for m in msgs if m.get("from") in allowed]


@router.post("/webhooks/whatsapp")
async def receive(request: Request, background: BackgroundTasks):
    received = time.perf_counter()
    body = await request.body()
    if not valid_signature(settings.whatsapp_app_secret, body, request.headers.get("x-hub-signature-256")):
        raise HTTPException(401, "bad signature")
    for msg in inbound_messages(await request.json()):
        background.add_task(handle_message, msg, received)  # runs after the 200 is sent: Meta wants a fast ack
    return {"ok": True}


# ── Conversations ──────────────────────────────────────────────────────────────

@dataclass
class Chat:
    context: agent.Conversation = field(default_factory=lambda: agent.Conversation("whatsapp"))
    history: list = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


# ponytail: one in-memory chat per sender; a restart forgets the history and any pending button
# (the user just asks again). Phase 6 adds the cross-channel memory summary.
CHATS: dict[str, Chat] = {}
_client: genai.Client | None = None
_http: httpx.AsyncClient | None = None


def http() -> httpx.AsyncClient:
    """One reused client: a fresh one per message spent ~0.6 s on TLS setup (measured on this laptop)."""
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=20)
    return _http


def gemini() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


async def handle_message(msg: dict, received: float | None = None) -> None:
    sender = msg["from"]
    chat = CHATS.setdefault(sender, Chat())
    async with chat.lock:  # SPEC §9: one message at a time per sender; the rest wait their turn
        stages = {"received": received if received is not None else time.perf_counter()}
        try:
            await _answer(sender, msg, chat, stages)
        except Exception as exc:
            log.exception("WhatsApp message %s failed", msg.get("id"))
            # Free-tier Gemini answers 503 "high demand" or 429 at busy times (seen in testing): say so plainly.
            busy = isinstance(exc, errors.APIError) and exc.code in {429, 503}
            with contextlib.suppress(Exception):
                await send_text(sender, "Gemini is busy right now. Please try again in a minute." if busy else
                                "Sorry, something went wrong on my side. Please try again.")
            return
        ms = {k: round((v - stages["received"]) * 1000) for k, v in stages.items() if k != "received"}
        log.info("WhatsApp turn latency (ms after webhook): %s", ms)
        await store.record_best_effort("whatsapp", chat.context.session_id, "latency", "WhatsApp turn", {"stages_ms": ms})


async def _answer(sender: str, msg: dict, chat: Chat, stages: dict) -> None:
    kind = msg.get("type")
    if kind == "interactive":
        reply_id = msg.get("interactive", {}).get("button_reply", {}).get("id", "")
        verdict, _, action_id = reply_id.partition(":")
        if verdict in {"approve", "reject"} and action_id:
            # A tapped button resolves exactly the action it was attached to, through the same gate as "yes".
            result = await agent.confirm(chat.context, verdict == "approve", action_id)
            stages["tools_done"] = time.perf_counter()
            await send_text(sender, text_agent.approval_text(result))
            stages["reply_sent"] = time.perf_counter()
            return
    if kind == "text":
        text = msg.get("text", {}).get("body", "")
    elif kind == "audio":
        audio, mime = await download_media(msg.get("audio", {}).get("id", ""))
        stages["media_downloaded"] = time.perf_counter()
        text = await transcribe(audio, mime)
        stages["transcribed"] = time.perf_counter()
        if not text:
            await send_text(sender, "I couldn't make out that voice note. Could you try again, or type it?")
            return
    else:
        await send_text(sender, "I can read text messages and voice notes for now.")
        return

    result = await text_agent.chat(text, chat.history, chat.context, gemini())
    trim(chat.history)
    stages["model_done"] = time.perf_counter()  # includes any tools the model called
    pending = result.get("pending_action")
    if pending:
        await send_buttons(sender, result["text"], pending["id"])
    else:
        await send_text(sender, result["text"])
    stages["reply_sent"] = time.perf_counter()


def trim(history: list) -> None:
    """Keep the last HISTORY_ITEMS Contents, cutting only where a user *message* starts, so a
    function call is never separated from its response (the model rejects that)."""
    if len(history) <= HISTORY_ITEMS:
        return
    for i in range(len(history) - HISTORY_ITEMS, len(history)):
        c = history[i]
        if c.role == "user" and c.parts and all(p.text is not None for p in c.parts):
            del history[:i]
            return


# ── Voice notes ────────────────────────────────────────────────────────────────

async def download_media(media_id: str) -> tuple[bytes, str]:
    """Media API: GET /<MEDIA_ID> → a URL valid for 5 minutes → GET it with the same token.
    https://developers.facebook.com/documentation/business-messaging/whatsapp/business-phone-numbers/media"""
    if not media_id:
        raise ValueError("audio message without a media id")
    headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}
    meta = await http().get(f"{GRAPH}/{media_id}", headers=headers)
    meta.raise_for_status()
    info = meta.json()
    url = urlparse(info.get("url", ""))
    host = url.hostname or ""
    if url.scheme != "https" or not any(host == h or host.endswith("." + h) for h in MEDIA_HOSTS):
        raise ValueError("media URL is not on a Meta host; refusing to send the token there")
    if int(info.get("file_size") or 0) > MAX_AUDIO_BYTES:
        raise ValueError("voice note larger than WhatsApp's 16 MB limit")
    audio = await http().get(info["url"], headers=headers)
    audio.raise_for_status()
    if len(audio.content) > MAX_AUDIO_BYTES:
        raise ValueError("voice note larger than WhatsApp's 16 MB limit")
    return audio.content, info.get("mime_type") or "audio/ogg"


async def transcribe(audio: bytes, mime: str) -> str:
    """Gemini understands audio parts directly (WhatsApp voice notes are OGG/Opus).
    https://ai.google.dev/gemini-api/docs/audio
    ponytail: transcribe, then run the text loop (two model calls). One call with the audio part in the
    conversation would be faster; this keeps one agent path, and "yes"/"no" voice notes work for free."""
    response = await gemini().aio.models.generate_content(
        model=settings.gemini_text_model,
        contents=[types.Part.from_bytes(data=audio, mime_type=mime.split(";")[0].strip() or "audio/ogg"),
                  "Transcribe this voice note exactly, in the language spoken. Reply with the transcript only."],
    )
    return (response.text or "").strip()


# ── Sending ────────────────────────────────────────────────────────────────────

async def _send(to: str, payload: dict) -> str:
    """POST one message; returns Meta's message id. Note "accepted" here isn't "delivered" (see smoke.py)."""
    if to not in allowed_numbers():
        raise ValueError("refusing to message a number outside ALLOWED_WHATSAPP_NUMBERS")
    r = await http().post(
        f"{GRAPH}/{settings.whatsapp_phone_number_id}/messages",
        headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
        json={"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, **payload},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["messages"][0]["id"]


async def send_text(to: str, body: str) -> str:
    """A free-form text. Only works inside the 24 h window after the user last messaged us."""
    if len(body) > MAX_TEXT:
        body = body[: MAX_TEXT - 1] + "…"
    return await _send(to, {"type": "text", "text": {"body": body}})


async def send_buttons(to: str, body: str, action_id: str) -> str:
    """Koe's reply plus Confirm / Cancel reply buttons for one pending action (SPEC §5).
    https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/interactive-reply-buttons-messages
    The full proposal must be readable before approving, so a long one goes as its own text first."""
    if len(body) > MAX_BUTTON_BODY:
        await send_text(to, body)
        body = "Confirm or cancel the proposal above."
    return await _send(to, {"type": "interactive", "interactive": {
        "type": "button",
        "body": {"text": body},
        "action": {"buttons": [
            {"type": "reply", "reply": {"id": f"approve:{action_id}", "title": "Confirm"}},
            {"type": "reply", "reply": {"id": f"reject:{action_id}", "title": "Cancel"}},
        ]},
    }})
