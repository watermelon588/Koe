"""Live Gemini tool selection with synthetic Notion responses; all service access blocked.

Run from backend/: python -m scripts.verify_notion_agent
No prompt, service data, credentials or model reply is printed.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from google import genai
from google.genai import types

from koe import agent, store, text_agent
from koe.config import settings


async def main():
    logging.getLogger('httpx').setLevel(logging.WARNING)
    calls = []
    original = dict(agent.TOOLS)
    original_record, original_propose = store.record_best_effort, store.propose

    async def no_record(*args, **kwargs):
        pass

    async def proposal(session, channel, tool, args, summary):
        # Local-only proposal: this check cannot leave an executable approval in Neon.
        return {'id': str(uuid4()), 'session_id': session, 'channel': channel,
                'tool': tool, 'args_json': args, 'summary': summary, 'status': 'pending',
                'expires_ts': (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()}

    def guarded(name):
        async def invoke(**kwargs):
            calls.append(name)
            if name != 'notion_read':
                return {'error': {'code': 'verification_read_only', 'message': 'Mutation blocked by verification.'}}
            # Never read the real workspace or transmit its contents to a model.
            return {'pages': [{'id': '11111111-1111-1111-1111-111111111111',
                               'title': 'Synthetic verification task', 'kind': 'Task',
                               'status': 'Open', 'date': {'start': '2099-12-30'}}],
                    'has_more': False, 'next_cursor': None}
        return invoke

    try:
        store.record_best_effort, store.propose = no_record, proposal
        for name, tool in original.items():
            agent.TOOLS[name] = tool._replace(fn=guarded(name))
        options = types.HttpOptions(timeout=20000, async_client_args={'trust_env': False},
                                    retry_options=types.HttpRetryOptions(attempts=1))
        async with genai.Client(api_key=settings.gemini_api_key, http_options=options).aio as client:
            # text_agent expects the regular client with an aio property.
            from types import SimpleNamespace
            holder = SimpleNamespace(aio=client)
            ctx, history = agent.Conversation('cli'), []
            result = await asyncio.wait_for(text_agent.chat(
                'Use notion_read now to list my Notion tasks. Only read; do not create or change anything.',
                history, ctx, holder), timeout=45)
            if 'notion_read' not in calls:
                raise SystemExit('UNVERIFIED: Gemini did not call notion_read. Check provider availability, then rerun; no service data was read or changed.')
            assert not ctx.pending and not result.get('approval_result')
            print('PASS live Gemini selected notion_read and answered using synthetic records only.')
            calls.clear()
            ctx, history = agent.Conversation('cli'), []
            result = await asyncio.wait_for(text_agent.chat(
                'Propose a Notion task titled Synthetic agent verification for 2099-12-30, status Open, '
                'notes Test preview only. Use notion_save. Do not confirm it or book Calendar time.',
                history, ctx, holder), timeout=45)
            assert ctx.pending and ctx.pending['tool'] == 'notion_save', 'Gemini did not produce the Notion proposal.'
            assert ctx.pending['args_json']['title'] == 'Synthetic agent verification'
            assert not calls, 'The preview must not execute external tools.'
            assert result.get('pending_action')
            print('PASS live Gemini prepared the expected task preview without executing a write.')
    finally:
        agent.TOOLS.clear()
        agent.TOOLS.update(original)
        store.record_best_effort, store.propose = original_record, original_propose


if __name__ == '__main__':
    asyncio.run(main())
