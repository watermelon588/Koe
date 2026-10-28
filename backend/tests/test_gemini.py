"""koe/gemini.py: 429 → next key, 503 → next model, failures rest so the next turn skips them. Fake clients only."""
import asyncio
from types import SimpleNamespace

import pytest
import httpx
from google.genai import errors

from koe import connections, gemini, identity
from koe.config import settings


def busy(code):
    return errors.APIError(code, {"error": {"code": code, "message": "busy", "status": "UNAVAILABLE" if code == 503 else "RESOURCE_EXHAUSTED"}})


@pytest.fixture
def calls(monkeypatch):
    """Fake clients that fail as scripted per (key, model) and record every attempt."""
    monkeypatch.setattr(settings, "gemini_api_key", "key-1")
    monkeypatch.setattr(settings, "gemini_api_key_2", "key-2")
    monkeypatch.setattr(settings, "gemini_text_model", "main")
    monkeypatch.setattr(settings, "gemini_fallback_models", "backup-a,backup-b")
    tried, failing = [], {}

    def client(key):
        async def generate_content(model, contents, config=None):
            tried.append((key, model))
            if (key, model) in failing or ("*", model) in failing:
                raise busy(failing.get((key, model)) or failing[("*", model)])
            return SimpleNamespace(text=f"{key}:{model}")
        return SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))

    monkeypatch.setattr(gemini, "client", client)
    return SimpleNamespace(tried=tried, failing=failing)


def run(**kw):
    return asyncio.run(gemini.generate(contents="hi", **kw))


def test_a_used_up_key_switches_to_the_second_key(calls):
    calls.failing[("key-1", "main")] = 429
    response, model = run()
    assert (response.text, model) == ("key-2:main", "main")
    response, _ = run()  # key-1 is resting: the next turn starts on key-2
    assert calls.tried[-1] == ("key-2", "main") and len(calls.tried) == 3


def test_an_overloaded_model_switches_to_the_next_model_and_rests(calls):
    calls.failing[("*", "main")] = 503
    response, model = run()
    assert model == "backup-a" and calls.tried == [("key-1", "main"), ("key-1", "backup-a")]  # 503 is model-wide: no second key
    run()
    assert calls.tried[-1] == ("key-1", "backup-a")  # main is resting, so it's tried last, not first


def test_a_pinned_model_stays_put_for_later_tool_rounds(calls):
    calls.failing[("*", "main")] = 503
    with pytest.raises(errors.APIError):
        run(models=["main"])
    assert {m for _, m in calls.tried} == {"main"}


def test_everything_busy_raises_the_last_error(calls):
    for model in ("main", "backup-a", "backup-b"):
        calls.failing[("*", model)] = 503
    with pytest.raises(errors.APIError) as caught:
        run()
    assert caught.value.code == 503


def test_a_friends_own_key_is_used_alone(calls, monkeypatch):
    monkeypatch.setattr(settings, "koe_secret_key", "a-test-secret-that-is-long-enough-for-koe-1234")
    connections.save("friend-id", "gemini", "key ending 9999", [], {"key": "friends-key"})
    token = identity.OWNER.set("friend-id")
    try:
        calls.failing[("friends-key", "main")] = 429
        response, _ = run()
    finally:
        identity.OWNER.reset(token)
    assert {k for k, _ in calls.tried} == {"friends-key"}  # never the shared keys
    assert response.text == "friends-key:backup-a"  # its 429 rests it; the next model still uses the friend's key


def test_the_model_that_answered_last_is_tried_first(calls):
    calls.failing[("*", "main")] = 503
    run()  # main fails, backup-a answers
    gemini._resting.clear()  # even once main may be tried again…
    calls.tried.clear()
    run()
    assert calls.tried[0] == ("key-1", "backup-a")  # …the last good model goes first: no wasted seconds on main


def test_the_entire_generation_chain_has_a_deadline(monkeypatch):
    async def stalled(**kwargs):
        await asyncio.Event().wait()
    fake = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=stalled)))
    monkeypatch.setattr(gemini, 'GENERATION_SECONDS', .01, raising=False)
    async def scenario():
        with pytest.raises(errors.APIError) as caught:
            await asyncio.wait_for(gemini.generate(contents='Synthetic input', only=fake), timeout=.2)
        assert caught.value.code == 503
    asyncio.run(scenario())


def test_cold_credential_lookup_does_not_block_the_event_loop(monkeypatch):
    import threading
    main_thread, seen = threading.get_ident(), []
    def keys():
        seen.append(threading.get_ident())
        return ['synthetic-key']
    async def generated(**kwargs): return SimpleNamespace(text='Synthetic answer')
    monkeypatch.setattr(gemini, 'keys', keys)
    monkeypatch.setattr(gemini, 'client', lambda key: SimpleNamespace(aio=SimpleNamespace(
        models=SimpleNamespace(generate_content=generated))))
    response, _ = run()
    assert response.text == 'Synthetic answer' and seen and all(t != main_thread for t in seen)


def test_a_transport_failure_tries_the_next_text_model_before_giving_up(monkeypatch):
    tried = []
    monkeypatch.setattr(settings, 'gemini_text_model', 'primary')
    monkeypatch.setattr(settings, 'gemini_fallback_models', 'backup')
    async def generated(model, **kwargs):
        tried.append(model)
        if model == 'primary':
            raise httpx.ConnectError('synthetic TLS reset')
        return SimpleNamespace(text='Recovered')
    fake = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generated)))
    response, model = run(only=fake)
    assert response.text == 'Recovered' and model == 'backup'
    assert tried == ['primary', 'backup']
