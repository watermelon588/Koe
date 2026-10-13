"""Koe app channel (SPEC §14): the installable web app on the phone. A WhatsApp-style chat with Koe
(text and voice notes both ways, Confirm/Cancel approvals) plus push notifications. No store, no Meta.

  GET  /api/app/messages?after=ID   history (newest last)
  POST /api/app/messages            {"text"} → your message + Koe's reply
  POST /api/app/voice               raw WAV body → your voice note (+ transcript) + Koe's spoken reply
  GET  /api/app/voice/{name}        a stored voice note (audio lives in the database)
  POST /api/app/approvals/{id}      {"approve": bool} → resolve a proposal
  GET  /api/app/push/key            VAPID public key for the browser's PushManager.subscribe
  POST /api/app/push/subscribe      the browser's PushSubscription JSON
  POST /api/app/push/test           a test notification to every device → {"sent": n}

Every endpoint needs `Authorization: Bearer <KOE_ACCESS_TOKEN>`: the phone reaches this through a public tunnel.
Web Push: https://developer.mozilla.org/en-US/docs/Web/API/Push_API · pywebpush: https://github.com/web-push-libs/pywebpush
"""
import asyncio
import contextlib
import hmac
import io
import json
import logging
import re
import wave
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from google.genai import errors
from py_vapid import Vapid02, b64urlencode
from pydantic import BaseModel
from pywebpush import WebPushException, webpush_async

from koe import agent, text_agent, voice_call, whatsapp
from koe.config import settings
from koe.db import sql

log = logging.getLogger("koe.app")
DATA = Path(__file__).resolve().parent.parent / "data"  # backend/data, git-ignored: vapid.pem fallback
MAX_VOICE_BYTES = 3 * 1024 * 1024  # ~90 s of 16 kHz mono 16-bit WAV
MAX_TEXT = 2000
VOICE_NAME = re.compile(r"^[0-9a-f]{32}\.wav$")  # only names we generated; no paths
SPEAK_PROMPT = "Read the user's message aloud exactly as written, in a warm, natural voice. Say nothing else."
BUSY = "Gemini is busy right now. Please try again in a minute."


def authorized(authorization: str = Header(default="")) -> None:
    token = authorization.removeprefix("Bearer ").strip()
    if not settings.koe_access_token or not hmac.compare_digest(token.encode(), settings.koe_access_token.encode()):
        raise HTTPException(401, "Enter the Koe access token from backend/.env.")


router = APIRouter(prefix="/api/app", dependencies=[Depends(authorized)])


# ── Storage: koe/db.py (Neon, or SQLite locally). Every row has an owner (ACCOUNTS_SPEC.md). ─────────

def owner() -> str:
    return settings.koe_owner_id  # ponytail: one owner until sign-in passes the user in (ACCOUNTS_SPEC.md task 3)


def _public(row: dict) -> dict:
    return {k: v for k, v in row.items() if k != "owner_id"}


async def add_message(role: str, text: str, voice: str | None = None, action_id: str | None = None) -> dict:
    rows = await sql("insert into koe_app_messages (owner_id, ts, role, text, voice, action_id) "
                     "values (%s, %s, %s, %s, %s, %s) returning *",
                     owner(), datetime.now(timezone.utc).isoformat(), role, text, voice, action_id)
    return _public(rows[0])


async def list_messages(after: int = 0, limit: int = 200) -> list[dict]:
    rows = await sql("select * from (select * from koe_app_messages where owner_id = %s and id > %s "
                     "order by id desc limit %s) newest order by id", owner(), after, limit)
    return [_public(r) for r in rows]


async def set_action_status(action_id: str, status: str) -> None:
    await sql("update koe_app_messages set action_status = %s where owner_id = %s and action_id = %s",
              status, owner(), action_id)


async def save_voice(audio: bytes) -> str:
    name = f"{uuid4().hex}.wav"
    await sql("insert into koe_app_voice (name, owner_id, created, audio) values (%s, %s, %s, %s)",
              name, owner(), datetime.now(timezone.utc).isoformat(), audio)
    return name


# ── The conversation ──────────────────────────────────────────────────────────────────────────────

CHAT = whatsapp.Chat(context=agent.Conversation("app"))  # one user, one conversation; the lock keeps turns in order
_background: set[asyncio.Task] = set()


async def reply(text: str, spoken: bool) -> dict:
    async with CHAT.lock:
        result = await text_agent.chat(text, CHAT.history, CHAT.context, whatsapp.gemini())
        whatsapp.trim(CHAT.history)
    voice = None
    if spoken:
        try:
            voice = await asyncio.wait_for(speak(result["text"]), timeout=30)
        except Exception:
            log.warning("spoken reply failed; sending text only", exc_info=True)
    pending = result.get("pending_action")
    message = await add_message("koe", result["text"], voice=voice, action_id=pending["id"] if pending else None)
    later(notify(message["text"], tag="koe-reply"))  # the app skips it if the chat is already on screen
    return message


async def speak(text: str) -> str:
    """Koe's voice note: Gemini Live (the call voice) reads the reply; saved as 24 kHz mono WAV."""
    pcm = bytearray()
    config = {"response_modalities": ["AUDIO"], "system_instruction": SPEAK_PROMPT}
    async with whatsapp.gemini().aio.live.connect(model=voice_call.LIVE_MODEL, config=config) as session:
        await session.send_realtime_input(text=text)
        async for msg in session.receive():
            content = msg.server_content
            if content and content.model_turn:
                pcm += b"".join(p.inline_data.data for p in content.model_turn.parts if p.inline_data)
            if content and content.turn_complete:
                break
    if not pcm:
        raise RuntimeError("no audio")
    wav = io.BytesIO()
    with wave.open(wav, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(24000)
        out.writeframes(bytes(pcm))
    return await save_voice(wav.getvalue())


def later(coro) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)  # keep a reference so it isn't garbage-collected mid-flight
    task.add_done_callback(_background.discard)


class TextIn(BaseModel):
    text: str


class Decision(BaseModel):
    approve: bool


@router.get("/messages")
async def get_messages(after: int = 0):
    return {"messages": await list_messages(after)}


@router.post("/messages")
async def post_message(body: TextIn):
    text = body.text.strip()[:MAX_TEXT]
    if not text:
        raise HTTPException(400, "Type a message first.")
    mine = await add_message("you", text)
    return {"messages": [mine, await reply(text, spoken=False)]}


@router.post("/voice")
async def post_voice(request: Request):
    audio = await request.body()
    if len(audio) > MAX_VOICE_BYTES:
        raise HTTPException(413, "Voice notes can be up to about 90 seconds.")
    if audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        raise HTTPException(415, "Send the voice note as WAV audio.")
    name = await save_voice(audio)
    try:
        heard = await whatsapp.transcribe(audio, "audio/wav")
    except Exception as exc:
        log.warning("transcription failed", exc_info=True)
        busy = isinstance(exc, errors.APIError) and exc.code in {429, 503}
        mine = await add_message("you", "", voice=name)
        return {"messages": [mine, await add_message("koe", BUSY if busy else "I couldn't hear that one. Try again?")]}
    mine = await add_message("you", heard, voice=name)
    if not heard:
        return {"messages": [mine, await add_message("koe", "I couldn't make out that voice note. Could you try again, or type it?")]}
    return {"messages": [mine, await reply(heard, spoken=True)]}


@router.get("/voice/{name}")
async def get_voice(name: str):
    rows = await sql("select audio from koe_app_voice where name = %s and owner_id = %s", name, owner()) \
        if VOICE_NAME.match(name) else []
    if not rows:
        raise HTTPException(404, "No such voice note.")
    # A note never changes once saved: the phone may keep it, but never a shared cache.
    return Response(bytes(rows[0]["audio"]), media_type="audio/wav",
                    headers={"Cache-Control": "private, max-age=31536000, immutable"})


@router.post("/approvals/{action_id}")
async def decide(action_id: str, body: Decision):
    async with CHAT.lock:
        result = await agent.confirm(CHAT.context, body.approve, action_id)
    status = result.get("status") or "unavailable"  # e.g. expired, or forgotten after a server restart
    await set_action_status(action_id, status)
    return {"messages": [await add_message("koe", text_agent.approval_text(result))], "action": {"id": action_id, "status": status}}


# ── Push notifications ────────────────────────────────────────────────────────────────────────────

def vapid() -> Vapid02:
    """The server's push identity: VAPID_PRIVATE_KEY, else generated once into backend/data.
    Losing it means every device must turn notifications on again."""
    if settings.vapid_private_key:
        return Vapid02.from_string(settings.vapid_private_key)
    path = DATA / "vapid.pem"
    if not path.exists():
        DATA.mkdir(parents=True, exist_ok=True)
        key = Vapid02()
        key.generate_keys()
        key.save_key(str(path))
    return Vapid02.from_file(str(path))


@router.get("/push/key")
def push_key():
    raw = vapid().public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return {"key": b64urlencode(raw)}


@router.post("/push/subscribe")
async def push_subscribe(subscription: dict):
    endpoint = subscription.get("endpoint", "")
    keys = subscription.get("keys") or {}
    if not endpoint.startswith("https://") or not keys.get("p256dh") or not keys.get("auth"):
        raise HTTPException(400, "Not a push subscription.")
    await sql("insert into koe_app_push (endpoint, owner_id, subscription) values (%s, %s, %s) on conflict (endpoint) "
              "do update set owner_id = excluded.owner_id, subscription = excluded.subscription",
              endpoint, owner(), json.dumps(subscription))
    return {"ok": True}


@router.post("/push/test")
async def push_test():
    """The install page's end-to-end check: did a real notification reach this phone?"""
    return {"sent": await notify("Notifications work. Koe's replies and GitHub alerts will arrive like this.", tag="koe-test")}


async def notify(body: str, title: str = "Koe", tag: str = "koe") -> int:
    """Push to every subscribed device; returns how many accepted it.
    Gone subscriptions (404/410) are removed; other failures are logged."""
    subs = [(r["endpoint"], json.loads(r["subscription"]))
            for r in await sql("select endpoint, subscription from koe_app_push where owner_id = %s", owner())]
    if not subs:
        return 0
    sent = 0
    payload = json.dumps({"title": title, "body": body[:300], "tag": tag, "url": "/#chat"})
    key = vapid()
    for endpoint, sub in subs:
        try:
            await webpush_async(sub, payload, vapid_private_key=key, vapid_claims={"sub": settings.koe_push_contact}, ttl=3600)
            sent += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status", None) or getattr(exc.response, "status_code", None)
            if status in {404, 410}:
                await sql("delete from koe_app_push where endpoint = %s", endpoint)
            else:
                log.warning("push failed (%s)", status)
        except Exception:
            log.warning("push failed", exc_info=True)
    return sent


async def alert(text: str) -> None:
    """A GitHub alert: saved in the chat and pushed to the phone."""
    with contextlib.suppress(Exception):
        await add_message("alert", text)
    await notify(text, title="GitHub", tag="koe-alert")
