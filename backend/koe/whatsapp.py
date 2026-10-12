"""WhatsApp channel (SPEC §2, §9): Meta webhook in, Send API out.

Webhooks: https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks
  GET  = one-time verification handshake (echo hub.challenge if hub.verify_token matches).
  POST = events, signed with X-Hub-Signature-256 = "sha256=" + HMAC-SHA256(app secret, raw body).
Send API: POST graph.facebook.com/<ver>/<phone-number-id>/messages (same version as scripts/smoke.py).
"""
import hashlib
import hmac
import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse

from koe.config import settings

log = logging.getLogger("koe.whatsapp")
router = APIRouter()
GRAPH = "https://graph.facebook.com/v25.0"


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


def handle_message(msg: dict) -> None:
    # ponytail: logs only. Phase 5 wires this to the agent's text loop (Phase 2) once it exists:
    # text/audio -> agent -> reply, button_reply -> resolve pending action.
    log.info("WhatsApp %s message %s from %s", msg.get("type"), msg.get("id"), msg.get("from"))


@router.post("/webhooks/whatsapp")
async def receive(request: Request, background: BackgroundTasks):
    body = await request.body()
    if not valid_signature(settings.whatsapp_app_secret, body, request.headers.get("x-hub-signature-256")):
        raise HTTPException(401, "bad signature")
    for msg in inbound_messages(await request.json()):
        background.add_task(handle_message, msg)  # runs after the 200 is sent: Meta wants a fast ack
    return {"ok": True}


async def send_text(to: str, body: str) -> str:
    """Send a free-form text; returns Meta's message id. Only works inside the 24 h window
    after the user last messaged us. Note "accepted" here isn't "delivered" (see smoke.py)."""
    if to not in allowed_numbers():
        raise ValueError("refusing to message a number outside ALLOWED_WHATSAPP_NUMBERS")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{GRAPH}/{settings.whatsapp_phone_number_id}/messages",
            headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
            json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body}},
        )
    r.raise_for_status()
    return r.json()["messages"][0]["id"]
