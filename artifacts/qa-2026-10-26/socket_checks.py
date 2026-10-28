"""Exercise authenticated real backend WebSockets with a greeting, never microphone data."""
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from koe.config import settings
import websockets
logging.disable(logging.CRITICAL)
OUTPUT=Path(os.environ.get('KOE_QA_OUTPUT',Path(__file__).parent))
OUTPUT.mkdir(parents=True,exist_ok=True)
results=[]
def record(name, **data):
    result={'name':name,**data}
    results.append(result)
    print(json.dumps(result),flush=True)
    (OUTPUT/'socket-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')

async def call():
    started=time.perf_counter()
    audio=0
    types=[]
    try:
        async with asyncio.timeout(75), websockets.connect('ws://127.0.0.1:8000/ws/call',open_timeout=10,ping_interval=None,max_size=8_000_000) as ws:
            await ws.send(json.dumps({'type':'auth','token':settings.koe_access_token}))
            await ws.send(json.dumps({'type':'text','text':'Say hello in one short sentence. Do not use any tools or change any records.'}))
            async for message in ws:
                if isinstance(message,bytes):
                    audio+=len(message)
                else:
                    data=json.loads(message)
                    types.append(data.get('type'))
                    if data.get('type')=='error':
                        record('Authenticated live call',audio_bytes=audio,event_types=sorted(set(types)),provider_error=True)
                        return
                    if data.get('type')=='turn_complete':
                        record('Authenticated live call',audio_bytes=audio,event_types=sorted(set(types)),elapsed_ms=round((time.perf_counter()-started)*1000),passed=audio>0)
                        return
            record('Authenticated live call',audio_bytes=audio,event_types=sorted(set(types)),ended_before_turn=True)
    except Exception as exc:
        record('Authenticated live call',exception_type=type(exc).__name__,audio_bytes=audio,event_types=sorted(set(types)),received_close_code=getattr(getattr(exc,'rcvd',None),'code',None),sent_close_code=getattr(getattr(exc,'sent',None),'code',None),elapsed_ms=round((time.perf_counter()-started)*1000))

async def dashboard():
    started=time.perf_counter()
    panels={}
    initial=False
    try:
        async with asyncio.timeout(75),websockets.connect('ws://127.0.0.1:8000/ws/events',open_timeout=10,ping_interval=None,max_size=8_000_000) as ws:
            await ws.send(json.dumps({'type':'auth','token':settings.koe_access_token}))
            async for message in ws:
                data=json.loads(message)
                if data.get('type')=='snapshot':
                    initial=True
                    for name,panel in data.get('panels',{}).items():
                        result=panel.get('result',{})
                        panels[name]={'error':bool(result.get('error'))}
                elif data.get('type')=='panel':
                    panels[data.get('name')]={'error':bool(data.get('result',{}).get('error'))}
                if len(panels)>=4:
                    record('Authenticated dashboard socket',snapshot=initial,panels=panels,elapsed_ms=round((time.perf_counter()-started)*1000))
                    return
    except Exception as exc:
        record('Authenticated dashboard socket',exception_type=type(exc).__name__,snapshot=initial,panels=panels,elapsed_ms=round((time.perf_counter()-started)*1000))

async def main():
    await call()
    await dashboard()

if __name__=='__main__':
    asyncio.run(main())
