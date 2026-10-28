"""Call regressions found by the live audit; all browser/provider data is synthetic."""
import asyncio
import threading
from contextlib import asynccontextmanager
from types import SimpleNamespace

from google.genai import errors

from koe import gemini, usage, voice_call
from test_voice_call import FakeBrowser, FakeSession, HANG_UP, SILENT, fake_gemini, msg


async def finish_call(call, browser):
    browser.says(HANG_UP)
    try:
        await asyncio.wait_for(call, 3)
    finally:
        if not call.done():
            call.cancel()
            await asyncio.gather(call, return_exceptions=True)


def test_call_cold_credentials_leave_the_event_loop_responsive(monkeypatch):
    fake_gemini(monkeypatch)
    lookup_started = threading.Event()
    event_loop_responded = threading.Event()
    observed = []

    def cold_key_lookup():
        lookup_started.set()
        # A live socket must still process work while the credential store is slow.
        observed.append(event_loop_responded.wait(timeout=.5))
        return ''

    monkeypatch.setattr(usage, 'own_key', cold_key_lookup)

    async def scenario():
        browser = FakeBrowser()
        call = asyncio.create_task(voice_call.call(browser))

        async def heartbeat():
            while not lookup_started.is_set():
                await asyncio.sleep(0)
            event_loop_responded.set()

        heartbeat_task = asyncio.create_task(heartbeat())
        try:
            browser.says(SILENT)
            assert await browser.hears() == b'reply:' + SILENT
            await heartbeat_task
        finally:
            await finish_call(call, browser)
        assert observed and all(observed), 'Slow credential lookup froze the live event loop.'

    asyncio.run(scenario())


def test_initial_live_tls_reset_recovers_without_replaying_input(monkeypatch):
    attempts, sessions = [], []

    @asynccontextmanager
    async def connect(model, config):
        attempts.append(config)
        if len(attempts) == 1:
            raise ConnectionResetError('synthetic initial TLS reset')
        session = FakeSession('recovered')
        sessions.append(session)
        yield session

    client = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
    monkeypatch.setattr(gemini, 'live_client', lambda: client)

    async def scenario():
        browser = FakeBrowser()
        call = asyncio.create_task(voice_call.call(browser))
        try:
            browser.says(SILENT)
            assert await browser.hears() == b'reply:' + SILENT
            assert len(attempts) == 2
            assert len(sessions) == 1 and len(sessions[0].sent) == 1
        finally:
            await finish_call(call, browser)

    asyncio.run(scenario())


def test_initial_live_failures_stop_after_a_bounded_number_of_attempts(monkeypatch):
    attempts = []

    @asynccontextmanager
    async def connect(model, config):
        attempts.append(config)
        raise ConnectionResetError('synthetic unavailable upstream')
        yield  # pragma: no cover - retain the async context-manager protocol

    client = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
    monkeypatch.setattr(gemini, 'live_client', lambda: client)

    async def scenario():
        browser = FakeBrowser()
        call = asyncio.create_task(voice_call.call(browser))
        try:
            closed = await asyncio.wait_for(browser.to_browser.get(), 8)
            assert closed[0:2] == ('closed', 1011)
            await asyncio.wait_for(call, 1)
            assert 2 <= len(attempts) <= 4, 'Startup needs bounded transient retries.'
        finally:
            if not call.done():
                call.cancel()
                await asyncio.gather(call, return_exceptions=True)

    asyncio.run(scenario())


def test_an_active_tool_turn_is_not_restarted_without_a_resume_handle(monkeypatch):
    sessions, executed = [], []

    class InterruptedSession(FakeSession):
        async def receive(self):
            data = await self.replies.get()
            if data == b'TOOL':
                function = SimpleNamespace(id='qa-tool', name='github_my_prs', args={'state': 'open'})
                yield msg(tool_call=SimpleNamespace(function_calls=[function]))
            elif data == b'after-tool':
                raise ConnectionResetError('synthetic active session loss')

    @asynccontextmanager
    async def connect(model, config):
        session = InterruptedSession('active')
        sessions.append(session)
        yield session

    async def my_prs(state='open'):
        executed.append(state)
        return {'count': 0, 'prs': []}

    client = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
    monkeypatch.setattr(gemini, 'live_client', lambda: client)
    monkeypatch.setitem(voice_call.agent.TOOLS, 'github_my_prs',
        voice_call.agent.TOOLS['github_my_prs']._replace(fn=my_prs))

    async def scenario():
        browser = FakeBrowser()
        call = asyncio.create_task(voice_call.call(browser))
        try:
            browser.says(b'TOOL')
            assert (await browser.hears())['phase'] == 'start'
            assert (await browser.hears())['phase'] == 'end'
            assert (await browser.hears())[0:2] == ('closed', 1011)
            await asyncio.wait_for(call, 1)
            assert len(sessions) == 1
            assert executed == ['open']
        finally:
            if not call.done():
                call.cancel()
                await asyncio.gather(call, return_exceptions=True)

    asyncio.run(scenario())


def test_permanent_live_setup_rejection_is_not_retried(monkeypatch):
    attempts = []

    @asynccontextmanager
    async def connect(model, config):
        attempts.append(config)
        raise errors.APIError(400, {'error': {'message': 'synthetic invalid configuration'}})
        yield  # pragma: no cover

    client = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
    monkeypatch.setattr(gemini, 'live_client', lambda: client)

    async def scenario():
        browser = FakeBrowser()
        await voice_call.call(browser)
        assert (await browser.hears())[0:2] == ('closed', 1011)
        assert len(attempts) == 1

    asyncio.run(scenario())
