"""Phase 0 smoke tests: one real call per service, to prove each key works.

Run from backend/:
    uv run python -m scripts.smoke              # all services
    uv run python -m scripts.smoke gemini live  # just some

A service with no credentials yet is SKIPPED, not failed.
"""
import asyncio
import sys
import tempfile
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

import httpx

from koe.config import settings

# Verified 2026-10-12 on https://ai.google.dev/gemini-api/docs/models (both stable, free tier).
TEXT_MODEL = "gemini-3.8-flash"
LIVE_MODEL = "gemini-3.8-live"


class Skip(Exception):
    pass


def need(*values):
    if not all(values):
        raise Skip("credentials not in .env yet")


def gemini():
    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)
    t = time.perf_counter()
    r = client.models.generate_content(model=TEXT_MODEL, contents="Reply with exactly: Koe is alive")
    return f"{TEXT_MODEL} said {r.text.strip()!r} in {time.perf_counter() - t:.2f}s"


def live():
    # Live API shape from https://ai.google.dev/gemini-api/docs/live-api/get-started-sdk
    # Output audio is raw PCM16, 24 kHz, mono, little-endian (https://ai.google.dev/gemini-api/docs/live).
    from google import genai

    async def run():
        client = genai.Client(api_key=settings.gemini_api_key)
        config = {"response_modalities": ["AUDIO"]}
        audio = bytearray()
        async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            t = time.perf_counter()
            first = None
            await session.send_realtime_input(text="Say hello to Rohit in one short sentence.")
            async for msg in session.receive():
                sc = msg.server_content
                if sc and sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.inline_data:
                            first = first or time.perf_counter() - t
                            audio += part.inline_data.data
                if sc and sc.turn_complete:
                    break
        out = Path(tempfile.gettempdir()) / "koe_smoke_live.wav"
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(24000)
            w.writeframes(audio)
        secs = len(audio) / 2 / 24000
        return f"{LIVE_MODEL}: first audio after {first:.2f}s, {secs:.1f}s of speech, play {out}"

    return asyncio.run(run())


def github():
    # https://docs.github.com/en/rest/users/users#get-the-authenticated-user
    need(settings.github_token)
    r = httpx.get(
        "https://api.github.com/user",
        headers={
            "Authorization": f"Bearer {settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
        },
    )
    r.raise_for_status()
    return f"logged in as {r.json()['login']} (rate limit left: {r.headers.get('x-ratelimit-remaining')})"


def notion():
    # https://developers.notion.com/reference/get-self
    need(settings.notion_token)
    r = httpx.get(
        "https://api.notion.com/v1/users/me",
        headers={"Authorization": f"Bearer {settings.notion_token}", "Notion-Version": "2026-03-11"},
    )
    r.raise_for_status()
    return f"integration bot: {r.json().get('name')}"


def calendar():
    # Pattern from https://developers.google.com/workspace/calendar/api/quickstart/python
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    need(Path("credentials.json").exists())
    # Scopes Koe will need (ARCHITECTURE §9). Changing them later = delete token.json and log in again.
    scopes = [
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    creds = Credentials.from_authorized_user_file("token.json", scopes) if Path("token.json").exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = InstalledAppFlow.from_client_secrets_file("credentials.json", scopes).run_local_server(port=0)
        Path("token.json").write_text(creds.to_json())
    events = (
        build("calendar", "v3", credentials=creds)
        .events()
        .list(calendarId="primary", timeMin=datetime.now(timezone.utc).isoformat(),
              maxResults=3, singleEvents=True, orderBy="startTime")
        .execute()
        .get("items", [])
    )
    return f"next events: {[e.get('summary') for e in events] or 'none'}"


def whatsapp():
    # The test number can only start a chat with a template; hello_world is pre-approved.
    # https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started (Graph v25.0, as shown in the app dashboard 2026-10-12)
    to = settings.allowed_whatsapp_numbers.split(",")[0].strip()
    need(settings.whatsapp_token, settings.whatsapp_phone_number_id, to)
    url = f"https://graph.facebook.com/v25.0/{settings.whatsapp_phone_number_id}"
    auth = {"Authorization": f"Bearer {settings.whatsapp_token}"}
    # "accepted" by /messages does NOT mean delivered: Meta fails it later (seen: 131031).
    # Health Status API tells us up front: https://developers.facebook.com/documentation/business-messaging/whatsapp/support/health-status
    health = httpx.get(url, params={"fields": "health_status"}, headers=auth).json()["health_status"]
    if health["can_send_message"] == "BLOCKED":
        reasons = [f"{e['entity_type']} {x['error_code']}: {x['error_description']}"
                   for e in health["entities"] if e["can_send_message"] == "BLOCKED" for x in e.get("errors", [])]
        raise RuntimeError(f"Meta blocks sending: {reasons}")
    r = httpx.post(
        f"{url}/messages",
        headers=auth,
        json={
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {"name": "hello_world", "language": {"code": "en_US"}},
        },
    )
    r.raise_for_status()
    return f"accepted hello_world for {to} (check your phone; delivery is reported by webhook)"


CHECKS = {"gemini": gemini, "live": live, "github": github, "notion": notion,
          "calendar": calendar, "whatsapp": whatsapp}

if __name__ == "__main__":
    failed = False
    for name in sys.argv[1:] or CHECKS:
        try:
            print(f"PASS  {name:9} {CHECKS[name]()}")
        except Skip as e:
            print(f"SKIP  {name:9} {e}")
        except Exception as e:
            failed = True
            print(f"FAIL  {name:9} {type(e).__name__}: {e}")
    sys.exit(1 if failed else 0)
