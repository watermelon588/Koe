"""Follow-up read diagnostics, with only sanitized status output."""
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from koe import store, connections, google_auth
from koe.config import settings
from koe.tools import sheets, github_stats
import httpx
import psycopg
logging.disable(logging.CRITICAL)
results=[]
def record(name, **data):
    result={'name':name, **data}
    results.append(result)
    print(json.dumps(result),flush=True)
    Path(__file__).with_name('follow-up-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')

def database():
    options=store.connection_options()
    options['connect_timeout']=8
    started=time.perf_counter()
    try:
        with psycopg.connect(**options) as con:
            con.read_only=True
            con.execute("set local statement_timeout='8000ms'")
            con.execute("set local lock_timeout='2000ms'")
            tables={table:con.execute('select to_regclass(%s) is not null',('public.'+table,)).fetchone()[0] for table in store.TABLES}
            record('Database tables',tables=tables,read_only=con.execute('show transaction_read_only').fetchone()[0],elapsed_ms=round((time.perf_counter()-started)*1000))
    except Exception as exc:
        record('Database tables',exception_type=type(exc).__name__,sqlstate=getattr(exc,'sqlstate',None),elapsed_ms=round((time.perf_counter()-started)*1000))

def google_refresh():
    try:
        creds=google_auth.credentials()
        record('Google Calendar credentials',valid=creds.valid)
    except Exception as exc:
        record('Google Calendar credentials',exception_type=type(exc).__name__,safe_message=str(exc) if isinstance(exc,google_auth.GoogleAuthError) else None)
    try:
        row=connections.load(settings.koe_owner_id,'google')
        record('Stored Google grant',exists=bool(row),calendar_scope=bool(row and connections.CALENDAR_SCOPE in row['scopes']),sheets_scope=bool(row and connections.SHEETS_SCOPE in row['scopes']),docs_scope=bool(row and connections.DOCS_SCOPE in row['scopes']),drive_file_scope=bool(row and connections.DRIVE_FILE_SCOPE in row['scopes']))
    except Exception as exc:
        record('Stored Google grant',exception_type=type(exc).__name__)
    try:
        creds=connections.google_credentials([connections.CALENDAR_SCOPE])
        record('Direct Google refresh',valid=bool(creds and creds.valid))
    except Exception as exc:
        # google.auth RefreshError includes a structured provider error; emit only its standard code.
        detail=exc.args[1] if len(exc.args)>1 and isinstance(exc.args[1],dict) else {}
        record('Direct Google refresh',exception_type=type(exc).__name__,provider_error=detail.get('error'),safe_message=str(exc) if isinstance(exc,connections.ConnectionError_) else None)
    try:
        prepared=sheets.prepare_hours('2026-10-26','QA read probe',1)
        record('Timesheet destination',configured=bool(prepared.get('spreadsheet_id')))
    except Exception as exc:
        record('Timesheet destination',exception_type=type(exc).__name__,safe_message=str(exc) if isinstance(exc,ValueError) else None)

async def api_reads():
    async with httpx.AsyncClient(timeout=65,trust_env=False,headers={'Authorization':'Bearer '+settings.koe_access_token}) as client:
        started=time.perf_counter()
        try:
            response=await client.get('http://127.0.0.1:8000/api/app/messages')
            record('Chat history sequential retry',http_status=response.status_code,messages_count=len(response.json().get('messages',[])),elapsed_ms=round((time.perf_counter()-started)*1000))
        except Exception as exc:
            record('Chat history sequential retry',exception_type=type(exc).__name__,elapsed_ms=round((time.perf_counter()-started)*1000))
        for endpoint in ('/api/backend/status','/api/notion/records','/api/connections'):
            response=await client.get('http://127.0.0.1:8000'+endpoint,headers={'Authorization':'Bearer deliberately-invalid-qa-token'})
            record('Unauthorized '+endpoint,http_status=response.status_code,protected=response.status_code in (401,403))

async def main():
    await asyncio.to_thread(database)
    await asyncio.to_thread(google_refresh)
    await api_reads()

if __name__=='__main__':
    asyncio.run(main())
