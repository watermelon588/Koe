"""Gemini with fallbacks, so one overloaded model or one used-up key doesn't stop Koe.

- 429 RESOURCE_EXHAUSTED: try the next configured key, then another model. Quotas are per Google project/model;
  two keys in the same project do not provide independent quota.
- 500/503/504 or a timeout: this *model* is overloaded for everyone (seen live: gemini-3.8-flash 503 on both keys
  while gemini-3.6-flash answered in ~3 s) → try the next model in GEMINI_FALLBACK_MODELS.
A key or model that failed sits out for a while, so the next turn goes straight to one that works.
Google's client retries 503s by itself for minutes (one turn took 185 s); here every attempt is single and short,
and Koe decides where to go next. https://ai.google.dev/gemini-api/docs/troubleshooting#error-codes
"""
import asyncio
import logging
import time

import httpx
from google import genai
from google.genai import errors, types

from koe import usage
from koe.config import settings

log = logging.getLogger("koe.gemini")
KEY_REST = 600  # a key out of quota sits out 10 minutes
MODEL_REST = 300  # an overloaded model sits out 5 minutes
# One attempt. Measured 2026-10-13: a healthy model answers a tool request in 3–5 s, but a busy one can hang ~42 s
# before a 504, so waiting longer than this only delays the fallback.
TIMEOUT_MS = 15_000
GENERATION_SECONDS = 30  # total budget across models/keys, before the optional text backup
OVERLOADED = {500, 503, 504}

_clients: dict[str, genai.Client] = {}
_resting: dict[tuple[str, str], float] = {}  # ("key"|"model", name) → monotonic time it may be tried again
_last_good: str | None = None  # the model that answered last: tried first next time


def keys() -> list[str]:
    """A friend's own key is used alone (their quota, never the shared keys); otherwise the shared keys in order."""
    own = usage.own_key()
    if own:
        return [own]
    return list(dict.fromkeys(k for k in (settings.gemini_api_key, settings.gemini_api_key_2) if k))


def text_models() -> list[str]:
    extra = [m.strip() for m in settings.gemini_fallback_models.split(",") if m.strip()]
    return list(dict.fromkeys([settings.gemini_text_model, *extra]))


def client(key: str) -> genai.Client:
    if key not in _clients:
        _clients[key] = genai.Client(api_key=key, http_options=types.HttpOptions(
            timeout=TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1)))
    return _clients[key]


def _ready(kind: str, name: str) -> bool:
    return _resting.get((kind, name), 0) <= time.monotonic()


def rest(kind: str, name: str, seconds: float) -> None:
    _resting[(kind, name)] = time.monotonic() + seconds


def _ordered(kind: str, names: list[str]) -> list[str]:
    """Ready ones first; resting ones last rather than skipped (if everything is resting, still try)."""
    return [n for n in names if _ready(kind, n)] + [n for n in names if not _ready(kind, n)]


def live_client() -> genai.Client:
    """For Gemini Live (calls, spoken replies): the first key that isn't resting."""
    return client(_ordered("key", keys())[0])


def rest_client(c: genai.Client) -> None:
    """A Live session hit the quota: rest that client's key so the next call starts on the other one."""
    for key, known in _clients.items():
        if known is c:
            rest("key", key, KEY_REST)


async def generate(*, contents, config=None, models: list[str] | None = None, only: genai.Client | None = None):
    """Bound one generation chain; the caller decides whether a provider switch is safe."""
    try:
        return await asyncio.wait_for(_generate(contents=contents, config=config, models=models, only=only),
                                      timeout=GENERATION_SECONDS)
    except (TimeoutError, httpx.TransportError):
        # A different provider may be reachable; never expose transport diagnostics or credentials.
        raise errors.APIError(503, {'error': {'message': 'Gemini unavailable within the generation budget.',
                                            'status': 'UNAVAILABLE'}}) from None


async def _generate(*, contents, config=None, models: list[str] | None = None, only: genai.Client | None = None):
    """generate_content across models × keys. Returns (response, model). Raises the last error if all fail.
    `models=[m]` pins a model (later tool rounds of a turn stay on the model that started it).
    `only` uses one given client (tests, the CLI) with model fallback but no key rotation."""
    last: Exception | None = None
    global _last_good
    order = models or text_models()
    if not models and _last_good in order:
        order = [_last_good, *[m for m in order if m != _last_good]]
    # A cold per-person credential cache can read Neon; keep that I/O off the audio/event loop.
    credentials = [None] if only else await asyncio.to_thread(keys)
    for model in _ordered("model", order):
        for key in _ordered("key", credentials) if not only else credentials:
            started = time.perf_counter()
            which = "given client" if only else f"key {credentials.index(key) + 1}"
            try:
                c = only or client(key)
                response = await c.aio.models.generate_content(model=model, contents=contents, config=config)
                _last_good = model
                log.info("%s on %s: ok in %.1fs", model, which, time.perf_counter() - started)
                return response, model
            except errors.APIError as exc:
                log.info("%s on %s: %s in %.1fs", model, which, exc.code, time.perf_counter() - started)
                last = exc
                if exc.code == 429 and key:
                    rest("key", key, KEY_REST)
                    continue  # same model, next key
                if exc.code in OVERLOADED:
                    rest("model", model, MODEL_REST)
                    break  # next model
                raise
            except httpx.TimeoutException as exc:
                log.info("%s on %s: timeout in %.1fs", model, which, time.perf_counter() - started)
                last = exc
                rest("model", model, MODEL_REST)
                break
    if isinstance(last, httpx.TimeoutException):
        raise errors.APIError(503, {"error": {"message": "Gemini timed out.", "status": "UNAVAILABLE"}})
    raise last or RuntimeError("No Gemini API key is configured.")
