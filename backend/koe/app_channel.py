"""Koe app channel (SPEC §14): the installable web app on the phone. A WhatsApp-style chat with Koe
(text and voice notes both ways, Confirm/Cancel approvals) plus push notifications. No store, no Meta.

  GET  /api/app/messages?after=ID   history (newest last)
  POST /api/app/messages            {"text"} → your message + Koe's reply
  POST /api/app/voice               raw WAV body → your voice note (+ transcript) + Koe's spoken reply
  GET  /api/app/voice/{name}        a stored voice note
  POST /api/app/approvals/{id}      {"approve": bool} → resolve a proposal
  GET  /api/app/push/key            VAPID public key for the browser's PushManager.subscribe
  POST /api/app/push/subscribe      the browser's PushSubscription JSON

Every endpoint needs `Authorization: Bearer <KOE_ACCESS_TOKEN>`: the phone reaches this through a public tunnel.
Web Push: https://developer.mozilla.org/en-US/docs/Web/API/Push_API · pywebpush: https://github.com/web-push-libs/pywebpush
"""
import asyncio
import contextlib
import hmac
import json
import logging
import re
import sqlite3
import wave
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse
from google.genai import errors
from py_vapid import Vapid02, b64urlencode
from pydantic import BaseModel
from pywebpush import WebPushException, webpush_async

from koe import agent, text_agent, voice_call, whatsapp
from koe.config import settings

log = logging.getLogger("koe.app")
DATA = Path(__file__).resolve().parent.parent / "data"  # backend/data, git-ignored
VOICE = DATA / "voice"
DB = DATA / "app.db"
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


# ── Storage: one SQLite file, opened per call (tiny and fast for one user) ─────────────────────────

def db() -> sqlite3.Connection:
    VOICE.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("""create table if not exists messages (
        id integer primary key autoincrement, ts text not null, role text not null,
        text text not null default '', voice text, action_id text, action_status text)""")
    con.execute("create table if not exists push (endpoint text primary key, subscription text not null)")
    return con


def add_message(role: str, text: str, voice: str | None = None, action_id: str | None = None) -> dict:
    with closing(db()) as con, con:
        cur = con.execute("insert into messages (ts, role, text, voice, action_id) values (?, ?, ?, ?, ?)",
                          (datetime.now(timezone.utc).isoformat(), role, text, voice, action_id))
        return dict(con.execute("select * from messages where id = ?", (cur.lastrowid,)).fetchone())


def list_messages(after: int = 0, limit: int = 200) -> list[dict]:
    with closing(db()) as con:
        rows = con.execute("select * from (select * from messages where id > ? order by id desc limit ?) order by id",
                           (after, limit)).fetchall()
    return [dict(r) for r in rows]


def set_action_status(action_id: str, status: str) -> None:
    with closing(db()) as con, con:
        con.execute("update messages set action_status = ? where action_id = ?", (status, action_id))


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
    message = add_message("koe", result["text"], voice=voice, action_id=pending["id"] if pending else None)
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
    name = f"{uuid4().hex}.wav"
    with wave.open(str(VOICE / name), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(24000)
        out.writeframes(bytes(pcm))
    return name


def later(coro) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)  # keep a reference so it isn't garbage-collected mid-flight
    task.add_done_callback(_background.discard)


class TextIn(BaseModel):
    text: str


class Decision(BaseModel):
    approve: bool


@router.get("/messages")
def get_messages(after: int = 0):
    return {"messages": list_messages(after)}


@router.post("/messages")
async def post_message(body: TextIn):
    text = body.text.strip()[:MAX_TEXT]
    if not text:
        raise HTTPException(400, "Type a message first.")
    mine = add_message("you", text)
    return {"messages": [mine, await reply(text, spoken=False)]}


@router.post("/voice")
async def post_voice(request: Request):
    audio = await request.body()
    if len(audio) > MAX_VOICE_BYTES:
        raise HTTPException(413, "Voice notes can be up to about 90 seconds.")
    if audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        raise HTTPException(415, "Send the voice note as WAV audio.")
    name = f"{uuid4().hex}.wav"
    VOICE.mkdir(parents=True, exist_ok=True)
    (VOICE / name).write_bytes(audio)
    try:
        heard = await whatsapp.transcribe(audio, "audio/wav")
    except Exception as exc:
        log.warning("transcription failed", exc_info=True)
        busy = isinstance(exc, errors.APIError) and exc.code in {429, 503}
        mine = add_message("you", "", voice=name)
        return {"messages": [mine, add_message("koe", BUSY if busy else "I couldn't hear that one. Try again?")]}
    mine = add_message("you", heard, voice=name)
    if not heard:
        return {"messages": [mine, add_message("koe", "I couldn't make out that voice note. Could you try again, or type it?")]}
    return {"messages": [mine, await reply(heard, spoken=True)]}


@router.get("/voice/{name}")
def get_voice(name: str):
    if not VOICE_NAME.match(name) or not (VOICE / name).is_file():
        raise HTTPException(404, "No such voice note.")
    return FileResponse(VOICE / name, media_type="audio/wav")


@router.post("/approvals/{action_id}")
async def decide(action_id: str, body: Decision):
    async with CHAT.lock:
        result = await agent.confirm(CHAT.context, body.approve, action_id)
    status = result.get("status") or "unavailable"  # e.g. expired, or forgotten after a server restart
    set_action_status(action_id, status)
    return {"messages": [add_message("koe", text_agent.approval_text(result))], "action": {"id": action_id, "status": status}}


# ── Push notifications ────────────────────────────────────────────────────────────────────────────

def vapid() -> Vapid02:
    """The server's push identity, generated once and kept in backend/data (losing it means re-subscribing)."""
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
def push_subscribe(subscription: dict):
    endpoint = subscription.get("endpoint", "")
    keys = subscription.get("keys") or {}
    if not endpoint.startswith("https://") or not keys.get("p256dh") or not keys.get("auth"):
        raise HTTPException(400, "Not a push subscription.")
    with closing(db()) as con, con:
        con.execute("insert or replace into push (endpoint, subscription) values (?, ?)", (endpoint, json.dumps(subscription)))
    return {"ok": True}


async def notify(body: str, title: str = "Koe", tag: str = "koe") -> None:
    """Push to every subscribed device. Gone subscriptions (404/410) are removed; other failures are logged."""
    with closing(db()) as con:
        subs = [(r["endpoint"], json.loads(r["subscription"])) for r in con.execute("select * from push")]
    if not subs:
        return
    payload = json.dumps({"title": title, "body": body[:300], "tag": tag, "url": "/#chat"})
    key = vapid()
    for endpoint, sub in subs:
        try:
            await webpush_async(sub, payload, vapid_private_key=key, vapid_claims={"sub": settings.koe_push_contact}, ttl=3600)
        except WebPushException as exc:
            status = getattr(exc.response, "status", None) or getattr(exc.response, "status_code", None)
            if status in {404, 410}:
                with closing(db()) as con, con:
                    con.execute("delete from push where endpoint = ?", (endpoint,))
            else:
                log.warning("push failed (%s)", status)
        except Exception:
            log.warning("push failed", exc_info=True)


async def alert(text: str) -> None:
    """A GitHub alert: saved in the chat and pushed to the phone."""
    with contextlib.suppress(Exception):
        add_message("alert", text)
    await notify(text, title="GitHub", tag="koe-alert")
