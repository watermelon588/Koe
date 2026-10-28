"""One real greeting through the application's text/fallback loop. No app messages or provider records created."""
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from koe import agent, store, text_agent
logging.disable(logging.CRITICAL)
async def main():
    started=time.perf_counter()
    seen=[]
    async with asyncio.timeout(90):
        reply=await text_agent.chat('QA health check: reply with exactly Koe QA OK. Do not call tools or prepare changes.',[],agent.Conversation('app'),seen=seen)
    result={'passed':'Koe QA OK' in reply.get('text',''), 'tools_executed':len(seen),
        'pending_action':bool(reply.get('pending_action')),'elapsed_ms':round((time.perf_counter()-started)*1000)}
    print(json.dumps(result),flush=True)
    Path(__file__).with_name('repairs').joinpath('final','text-turn-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    await store.drain_background(3)
asyncio.run(main())
