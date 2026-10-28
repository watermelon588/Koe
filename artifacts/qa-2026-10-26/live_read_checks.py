"""Read-only acceptance probes. Outputs counts/status, never credentials or record contents."""
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from koe.config import settings
from koe import gemini, store, spotify_service as sp
from koe.tools import calendar, docs, sheets, github, github_stats
import httpx

logging.disable(logging.CRITICAL)
OUTPUT = Path(os.environ.get('KOE_QA_OUTPUT', Path(__file__).parent))
OUTPUT.mkdir(parents=True, exist_ok=True)
checks = []

def summary(data):
    if not isinstance(data, dict):
        return {'response_type': type(data).__name__}
    if data.get('error'):
        err = data['error']
        return {'error': {k: err.get(k) for k in ('code', 'message', 'hint')} if isinstance(err, dict) else 'provider error'}
    result = {'keys': sorted(data)}
    for key in ('events', 'prs', 'commits', 'pages', 'documents', 'items', 'messages', 'editable', 'optional_headers'):
        if isinstance(data.get(key), list):
            result[key + '_count'] = len(data[key])
    for key in ('partial', 'totals_are_complete', 'connected', 'workflow_ready', 'docs_ready', 'ready', 'github_ready', 'github_token_ready', 'google', 'configured', 'enabled', 'unavailable_reason'):
        if key in data:
            result[key] = data[key]
    if isinstance(data.get('connections'), list):
        result['providers'] = [{'provider': c.get('provider'), 'connected': c.get('connected')} for c in data['connections']]
    return result

async def probe(name, fn):
    started = time.perf_counter()
    try:
        async with asyncio.timeout(65):
            data = await fn()
        item = {'name': name, 'status': 'FAIL' if isinstance(data, dict) and data.get('error') else 'PASS', 'result': summary(data)}
    except Exception as exc:
        item = {'name': name, 'status': 'FAIL', 'exception_type': type(exc).__name__}
        code = getattr(exc, 'code', None)
        if isinstance(code, (str, int)):
            item['error_code'] = code
    item['elapsed_ms'] = round((time.perf_counter() - started) * 1000)
    checks.append(item)
    print(json.dumps(item), flush=True)
    OUTPUT.joinpath('live-read-results.json').write_text(json.dumps({'mode': 'live-read-only; no messages, bookings, documents, rows or playlist edits', 'checks': checks}, indent=2), encoding='utf-8')

async def http_probe(path, authenticated=True):
    headers = {'Authorization': 'Bearer ' + settings.koe_access_token} if authenticated else {}
    async with httpx.AsyncClient(timeout=45, trust_env=False) as client:
        response = await client.get('http://127.0.0.1:8000' + path, headers=headers)
        data = response.json()
        if response.status_code >= 400:
            return {'error': {'code': response.status_code, 'message': data.get('detail', data.get('error', {}).get('message', 'HTTP failure'))}}
        return data

async def neon():
    await store.check_connection()
    return {'reachable': True}

async def text_model():
    response, model = await gemini.generate(contents='Reply with exactly: Koe QA is alive')
    return {'model': model, 'has_text': bool(response.text)}

async def live_model():
    from koe.voice_call import LIVE_MODEL
    async with gemini.live_client().aio.live.connect(model=LIVE_MODEL, config={'response_modalities': ['AUDIO']}) as session:
        await session.send_realtime_input(text='Say hello in one short sentence.')
        size = 0
        async for message in session.receive():
            content = message.server_content
            if content and content.model_turn:
                for part in content.model_turn.parts:
                    if part.inline_data:
                        size += len(part.inline_data.data)
            if content and content.turn_complete:
                break
        if not size:
            raise RuntimeError('No audio returned')
        return {'audio_bytes': size}

async def spotify_read():
    sp.require_enabled()
    async with sp.owner_lock(settings.koe_owner_id):
        row = await sp.connection(settings.koe_owner_id)
        generation = row['token']['connection_id']
        selected = await sp.selected(settings.koe_owner_id, generation)
        result = await sp.request(settings.koe_owner_id, 'GET', '/playlists/' + selected['id'] + '/items', generation=generation, params={'limit': 5})
        return {'connected': True, 'items': result.get('items', [])}

async def whatsapp_health():
    if not settings.whatsapp_token or not settings.whatsapp_phone_number_id:
        return {'error': {'code': 'not_configured'}}
    async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
        response = await client.get('https://graph.facebook.com/v25.0/' + settings.whatsapp_phone_number_id,
            params={'fields': 'health_status'}, headers={'Authorization': 'Bearer ' + settings.whatsapp_token})
        data = response.json()
        if response.status_code >= 400:
            return {'error': {'code': data.get('error', {}).get('code', response.status_code), 'message': 'Meta health read rejected'}}
        health = data.get('health_status', {})
        return {'error': {'code': 'sending_blocked', 'message': 'Meta reports sending blocked'}} if health.get('can_send_message') == 'BLOCKED' else {'can_send_message': health.get('can_send_message')}

async def main():
    today = datetime.now(ZoneInfo(settings.timezone)).date().isoformat()
    jobs = [
        ('HTTP health', lambda: http_probe('/health', False)),
        ('HTTP sign-in status', lambda: http_probe('/auth/status', False)),
        ('HTTP configuration diagnostics', lambda: http_probe('/api/backend/status')),
        ('HTTP provider connections', lambda: http_probe('/api/connections')),
        ('HTTP chat history', lambda: http_probe('/api/app/messages')),
        ('HTTP Notion readiness', lambda: http_probe('/api/notion/status')),
        ('HTTP Notion records', lambda: http_probe('/api/notion/records')),
        ('HTTP Notion schema', lambda: http_probe('/api/notion/schema')),
        ('Neon storage read', neon),
        ('Calendar today', lambda: calendar.calendar_list(today)),
        ('Calendar free slots', lambda: calendar.calendar_find_free(today, 30)),
        ('Sheets configured headers', sheets.sheets_schema),
        ('Docs app-accessible discovery', docs.docs_find),
        ('GitHub review queue', github.github_review_queue),
        ('GitHub own PRs', github.github_my_prs),
        ('GitHub yesterday activity', lambda: github_stats.github_activity(since='yesterday', include_lines=True)),
        ('GitHub 30-day contributions', lambda: github_stats.github_contributions(days=30)),
        ('Spotify selected playlist read', spotify_read),
        ('WhatsApp sending health (no send)', whatsapp_health),
        ('Gemini text generation', text_model),
        ('Gemini Live audio generation', live_model),
    ]
    # Keep calls to each provider sequential; independent checks overlap four at a time.
    gate = asyncio.Semaphore(4)
    async def bounded(name, fn):
        async with gate:
            await probe(name, fn)
    await asyncio.gather(*(bounded(name, fn) for name, fn in jobs))

if __name__ == '__main__':
    asyncio.run(main())
