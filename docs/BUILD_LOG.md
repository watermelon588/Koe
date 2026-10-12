# Build log: Koe (声)

A plain-English learning journal. **One entry per step**, newest at the bottom. Written for Rohit to reread later and to prepare for interviews.

## Template (copy for each step)
```markdown
## Step N: <short title>  (Phase X · YYYY-MM-DD)
**Files:** path/one.py (new) · path/two.tsx (changed)
**What it does:** 2–3 sentences.
**Core concept:** the idea behind it in plain English (e.g. "Webhooks: don't call us, we'll call you…").
**How it connects:** what calls it / what it calls (→ arrows are fine).
**Try it yourself:** exact command or action, and what you should see.
**Gotchas:** anything that bit us or might.
**Measured:** numbers, if any (latency, accuracy).
**Interview line:** one sentence you could say in an interview about this.
```

---

## Step 0: project docs written  (Planning · 2026-10-12)
**Files:** CLAUDE.md · docs/PROBLEM_STATEMENT.md · docs/SPEC.md · docs/ARCHITECTURE.md · docs/TECH_STACK.md · docs/SERVICES_AND_COSTS.md · docs/PLAN.md · docs/SKILLS.md · docs/DECISIONS.md · docs/RESEARCH_SOURCES.md · docs/BUILD_LOG.md · README.md
**What it does:** Captures every decision from the planning conversation, so any future session or agent starts with full context.
**Core concept:** *Spec-driven development*: write down what "done" means before coding, so you don't build the wrong thing.
**How it connects:** CLAUDE.md is auto-read by Claude Code and points to everything else.
**Interview line:** "I wrote the spec, architecture and acceptance criteria first, including a 'not doing' list, which kept a one-month project in scope."

## Step 1: git repo + .gitignore  (Phase 0 · 2026-10-12)
**Files:** .gitignore (new)
**What it does:** Turns the folder into a git repo and tells git never to track secrets (`.env`, `credentials.json`, `token.json`), the local database, or generated folders (`.venv`, `node_modules`, `dist`).
**Core concept:** *Ignore before you create.* A `.gitignore` rule only protects files that were never committed. Once a secret is in history, deleting the file doesn't remove it. So the ignore list comes before the first key ever lands on disk.
**How it connects:** Every later step creates files; this decides which ones are shared and which stay on your laptop.
**Try it yourself:** `git check-ignore -v backend/.env` prints the matching rule (`.gitignore:2:.env`).
**Gotchas:** Git prints "LF will be replaced by CRLF" warnings on Windows. That's harmless: `core.autocrlf` converts line endings on checkout.
**Interview line:** "I set up the ignore rules for secrets before creating any, because git history is forever."

## Step 2: backend scaffold — FastAPI, config, /health  (Phase 0 · 2026-10-12)
**Files:** backend/pyproject.toml · backend/uv.lock · backend/koe/{__init__,config,main}.py · backend/.env.example · backend/tests/test_health.py (all new) · docs/TECH_STACK.md (Python 3.13)
**What it does:** Creates the Python project with `uv`, installs the libraries from TECH_STACK.md, and starts a FastAPI app with one route, `GET /health → {"ok": true}`. `config.py` reads `backend/.env` into a typed `Settings` object.
**Core concept:** *Fail fast on config.* `GEMINI_API_KEY` has no default, so pydantic-settings raises "Field required" the moment the app imports config. A missing key crashes at startup with a clear message, not minutes later in the middle of a call. Keys for later phases default to `""`, which means "not set up yet". `uv.lock` pins every exact version, so the same install works on the Azure VM later.
**How it connects:** `uvicorn` → `koe.main:app` → imports `koe.config.settings`. Every future module (`agent.py`, tools, webhooks) reads keys from `settings`, never from `os.environ` directly.
**Try it yourself:** from `backend/`: `uv run uvicorn koe.main:app --reload --port 8000`, then open http://localhost:8000/health and http://localhost:8000/docs (FastAPI's auto-generated API page). `uv run pytest -q` → `1 passed`.
**Gotchas:** uv chose Python 3.13 (already installed) over 3.12; the docs are updated. The pytest warning about `httpx2` comes from Starlette itself and is safe to ignore.
**Measured:** verified that it refuses to boot without the key and `/health` returns 200 with it.
**Interview line:** "Config is typed and validated at startup, so a missing secret fails loudly on boot instead of silently mid-request."

## Step 3: frontend scaffold — Vite + React + TS  (Phase 0 · 2026-10-12)
**Files:** frontend/* (Vite `react-ts` template, unmodified except removing its README)
**What it does:** A React + TypeScript app with Vite as the dev server and bundler. It's still the default template; Phase 1 replaces `App.tsx` with the call panel.
**Core concept:** *Vite* serves your source files to the browser almost as-is during development (instant reloads), and `npm run build` bundles them into small static files in `dist/`, which is exactly what Vercel hosts.
**How it connects:** Later, `frontend/src` opens WebSockets to the backend (`/ws/call`, `/ws/events`).
**Try it yourself:** from `frontend/`: `npm run dev` → open the printed URL. `npm run build` → `✓ built`.
**Gotchas:** CLAUDE.md warned that the `声` in the path might break build tools. It doesn't: build and lint pass, so no rename is needed.
**Interview line:** "Frontend is a static Vite build, so it hosts free on Vercel; all real-time work lives in the backend."

## Step 4: smoke tests + verified Gemini model IDs  (Phase 0 · 2026-10-12)
**Files:** backend/scripts/smoke.py (new) · backend/.env (created from the template, git-ignored) · docs/SERVICES_AND_COSTS.md · docs/TECH_STACK.md · docs/SPEC.md · docs/RESEARCH_SOURCES.md · docs/DECISIONS.md
**What it does:** One script, six checks, each making one real API call: Gemini text, **Gemini Live** (speaks a sentence and saves it as a WAV you can play), GitHub `/user`, Notion `/users/me`, Google Calendar (next 3 events, runs the OAuth login once and saves `token.json`), WhatsApp (sends the pre-approved `hello_world` template to your number). Each prints PASS, SKIP (no key yet) or FAIL.
**Core concept:** *Smoke test*: the cheapest test that proves the wiring works (the key is valid, the endpoint is right, the account is set up) before you build logic on top. If a later feature breaks, rerun this first to rule out credentials. Also: *source-driven*: every endpoint, header version and model ID came from the official docs on 2026-10-12, with the link in a comment. Model names change often (2.5 is already closed to new users).
**How it connects:** The Live check is a mini version of Phase 1: same `client.aio.live.connect(...)`, same 24 kHz PCM16 output. If it passes, the riskiest part of the project (free-tier Live access) is proven.
**Try it yourself:** put your key in `backend/.env`, then from `backend/`: `uv run python -m scripts.smoke gemini live`. Play the WAV path it prints.
**Gotchas:** The WhatsApp test number can't send free-form text until you've messaged it first (the 24-hour window), so the smoke test uses the `hello_world` template. Google free-tier rate limits aren't in the docs; check AI Studio → Rate limit. Changing Google OAuth scopes later means deleting `token.json` and logging in again.
**Measured:** _(fill in after the first real run: text latency, Live first-audio latency)_
**Interview line:** "Before writing features, I proved every external dependency with a one-command smoke test, built from the official docs, not memory."
