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
**Measured (2026-10-12, first real run):** Gemini Live `gemini-3.8-live` **first audio 0.85 s** after a text prompt (2.6 s of speech) ✅ free tier works · GitHub ✅ · `gemini-3.5-flash-lite` text 2.09 s ✅ · `gemini-3.8-flash` returned **503 "high demand"** and the SDK's retries made the script hang more than 60 s. The key is fine; the model was overloaded. That's real evidence for the rate-limit plan: Phase 2 needs a short timeout + fallback to Flash-Lite.
**Gotcha found:** printing `→` crashed on the Windows console (cp1252 encoding), so the script output is plain ASCII now.
**Interview line:** "Before writing features, I proved every external dependency with a one-command smoke test, built from the official docs, not memory."

## Step 5: all service keys verified except Google  (Phase 0 · 2026-10-12)
**Files:** backend/scripts/smoke.py (Graph API v23.0 → v25.0) · backend/.env (filled by Rohit, git-ignored)
**What it does:** Ran the smoke tests with real keys: GitHub ✅ (`watermelon588`) · Notion ✅ (integration "koe") · WhatsApp ✅ (`hello_world` template accepted from the test number +1 555-653-7747 to your phone) · Gemini Live ✅ (0.85 s first audio). Google Calendar/Sheets is pending `credentials.json`.
**Core concept:** *Accepted ≠ delivered.* WhatsApp's API returns a message ID as soon as it *accepts* the message. Whether it was *delivered* arrives later as a status webhook (Phase 5). The smoke test proves the token and IDs are right; your phone proves delivery.
**How it connects:** Phase 5 sends replies and alerts with this same `POST /{phone-number-id}/messages` call.
**Try it yourself:** `uv run python -m scripts.smoke github notion whatsapp` from backend/.
**Gotchas:** The Meta dashboard showed Graph **v25.0** while the docs page said v23.0, so we went with the dashboard. The temporary WhatsApp token expires soon; Phase 5 replaces it with a permanent system-user token. Free-form text only works within 24 h of your last message to the test number; templates work any time.
**Interview line:** "I verified every third-party credential with a one-command smoke test before writing features, so later failures can't be blamed on setup."

## Step 6: debugging "WhatsApp message never arrived"  (Phase 0 · 2026-10-12)
**Files:** none in the repo (a throwaway webhook logger in the scratch folder + a cloudflared tunnel) · docs/SERVICES_AND_COSTS.md
**What it does:** Found out why no WhatsApp message reached the phone, using evidence instead of guesses.
**Core concept:** *Accepted ≠ delivered.* The send API only says "accepted"; delivery results (`sent`/`delivered`/`failed` + error code) come later through a **webhook**. To see them we needed: a public URL (cloudflared) → a tiny listener that answers Meta's verify handshake (`hub.challenge`) → the app subscribed to the "messages" field → **and** the WhatsApp Business Account subscribed to *our* app (it was only subscribed to Meta's internal dashboard app, so nothing arrived at first). Then the **Health Status API** gave the root cause.
**How it connects:** This is a preview of Phase 5's `/webhooks/whatsapp`: same handshake, same payload shape.
**Debug trail:** dashboard test not delivered → our template not delivered → phone `CONNECTED`/`GREEN`, token valid, `hello_world` APPROVED → webhook shows `failed 131031 Business Account locked` → Health Status: WABA BLOCKED, **141006 payment method** → user sends "test": inbound ✅ → free text reply inside the 24 h window ❌ also 131031.
**Measured:** inbound works; 0 of 4 outbound messages delivered.
**Gotchas:** The block applies even to free messages. Without a card, this WhatsApp account can listen but never speak.
**Interview line:** "Our sends returned 200, but nothing arrived. I stood up a webhook to read the real delivery status, found error 131031, and traced it via the Health Status API to a billing block on the account, then re-planned the channel instead of guessing."

## Step 7: first sound — test tone over WebSocket  (Phase 1 · Slice 1 · 2026-10-12)
**Files:** backend/koe/voice_call.py (new) · backend/koe/main.py (mounts the router) · backend/tests/test_voice_call.py (new) · frontend/src/call/player.ts (new) · frontend/src/App.tsx (replaced the Vite starter) · frontend/vite.config.ts (dev proxy) · frontend/src/index.css (tiny base) · removed template assets
**What it does:** Clicking **Call** opens a WebSocket to `/ws/call`. The backend streams 1 s of a 440 Hz tone in exactly the format Gemini Live will use (raw PCM16, 24 kHz, mono, little-endian) as 25 messages of 40 ms each, and the browser plays them back-to-back.
**Core concept:** *Raw PCM* is just a list of numbers: 24,000 per second, each a 16-bit signed integer (−32768…32767) giving the speaker's position at that instant. There's no header, so both sides must agree on **sample rate** (wrong → chipmunk/slow-mo voice), **sample width** (16-bit) and **byte order** (little-endian: low byte first; wrong → loud static). The browser's Web Audio API wants floats from −1 to 1, so `player.ts` divides by 32768. *Gapless playback:* each chunk becomes an `AudioBufferSourceNode` scheduled with `start(nextStart)`, and `nextStart` moves forward by the chunk's duration, so chunk 2 starts at the exact sample where chunk 1 ends. If the network falls behind, we start "now" instead of in the past.
**How it connects:** Browser `:5173` → Vite dev proxy → backend `:8000/ws/call` → `voice_call.py`. In Slice 3 the tone is replaced by Gemini's audio; `player.ts` stays the same.
**Try it yourself:** backend `uv run uvicorn koe.main:app --reload --port 8000`, frontend `npm run dev`, open http://localhost:5173 → **Call** → a clean 1-second beep (a pure "A" note). `uv run pytest -q` checks the bytes: 25 × 1920-byte chunks, 48,000 bytes total, and sample #6 decodes to the right value only when read as little-endian.
**Gotchas:** An `AudioContext` must be created inside a click handler (browser autoplay rules). An `AudioBufferSourceNode` can only be started once, hence one per chunk. Vite doesn't check the WebSocket `Origin` header; the backend's access token comes in Phase 3.
**Measured:** 1.00 s of audio arrives through the proxy in 7 ms, so the network is far faster than real time, and the scheduling (not the network) sets the pace.
**Interview line:** "Before involving the model I proved the audio pipeline with a synthetic tone in the model's exact wire format, so any format bug would be obvious and isolated."

## Step 8: microphone → backend → echo  (Phase 1 · Slice 2 · 2026-10-12)
**Files:** frontend/src/call/mic-worklet.js (new) · frontend/src/call/mic.ts (new) · frontend/src/App.tsx (Call / Hang up) · backend/koe/voice_call.py (tone → echo) · backend/tests/test_voice_call.py · CLAUDE.md (dev command)
**What it does:** **Call** asks for the mic, converts your voice to 16 kHz PCM16 (Gemini Live's *input* format), and streams 40 ms chunks to `/ws/call`. The backend sends each chunk straight back, and the page plays it, so you hear yourself. **Hang up** stops the mic (the browser's red mic dot disappears).
**Core concept:** An *AudioWorklet* is a tiny script that runs on the browser's **audio thread**, not the main thread where React runs. Audio arrives every ~8 ms in blocks of 128 samples; if that work ran on the main thread, a busy UI would drop audio. The worklet clamps each float sample to −1…1, scales it to a 16-bit integer, writes it little-endian, and every 640 samples (40 ms) *transfers* the buffer to the main thread (a zero-copy move, not a copy). The AudioContext runs at 16 kHz, so the browser itself resamples the mic (usually 48 kHz) and we write no resampling code. `echoCancellation` / `noiseSuppression` / `autoGainControl` are the same browser DSP that video-call apps use.
**How it connects:** mic → `MediaStreamSource` → worklet → `postMessage` → `ws.send` → backend → (Slice 3: Gemini) → back → `player.ts`.
**Try it yourself:** Chrome or Edge, **wear headphones**, http://localhost:5173 → Call → allow the mic → talk. Your voice comes back almost instantly at normal pitch. Chipmunk or slow-mo means a sample-rate bug; static means byte order.
**Gotchas:** (1) `uvicorn --reload` **hung** when I ran it in the background. My first guess (open WebSockets) was wrong: it hung with no connections too. Real cause, read from uvicorn's source: on Windows the reloader restarts the worker by sending **Ctrl+C (`CTRL_C_EVENT`)**, which only reaches processes attached to a real console window. A background shell has none, so the restart waits forever. In a normal VS Code terminal `--reload` works; for background runs, restart manually. (2) The worklet is plain `.js` loaded with `?url` because Vite copies such files as-is (no TypeScript compile). (3) Older Firefox versions refused to connect a mic to a context at a different sample rate (unverified for current Firefox); use Chrome/Edge. (4) Without headphones, the echo comes out of the speakers and back into the mic; echo cancellation helps but headphones are cleaner.
**Measured:** echo round trip through the Vite proxy, 50 × 40 ms chunks: **p50 0.3 ms, p95 0.6 ms** on localhost, so the WebSocket hop is effectively free and the latency budget belongs to Gemini.
**Interview line:** "Mic capture runs in an AudioWorklet on the audio thread, converting to the model's 16 kHz PCM16 wire format, so UI work can never cause audio dropouts."

## Step 9: talking to Gemini Live  (Phase 1 · Slice 3 · 2026-10-12)
**Files:** backend/koe/voice_call.py (echo → Gemini relay) · backend/tests/test_voice_call.py (fake Gemini session) · frontend/src/App.tsx (24 kHz playback, shows Gemini errors) · backend/scripts/smoke.py (shares `LIVE_MODEL`) · docs/BUILD_LOG.md + CLAUDE.md (reload fix reverted, see Step 8)
**What it does:** Each call opens a Gemini Live session (`gemini-3.8-live`) with a short Koe persona prompt. Two tasks run at the same time: **mic → Gemini** (each 40 ms chunk is sent as `audio/pcm;rate=16000`) and **Gemini → browser** (each audio part is forwarded as-is). When you stop talking, Gemini's server-side *voice activity detection* (VAD) notices the silence and starts answering.
**Core concept:** *A relay with two directions.* A phone call is full-duplex: both sides can send at any moment, so one loop that alternates "read, then write" would freeze while waiting on either side. `asyncio.TaskGroup` runs both loops concurrently, and if either one stops (you hang up → `WebSocketDisconnect`, or Gemini errors), the group **cancels the other** so nothing leaks. `except*` handles each kind of error from the group separately. Also, the SDK's `session.receive()` ends after every model turn, so it sits inside a `while True`.
**How it connects:** browser mic → `/ws/call` → Gemini Live → `/ws/call` → `player.ts`. Phase 2 adds tools to the same session config; Slice 4 handles Gemini's `interrupted` signal (barge-in).
**Try it yourself:** http://localhost:5173 → Call → "Hi Koe, who are you?" (headphones recommended). Test: `uv run pytest -q`; the fake session proves chunks are forwarded with the right format label and that replies flow across several turns.
**Gotchas:** A test run reported "first audio after 1 ms", which was too good to be true: the **old echo code** was still running because the reload had silently stalled. Checking suspicious numbers caught it. See Step 8 for the real cause (Windows Ctrl+C reload needs a console).
**Measured:** scripted e2e (2.6 s of real speech streamed in real time, then silence), 3 calls: speech end → first audio **1,697 / 1,089 / 1,094 ms → p50 ≈ 1.09 s** (target ≤ 1.5 s). This includes VAD end-pointing. Too few samples to claim yet; Slice 5 measures real calls. **⚠️ Corrected in Step 11:** these were timed from the end of the *file*, which had 0.36 s of quiet after the voice, so they were about 0.4 s too optimistic. Real p50 ≈ 1.7 s.
**Interview line:** "The call is a full-duplex relay: two concurrent asyncio tasks under a TaskGroup, so a hang-up or model error on either side tears down the other cleanly. First measurements put speech-end to first audio around 1.1 s."

## Step 10: barge-in, so you can interrupt Koe  (Phase 1 · Slice 4 · 2026-10-12)
**Files:** backend/koe/voice_call.py (forwards `interrupted`) · frontend/src/call/player.ts (`flush()`) · frontend/src/App.tsx (text vs binary frames) · backend/tests/test_voice_call.py (fake interruption)
**What it does:** If you start talking while Koe is speaking, Koe stops at once instead of finishing its sentence.
**Core concept:** *Why a flush is needed.* Gemini generates audio **faster than real time**, so by the time you interrupt, the browser has several seconds of Koe's answer already *scheduled* to play. Gemini's VAD hears you and sends `server_content.interrupted`. The backend forwards it as a **text** WebSocket frame `{"type":"interrupted"}` (binary frames = audio, text frames = control events: one socket, two kinds of message), and `player.flush()` calls `stop()` on every scheduled source node and resets the schedule. Without it, Koe would keep talking over you from the backlog.
**How it connects:** Gemini VAD → `interrupted` → `/ws/call` text frame → `player.flush()`. Phase 3's mascot will use the same control channel (thinking / speaking states).
**Try it yourself:** Call → ask "Tell me a long story about a fox" → start talking mid-story → Koe goes silent and answers your new words. Test: `uv run pytest -q` (the fake session sends `interrupted`; the browser must receive the JSON event).
**Gotchas:** Use headphones: on speakers, Koe's own voice can leak into the mic and "interrupt" itself, although the browser's echo cancellation usually prevents this.
**Measured:** real Gemini, scripted (speak → wait for 0.5 s of Koe's reply → talk over it), 3 runs: `interrupted` arrives **459 / 489 / 516 ms** after you start talking. That's Gemini's VAD needing about half a second of speech to be sure; the local flush after that is effectively instant.
**Interview line:** "Barge-in needed a client-side flush, because the model streams audio faster than real time and the browser holds a backlog. A control frame on the same socket stops every scheduled buffer, and interruption lands in about 0.5 s."

## Step 11: measuring latency honestly  (Phase 1 · Slice 5 · 2026-10-12)
**Files:** backend/koe/voice_call.py (per-turn latency, call summary, `latency` event, mic reader/uploader split, odd-byte guard) · backend/tests/test_voice_call.py (latency events, `rms`, `summarize`)
**What it does:** For every turn the backend logs `turn latency: speech end -> first audio N ms`, sends `{"type":"latency","ms":N}` to the browser (for the UI), and when the call ends logs `call ended: X turns, p50 …, p95 …`.
**Core concept:** *Measuring "you stopped talking".* Gemini decides end-of-speech internally and doesn't tell us when, so the backend runs its own tiny *energy detector*: the **RMS** (root mean square, roughly "loudness") of each 40 ms mic chunk. Chunks above 500 count as voice; the last voiced chunk's arrival time is "speech end", and the first audio of Koe's next turn closes the measurement. *p50 / p95:* the median turn, and the turn that 95% of turns are faster than. p95 catches the bad moments users remember.
**How it connects:** mic reader → timestamps voice → queue → uploader → Gemini … → first audio → latency event → browser (the UI agent can show it).
**Debugging story (worth rereading):**
1. The first numbers disagreed between my test script (end of *file*) and the backend (end of *voice*). The test WAV had **0.36 s of quiet after the voice**, so the script, and my earlier Slice 3 "1.09 s" claim, were about 0.4 s too optimistic. Corrected.
2. One call took 7.7 s while the backend reported 3.1 s. Cause: the relay read a mic chunk and then *waited for the upload to Gemini* before reading the next. When the upload stalled (the internet was dropping: `getaddrinfo failed`), mic chunks piled up unread and the latency clock started late, **hiding the stall**. Fix: a **reader** task timestamps chunks on arrival and puts them on an `asyncio.Queue`; a separate **uploader** task drains it to Gemini. Three tasks now run under one TaskGroup.
3. A test sent a 5-byte message, and `rms()` crashed the whole call. Untrusted input must not kill a call, so odd bytes are now ignored.
4. A remaining 50–265 ms difference between script and backend is unexplained (part of it is the script's own 40 ms send pacing). The true user-perceived number should come from the browser.
**Try it yourself:** make a call, then read the backend terminal: one `turn latency` line per answer, and a `call ended` summary when you hang up.
**Measured (2026-10-12, scripted 2.3 s utterance, real Gemini, localhost):**
| What | p50 | n |
|---|---|---|
| Gemini direct (no Koe backend) | 1,551 ms | 1 |
| Koe backend metric | ~1,700 ms (1,535–2,147) | 16 |
| Test client end to end | ~1,850 ms | 16 |
| SPEC target | ≤ 1,500 ms | |
So we're **≈0.2–0.35 s over target**, mostly in Gemini's end-of-speech wait plus first-audio generation. Next lever: tune Gemini's VAD end-of-speech settings, then re-measure.
**Interview line:** "I instrumented speech-end → first-audio per turn, found my own test was 0.4 s optimistic and that a blocking relay hid upstream stalls from the metric, fixed both, and reported p50 1.7 s against a 1.5 s target instead of the flattering number."

## Step 11: five UI directions to choose from  (Phase 3 prep · 2026-10-12)
**Files:** frontend/design/index.html · base.css · koe.js · v1-kasumi.html · v3-ma.html · v5-utsuwa.html (all new; v2 Hibiki and v4 Kotoba were built, then dropped by the user) · .claude/launch.json (new, dev server for the preview pane)
**What it does:** Five static design variants of the three pages Koe needs: **Call** (mascot slot, call button, live captions), **Today** (calendar + GitHub) and **Activity** (approvals, log, latency). All five share the same fonts; each one changes layout, colour, elements and buttons. Open http://localhost:5173/design/ while `npm run dev` runs.
**Core concept:** *Explore cheap, build once.* Plain HTML + CSS mockups cost minutes and touch nothing in the real app, so we can compare five directions side by side, pick one, and only then port it into React. The pages share one tiny script: the URL hash (`#call`, `#today`, `#activity`) picks which `<section>` is visible, and a fake call sets `body[data-state]` to listening, thinking or speaking. Each variant's CSS reacts to that one attribute, which is the same contract the real mascot will use (SPEC §6 states).
**How it connects:** `koe.js` → `body[data-state]` → each variant's CSS (orb, rings, ensō, ASCII field, glowing eyes). When a variant is chosen, its tokens become `index.css` and the state attribute will be driven by the real call (`/ws/call` + `AnalyserNode`).
**Try it yourself:** open the gallery, pick a variant, press Call and watch the mascot slot cycle through states; on Activity, press Approve. Resize to phone width: every page collapses to one column.
**Gotchas:** Google Fonts' `text=` parameter downloads only the kanji we use (声響間言葉器霞), so the Japanese font stays tiny. The inspiration images in `frontend/assets/` are references only; one carries a stock watermark, so none are embedded in the pages.
**Measured:** latency numbers on the pages are the real Step 9 and 10 measurements (p50 1.09 s first audio, 0.49 s barge-in). Everything else is sample data.
**Interview line:** "I explored five visual directions as throwaway static mockups that share one state contract with the future mascot, then chose one before writing any React."

## Step 12: tuning Gemini's end-of-speech detection (reverted)  (Phase 1 · 2026-10-12)
**Files:** none kept. backend/koe/voice_call.py was changed, measured, and reverted.
**What it does:** Nothing ships. This entry records an experiment so nobody repeats it blindly.
**Core concept:** *Measure → change one thing → re-measure under the same conditions → keep only a real win.* Gemini Live lets you tune its VAD: `silence_duration_ms` (how much silence before it decides you're done; Google recommends 500–800 ms) and `end_of_speech_sensitivity` (HIGH = decide sooner). Faster end-pointing should cut latency, but too eager and Koe interrupts you when you pause to think. *Interleaving* (A, B, A, B… in the same minutes) makes network drift hit both configs equally; *paired wins* (did B beat A in the same round?) are more telling than comparing two medians.
**Measured (direct to Gemini, scripted 2.28 s utterance; ledger):**
| Experiment | default p50 | tuned (HIGH + 500 ms) p50 | tuned faster in | cut-ins |
|---|---|---|---|---|
| #1: 4 configs × 8 interleaved rounds | 1,542 ms | 1,402 ms | 8/8 rounds | 0 |
| #2: repeat, 2 configs × 10 rounds | 1,429 ms | 1,496 ms | 5/10 rounds | 0 |
(#1 also tried HIGH alone, p50 1,414, and 500 ms alone, p50 1,392; both 6/8.)
**Verdict: reverted.** The 140 ms win in #1 didn't reproduce in #2: within noise. Gemini's own response time drifts ±150 ms between sessions, more than the effect. A neutral change still costs something (a more eager VAD can cut the user off), so it doesn't stay.
**What this tells us:** Gemini itself takes ~1.4–1.55 s (voice end → first audio). The Koe backend metric reads ~1.7–1.8 s, so ~150–250 ms is added between the scripts and the backend, not yet explained (see Step 11). Next places to look: measure again on the Linux Azure VM in Phase 7 (Windows event loop and dev laptop vs prod), and have the browser measure the user-perceived number.
**Interview line:** "I A/B-tested Gemini's VAD settings with interleaved runs. A 140 ms win didn't reproduce, so I reverted it and logged it rather than shipping noise."

## Step 13: 3D mascot spike, a VRM avatar that lip-syncs to Koe  (Phase 3 · 2026-10-12)
**Files:** frontend/src/mascot/mascot.ts (new) · frontend/src/call/player.ts (AnalyserNode) · frontend/src/App.tsx (canvas, lazy load) · frontend/src/index.css · frontend/package.json (`three`, `@pixiv/three-vrm`, `@types/three`) · .gitignore (sample model) · docs: SPEC §6, TECH_STACK, ARCHITECTURE, DECISIONS, RESEARCH_SOURCES
**What it does:** The call page shows a 3D anime girl (pixiv's free sample VRM, a placeholder until our own VRoid model exists). She breathes, sways, blinks every 2–6 s, looks at you, and her mouth opens and closes with Koe's voice.
**Core concept:** *A VRM is a 3D model with a face contract.* VRM is glTF (the "JPEG of 3D") plus a standard list of **expressions**: mouth vowels `aa ih ou ee oh`, `blink`, `happy`, `sad`… So "open the mouth 60%" is one call, `expressionManager.setValue('aa', 0.6)`, on *any* VRM, including the one you'll make in VRoid. *Lip sync by loudness:* every chunk Koe says flows through one `AnalyserNode` on its way to the speakers; 30 times a second the mascot reads the last 2048 samples, takes the **RMS** (same loudness idea as Step 11), and maps it to the mouth, opening fast and closing a bit slower so it doesn't flicker. *Why it can't hurt latency:* the mic runs on the audio thread (AudioWorklet), the drawing runs on the GPU, and what's left on the main thread is ~1 ms per frame. The three.js code (~186 kB gzipped) and the 10 MB model load **after** the page in their own chunk (`import()`), so the Call button never waits for them.
**How it connects:** `createPlayer()` → `analyser` → `mascot.listen(analyser)` → each frame: RMS → `setValue('aa')` → `vrm.update()` → `renderer.render()`. Phase 3 states (thinking, happy, error) will set more expressions from the `/ws/call` control events.
**Try it yourself:** the sample model isn't in git (10 MB). Download it once:
`curl -L -o frontend/public/mascot/sample.vrm https://raw.githubusercontent.com/pixiv/three-vrm/dev/packages/three-vrm/examples/models/VRM1_Constraint_Twist_Sample.vrm`
then `npm run dev`, open http://localhost:5173, press Call, ask something, and watch her mouth.
**Gotchas:** VRMs load in a **T-pose**, so the code rotates the upper arms down. `chest`/`neck` bones are optional in VRM, so the idle motion uses the required `spine`/`head`. React StrictMode mounts twice in dev, so `dispose()` must free the WebGL objects, and a model that finishes loading after unmount is thrown away. `requestAnimationFrame` stops when the tab is hidden: free battery saving, but it also means a hidden browser shows a frozen mascot (by design).
**Measured (dev build, 2026-10-12):**
| What | Value |
|---|---|
| Mascot frame cost (main thread) | p50 1.2 ms · p95 1.9 ms · max 2.5 ms, at 29.9 fps |
| Main-thread queue delay (how long a WebSocket audio frame would wait), mascot off → on | p50 0.1 → 0.1 ms · p95 0.2 → 0.2 ms · max 0.5 → 2.8 ms |
| Real Gemini call, speech end → mascot's mouth starts moving (browser clock, scripted TTS utterance) | 816 ms and 891 ms (2 calls) |
| Mouth gain 8 → 5 | gain 8 pinned the mouth open (p50 0.79, many frames at 1.0); gain 5: p50 0.61, fully open 1% of frames |
| Bundle | main chunk 71 kB gzip; mascot chunk 186 kB gzip (lazy) |
Worst case adds < 3 ms to a ~1,700 ms voice turn: **0.2%**. The spike's question ("does 3D cost latency?") is answered: no.
**Interview line:** "Before committing to a 3D avatar for a voice agent, I measured its main-thread cost and the task-queue delay it adds to incoming audio frames: about 1 ms per frame and no change at p95. Then I lazy-loaded it so the call path never waits on three.js."

## Step 13: calls that outlive Gemini's connection limits  (Phase 1 · Slice 6 · 2026-10-12)
**Files:** backend/koe/voice_call.py (`CallState`, `_relay_gemini` reconnect loop, resumption + context compression in `CONFIG`) · backend/tests/test_voice_call.py (fake GoAway, fake drop)
**What it does:** One browser call can now span several Gemini connections. The backend asks Gemini for **session-resumption handles** from the start and always keeps the newest. When Gemini sends **GoAway** ("I'll close soon"), or the connection drops unexpectedly (a network blip), the backend opens a new connection with that handle and carries on. The browser's WebSocket never closes. **Context-window compression** (a sliding window) lifts the 15-minute audio-session cap by trimming the oldest context.
**Core concept:** *Separate the logical session from the physical connection.* What you experience as "the call" is the browser ↔ backend WebSocket plus Gemini's conversation state. The Gemini WebSocket underneath is replaceable, and the **handle** is the key that re-attaches a new connection to the old conversation (valid for 2 h). That's why the code splits into a long-lived part (`_read_mic`, the queue, `CallState`) and a per-connection part (`_upload_mic`, `_gemini_to_browser`) inside a `while True` reconnect loop. *Back-off:* three connections in a row that die within 30 s means something is really wrong, so give up instead of looping forever, waiting a little longer each time.
**How it connects:** browser ⇄ `/ws/call` (one socket for the whole call) ⇄ `_relay_gemini` ⇄ Gemini connection #1, #2, … (same conversation).
**Try it yourself:** `uv run pytest -q`: `test_goaway_resumes_on_new_connection_with_latest_handle` and `test_unexpected_drop_resumes_with_handle`.
**Verified against real Gemini:**
- **Resumption keeps the conversation** (the docs don't say so): connection 1, "my codename is Blue Lotus" → reconnect with the handle → connection 2, "What's my codename?" → Koe: *"Your secret project codename is Blue Lotus."*
- **A 13-minute scripted call:** Koe answered in all 13 minutes. Gemini did **not** send GoAway on that connection, so the ~10-minute connection lifetime isn't strict in practice, and my GoAway branch has only run against the fake. A 20-minute call is being run to catch a real one (result to be added).
- That call's latency: p50 1,636 ms, p95 4,291 ms (13 turns). The p95 came from a few 3–4 s turns early in the call, likely network.
**Gotchas:** Up to one 40 ms mic chunk can be lost during a reconnect if it was mid-upload (`last_consumed_client_message_index` could replay it; not worth the code yet).
**Interview line:** "I separated the logical call from the model connection: resumption handles let the backend swap Gemini connections under a live call (on GoAway or network drops) without the user noticing, and I verified the model really keeps context across a resume."
