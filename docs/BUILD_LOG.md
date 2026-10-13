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
- **A 13-minute scripted call:** Koe answered in all 13 minutes. Gemini did **not** send GoAway on that connection, so the ~10-minute connection lifetime isn't strict in practice, and my GoAway branch has only run against the fake. A 20-minute call (Step 14) answered in all 20 minutes, again with **no GoAway**: with context compression on, Gemini held one connection past both the ~10 min and 15 min limits. The GoAway branch is still only tested against the fake.
- That call's latency: p50 1,636 ms, p95 4,291 ms (13 turns). The p95 came from a few 3–4 s turns early in the call, likely network.
**Gotchas:** Up to one 40 ms mic chunk can be lost during a reconnect if it was mid-upload (`last_consumed_client_message_index` could replay it; not worth the code yet).
**Interview line:** "I separated the logical call from the model connection: resumption handles let the backend swap Gemini connections under a live call (on GoAway or network drops) without the user noticing, and I verified the model really keeps context across a resume."

## Step 14: a flaky test that was hiding a real bug  (Phase 1 → 2 · 2026-10-12)
**Files:** backend/koe/voice_call.py (uploader in a TaskGroup; re-raise swallowed cancellation) · backend/tests/test_voice_call.py (rewritten around a fake browser socket)
**What happened:** The barge-in test started failing **6 times in 10**. My first guess (the uploader was a "loose" `asyncio.create_task` that was never awaited) was plausible, and I fixed it properly with a TaskGroup, but failures went *up* to 17/20. So I stopped guessing and logged how the app exited. In every failing run the app's task **was being cancelled** (`cancelling()=4`) yet it **returned normally**.
**Core concept:** *Cancellation must never be swallowed.* When the user hangs up (`WebSocketDisconnect`) at the same moment the server cancels the call (shutdown), the TaskGroup reports only the hang-up error. Our `except* WebSocketDisconnect: pass` then ate it, and the cancel request with it. Python's rule: code that absorbs a cancellation must re-raise it, so `call()` now re-raises `CancelledError` if its task is still being cancelled.
**The other half:** Starlette's threaded `TestClient` hangs up and then *immediately* cancels the app without waiting. Real uvicorn delivers the hang-up and lets the app finish. That race is a test-harness artifact, so the tests now call `call()` directly with a **FakeBrowser** (an asyncio-queue WebSocket) in one event loop. That's deterministic, and every test now also asserts that **hanging up ends the call cleanly within 3 s**, which the old tests never checked. Determinism also exposed a real (documented) edge: audio sent in the instant between GoAway and the new connection can go to the old one and be lost.
**Measured:** flaky rate 60% → **0 failures in 25 full-suite runs**. 20-minute real call: answered **20/20 minutes**, p50 1,607 ms, p95 2,690 ms, no GoAway, no drops.
**Interview line:** "A flaky test turned out to be a swallowed cancellation: hang-up and shutdown racing inside a TaskGroup. I proved it by logging the task's cancel count, fixed the real bug, and replaced a racy threaded harness with a deterministic in-loop fake."

## Step 15: webhooks in, GitHub alerts out  (Phase 5 · built in parallel with Phase 2 · 2026-10-12)
**Files:** backend/koe/github_hooks.py (new) · backend/koe/whatsapp.py (new) · backend/koe/main.py · backend/koe/config.py · backend/.env.example · backend/tests/test_github_hooks.py (new) · backend/tests/test_whatsapp.py (new) · docs: SPEC §4, PLAN, DECISIONS, RESEARCH_SOURCES
**What it does:** Two new public endpoints. `POST /webhooks/github` receives GitHub events, checks they really came from GitHub, ignores repeats, and turns the 4 interesting ones (CI failed on my PR, review requested from me, my PR merged, changes requested on my PR) into a one-line WhatsApp alert. `GET/POST /webhooks/whatsapp` does Meta's verification handshake and receives messages, keeping only ones from your allow-listed number.
**Core concept:** *Webhooks: "don't call us, we'll call you."* Instead of polling GitHub every minute, GitHub POSTs to us the moment something happens. Since the URL is public, anyone could POST fake events, so both GitHub and Meta **sign** each body: `HMAC-SHA256(shared secret, raw body)` in the `X-Hub-Signature-256` header. We recompute it and compare in **constant time** (`hmac.compare_digest`, so an attacker can't guess the signature byte by byte from response timing). An **empty secret is rejected**, because anyone can compute an HMAC with an empty key: *fail closed*. Then **ack fast, work later**: GitHub gives up after 10 s, so the reply is sent first and the WhatsApp send runs as a FastAPI `BackgroundTask` after the response. *Idempotency:* GitHub can redeliver the same event (same `X-GitHub-Delivery` ID), so we remember IDs and skip repeats. *Rules, not an LLM:* alerts are plain `if`s, so they're instant, free and fully testable.
**How it connects:** GitHub → `/webhooks/github` → `valid_signature` → dedupe → `alert(event, payload, GITHUB_LOGIN)` → background `send_alert` → `whatsapp.send_text` (allow-list enforced) → Meta Send API. Meta → `/webhooks/whatsapp` → signature → `inbound_messages` (allow-list) → `handle_message` (only logs for now; Phase 2's text loop plugs in here).
**Try it yourself:** `uv run pytest -q tests/test_github_hooks.py tests/test_whatsapp.py`. The first test checks our HMAC against **GitHub's own published test vector**. For a real delivery: set `GITHUB_LOGIN` and `GITHUB_WEBHOOK_SECRET` in `.env`, run `cloudflared tunnel --url http://localhost:8000`, then in a repo go to Settings → Webhooks → Add: URL `<tunnel>/webhooks/github`, content type `application/json`, the same secret, and the events *Workflow runs, Pull requests, Pull request reviews*. GitHub sends a `ping`, which should show a green tick in "Recent deliveries".
**Gotchas:** GitHub Actions fires **both** `check_suite` and `workflow_run` for one CI failure, so we use only `workflow_run` to avoid double alerts. `workflow_run.pull_requests` has no author, so "my PR" means "I triggered the run" (fine for PRs you push to). A **team** review request has no `requested_reviewer`, and with an empty `GITHUB_LOGIN`, `"" == ""` would have matched "me", so an empty login now disables alerts. Dedupe is an in-memory set that's forgotten on restart; it moves to SQLite (`github_deliveries`) when `store.py` lands. **WhatsApp sends still fail on Meta's side (131031, business verification)**, so alert sends are logged as failed and the webhook still returns 200. The `koe_alert` template (for alerts outside the 24 h window) waits on the same verification.
**Measured:** 24 tests pass. Real app on uvicorn with curl: a signed `workflow_run` gave the 🔴 alert, the same delivery ID again gave `duplicate`, a forged signature gave 401, and Meta's handshake echoed the challenge. A real GitHub → tunnel delivery isn't done yet (it needs a webhook added in your repo settings).
**Interview line:** "My GitHub→WhatsApp alerts are deterministic rules behind HMAC-verified, idempotent webhooks. They ack within milliseconds and do the slow send in the background, and they fail closed on a missing secret."

## Step 16: Koe can check GitHub by voice  (Phase 2 · Slice 1 · 2026-10-12)
**Files:** backend/koe/agent.py (new: persona prompt, tool registry, `declarations()`, `run_tool()`) · backend/koe/tools/github.py (new: `github_review_queue`, `github_my_prs`) · backend/koe/voice_call.py (tools in the Live config, `_run_tools`, `tool` events) · tests: test_agent.py, test_github_tools.py (new), test_voice_call.py (tool-call relay)
**What it does:** Ask on the call "what's waiting for my review?" or "how are my PRs doing?". Gemini decides to call a tool; the backend runs it against GitHub and sends the result back, and Koe speaks a summary. The browser gets `{"type":"tool",…,"phase":"start"}` / `"end"` events (for a "thinking" mascot).
**Core concept:** *Function calling.* We give the model a menu (each tool's name, a description, and a JSON Schema of its arguments). The model **chooses** when to call and with which arguments; **our code** does the work and returns plain JSON. The model never touches GitHub. So the rules that matter (validate the `repo` argument, no merge tool, errors as data not exceptions, write tools fail closed until the approval gate exists) live in code where they can be tested, not in the prompt. Live API tool calls are *blocking*: Gemini waits for our result, and the prompt asks it to say "let me check" first so the silence isn't dead air.
**Why GraphQL:** one GitHub GraphQL search returns each PR's CI rollup, review decision, conflicts and size, where REST would need ~3 calls per PR.
**How it connects:** voice → Gemini → `tool_call` → `voice_call._run_tools` → `agent.run_tool` → `tools/github.py` → GitHub → `FunctionResponse` → Gemini speaks. WhatsApp and evals will reuse `agent.run_tool` unchanged.
**Try it yourself:** Call → "Koe, what's the status of my open pull requests?". Backend log: `tool github_my_prs({'state': 'open'}) … ms ok=True`. Tests: `uv run pytest -q` (GitHub faked with `respx`; Gemini faked with a FakeSession).
**Measured (real voice question through the backend, real GitHub):** Gemini picked `github_my_prs(state="open")` by itself. Koe's answer, transcribed, matched GitHub (1 open PR, no review yet); nothing invented. **The tool took 4.2 s.** Measuring (not guessing) showed the GraphQL query itself takes ~0.93 s on a warm connection and trimming fields barely mattered (0.83–1.0 s). The cost was a **new HTTP client per call**: DNS + TCP + TLS handshakes at ~400 ms round trip from India. Fix: one reused client with 2-minute keep-alive → **0.83–1.67 s per call** (was 3.1–4.3 s). After about 60 s idle GitHub seems to drop the connection (~+0.4 s).
| Idea | Before → after | Verdict |
|---|---|---|
| Drop `mergeable` / CI / fewer results from the query | 0.93 s → 0.83–1.05 s | not worth it (noise) |
| Reuse one HTTP client (keep-alive) | 3.1–4.3 s → 0.83–1.67 s | **kept** |
**Gotchas:** "Let me check" itself arrived 4 s after the question on that run, well above our usual ~1.7 s. One sample only, so watch it. GitHub's `mergeable` is often `UNKNOWN` at first (computed lazily); Koe says "still checking" rather than guessing.
**Interview line:** "Tools are a JSON-Schema menu the model chooses from, but the rules live in tested code. When the first voice tool call took 4 s, I measured the query vs the connection and found handshake cost, not the query, so connection reuse cut it to about 1 s."

## Step 17: your VRoid models, moods, and softer shading  (Phase 3 · 2026-10-12)
**Files:** frontend/src/mascot/mascot.ts (moods, auto-framing, shading) · frontend/src/App.tsx (model picker, events → moods) · frontend/public/mascot/{akane,kami,miku}.vrm (git-ignored) · .gitignore · docs: SPEC §6, DECISIONS
**What it does:** The three models you exported load in the call page with a picker (`?model=akane|kami|miku|sample`). She frames herself head-and-shoulders, her shading is softer, and she reacts to the call: listening nods, a "thinking" glance while a tool runs, a happy hop when it succeeds, a sad dip when it fails.
**Core concept:** *State machine + easing.* The mascot keeps one **base mood** (idle / listening / thinking) and an optional short **reaction** (happy / sad) with an expiry time. Each frame it looks up the target face and pose for the current one and moves a fraction of the way there (`value += (target − value) × min(1, dt × 4)`), so every change glides in about 0.25 s instead of snapping. *Events, not polling:* the backend already sends `{"type":"tool","phase":"start"|"end","ok":…}` on `/ws/call`, so App maps those straight to `mood('thinking')` and `react('happy'|'sad')`. *Shading:* VRoid exports use the **MToon** shader; lowering `shadingToonyFactor` widens the light→shadow gradient, pulling `shadeColorFactor` toward the lit colour removes the harsh pink shadow, and scaling `outlineWidthFactor` thins the outlines. All three are knobs in `SOFTEN`.
**How it connects:** `/ws/call` text frame → App `onmessage` → `mascot.mood()` / `mascot.react()` → per frame: expression weights + head bone + gaze target → `vrm.update()` → render.
**Try it yourself:** `npm run dev`, open http://localhost:5173/?model=kami, switch models with the picker, start a call and ask "what are my PRs?": she looks away while the GitHub tool runs, then smiles.
**Gotchas:**
- VRoid's `happy` expression already squints, and blink adds on top (its `overrideBlink` is `none`), so blinking is scaled by `1 − happy`.
- The hips bone isn't at height 0 in its rest pose: the hop adds to the stored rest height. Writing `y = hop` would drop her to the floor.
- **Testing in a hidden browser pane lies.** `requestAnimationFrame` stops, `setTimeout` is throttled to ~1/s, and screenshots don't refresh the WebGL canvas. Three "it doesn't work" results were test artefacts. The proof came from reading the face mesh's `morphTargetInfluences` directly.
**Measured (dev build, hidden pane with a 60 Hz test pump, each model from a fresh page load):**
| Model | Triangles | Hair-bone chains | Frame p50 | p95 | max |
|---|---|---|---|---|---|
| sample (baseline) | — | — | 2.5 ms | 4.1 ms | 6.3 ms |
| miku | 33.6k | 15 | 2.5 ms | 4.0 ms | 11 ms |
| kami | 49.6k | 36 | 4.2 ms | 7.1 ms | 24 ms |
| akane | 43.5k | 36 | 4.5 ms | 8.0 ms | 25 ms |
| Mood weights on the face mesh | | | happy **0.70** after `ok:true`, sad **0.60** after `ok:false`, both **0.00** ~3 s later | | |
These run ~2× the Step 13 numbers for the same sample model (that run used a visible pane), so compare models with each other, not with Step 13. Hair physics is the cost: 36 bone chains cost ~1.8× the 15-chain model, with occasional ~25 ms spikes. That's still small next to a ~1.7 s voice turn, but if akane or kami wins, re-export with fewer hair bone groups.
**Interview line:** "I drove the avatar's moods from the same WebSocket control events the agent already emits, eased every change with a one-line exponential approach, and proved it with mesh morph-target values, because screenshots of a hidden browser pane were lying to me."

## Step 18: seven UIs, each with the real mascot  (Phase 3 · 2026-10-12)
**Files:** frontend/design/v6-mizu.html · v7-monogatari.html · v8-kagura.html · v9-gin.html · stage.js · img/miku.jpg · img/kami.jpg (new) · v1-kasumi.html · v3-ma.html · v5-utsuwa.html · koe.js · index.html (changed) · frontend/src/mascot/mascot.ts (framing + interaction) · frontend/src/App.tsx + index.css (design launcher on the home route)
**What it does:** Four new UI directions shaped around the two mascots: **Mizu** (teal bubbles, for Miku), **Monogatari** (a visual-novel screen with a dialogue box and choices, for Miku), **Kagura** (shrine stillness in an arch, for Kami), **Gin** (silver fashion editorial, for Kami). The three earlier ones (Kasumi, Ma, Utsuwa) now hold the real mascot too. Every page shows her from the hair to the knees, has a Miku / Kami switch, and makes a **real call** when the backend runs. The home route lists all seven, each with both mascots. She also reacts to you: her eyes follow the cursor, a tap surprises or pleases her, and a drag turns her.
**Core concept:** *Framing from the skeleton.* Every VRM has the same named bones, so the camera can be placed from the model itself: the head bone (base of the skull) × 1.2 gives the top of the hair, the knee bone × 0.85 gives the bottom, and the camera distance follows from the field of view (`distance = height / (2·tan(fov/2))`). That's why tall, short and chibi models all fit without hand-tuned numbers. For interaction, the pointer is converted to −1…1 canvas coordinates; the eyes look at the point in the viewer's plane that lines up with the cursor, and a `Raycaster` (a line from the camera through the tap) tells head from body by comparing the hit height with the head bone.
**How it connects:** design page → `stage.js` → `createMascot(canvas, url, 'body')` + `startMic` + `createPlayer` + `/ws/call` (the same pieces `App.tsx` uses) → `body[data-state]` (connecting, listening, thinking, speaking), which each variant's CSS styles. Speaking = Koe's audio is loud (RMS > 0.01, held 0.4 s so pauses between words don't flicker).
**Try it yourself:** run the backend and `npm run dev`, open http://localhost:5173, choose a design and a mascot, press Call. Move the mouse around her, tap her face, drag her sideways.
**Gotchas:** a hidden browser tab or pane pauses `requestAnimationFrame`, so WebGL screenshots of a hidden pane show an empty frame even though the model loaded; check the network log (`miku.vrm` 200) or look with the pane visible. Raycasting a 34 to 50k triangle skinned mesh is too slow for every frame, so it only runs on a tap.
**Measured:** all 7 variants × 3 pages at 1280 px and 375 px: correct page shown, no horizontal overflow (one 16 px overflow on Ma at phone width was found and fixed). No console errors when switching mascots or tapping and dragging her.
**Interview line:** "The camera frames the avatar from its own skeleton, so any VRM fits a three-quarter shot, and interaction is cheap because raycasting only happens on a tap."

## Step 19: a calm home, a call panel you can chat in, and a mascot that moves on her own  (Phase 3 · 2026-10-12)
**Files:** frontend/src/App.tsx (rewritten) · frontend/src/index.css (rewritten) · frontend/src/call/useCall.ts (new) · frontend/src/mascot/mascot.ts (shots, idle routines, touch zones) · frontend/index.html (fonts, theme before first paint) · backend/koe/voice_call.py (transcripts, typed text) · backend/tests/test_voice_call.py · frontend/design/ (deleted)
**What it does:** The home page shows Kami as a half figure on one side of a dark, flat page, next to today's calendar, GitHub and approvals. Press **Call Koe** and a panel slides in (Shoji: from the right; Engawa: a sheet rises), while she moves into a full-figure shot. The panel shows the conversation as text as it happens, lets you type instead of talk, and has mute and end. She moves on her own: she fixes her hair, looks around, tilts her head, shifts her weight, and reacts to where you tap her.
**Core concept:** *Move the camera, not the canvas.* The mascot lives on one transparent canvas that covers the window. To put her on the right, the camera's view window is shifted (`setViewOffset`) instead of moving the canvas; to go from half to full figure, the camera dollies back. So the panels can slide using only `transform` (cheap, GPU-composited), and WebGL never has to reallocate its drawing buffer mid-animation. *Gestures as data:* each idle routine is a small function from progress (0 to 1) to bone rotations, multiplied by an envelope that eases it in and out, then blended into the rest pose, so routines never snap. *Transcripts for free:* Gemini Live can transcribe both sides of the audio (`input_audio_transcription`, `output_audio_transcription`); the backend forwards each piece as a `transcript` event, and typed text goes into the same session with `send_realtime_input(text=...)`.
**How it connects:** `App` → `useCall` (mic, player, `/ws/call`, transcript lines, mute) → mascot `mood/listen/react/gesture`; `App` → mascot `shot(bust|full, x)` from layout + call state; `voice_call.py` → `transcript` / `turn_complete` events; browser text frames → `_read_mic` → the same upload queue as audio.
**Try it yourself:** backend on :8000, `npm run dev`, open http://localhost:5173. Switch layout, mascot and theme in the header. Tap her hair, face and hands; drag her sideways. Press Call, say something, or type in the box.
**Gotchas:** (1) `setViewOffset`'s x is where the *window* starts: a positive offset moves the view right, so she appears *left*. I flipped the sign once by mistake and caught it from a screenshot. (2) Arm poses were tuned by eye: on her right arm, −z raises the upper arm and folds the forearm up, +y swings the upper arm forward, −y swings the forearm in toward her head. (3) A hidden browser pane freezes WebGL and CSS transitions, so screenshots lie; layout was checked by measuring with transitions turned off.
**Measured:** typed chat end-to-end against the real Gemini Live session: answer audio (~6 s of speech), the transcript "I'm Koe, your friendly voice assistant...", a latency event and `turn_complete`. Backend tests: 46 pass (2 new: transcripts reach the browser; typed text reaches Gemini, bad frames are ignored, long text is capped). Layout: both layouts × 1280 px / 375 px × home / call: no sideways scroll; closed panels fully off-screen, open ones in place.
**Interview line:** "The 3D mascot is placed by the camera, not by CSS, so the call panel animates with transforms alone, and the chat is just Gemini Live's own transcription plus typed text into the same session."

## Step 20: durable proposals and activity in Supabase (Phase 2 · 2026-10-12)
**Files:** backend/koe/store.py · backend/migrations/001_phase2.sql · backend/koe/config.py · backend/.env.example · backend/scripts/verify_store_sql.py · backend/tests/test_store.py
**What it does:** Stores pending actions and their approved, rejected, expired and completed outcomes in managed PostgreSQL. Activity includes conversation identity and tool timing. The migration reserves daily-note and webhook-delivery tables for later phases without changing those features yet.
**Core concept:** *Atomic claim.* An approval updates a pending row only when its owner, conversation and action ID match. PostgreSQL returns the row to exactly one caller; only that caller can execute the write. A transaction lock also prevents two different pending proposals in the same conversation. RLS and grants keep these tables and RPC functions accessible only to the backend service role.
**How it connects:** agent proposal → backend-only PostgREST RPC → pending row → explicit user confirmation → claim RPC → Calendar write → finish RPC and audit entry.
**Try it yourself:** Apply the migration in Supabase SQL Editor, fill the two Supabase settings in backend/.env, then follow docs/PHASE2_SETUP.md. With local PostgreSQL binaries installed, run `uv run python -m scripts.verify_store_sql` from backend to exercise the migration against a disposable local database.
**Gotchas:** Google and PostgreSQL cannot share one transaction. If an external write succeeds but recording its outcome fails, check Calendar before trying again. The app deliberately avoids automatic retries of uncertain writes. Supabase Auth login is a later feature; this single-user phase uses a private application access token.
**Measured:** Migration applied twice without losing data in a disposable PostgreSQL instance. Four simultaneous approval claims produced exactly one winner. Owner/conversation isolation, expiry, rejection, audit records and service-role permissions passed. The user's hosted Supabase project remains unverified until credentials and the migration are supplied.
**Interview line:** "I used a conditional database update as the execution gate, so duplicate confirmations cannot independently authorize the same action, and I made uncertain cross-service outcomes explicit instead of retrying a potentially completed write."

## Step 21: Google consent and conflict-aware Calendar tools (Phase 2 · 2026-10-12)
**Files:** backend/koe/google_auth.py · backend/koe/tools/calendar.py · backend/scripts/google_auth.py · backend/scripts/check_setup.py · backend/scripts/smoke.py · backend/tests/test_google_auth.py · backend/tests/test_calendar.py · backend/pyproject.toml
**What it does:** Adds Calendar listing, free-time search, and proposed event creation or movement. A one-time Desktop OAuth consent script obtains a refreshable local token; Sheets permission is optional. The server refreshes existing consent without opening an interactive login.
**Core concept:** *Normalize, then validate again at the boundary.* Event times require explicit offsets and are converted to the configured IANA timezone. Availability accounts for paginated events and all-day ranges. Immediately before an approved write, the tool checks conflicts again. Moving an event excludes that event from the conflict check and uses its ETag to detect concurrent edits.
**How it connects:** Google Cloud Desktop client → local consent script → ignored token.json → backend token refresh → Calendar REST API. The agent can read directly, but event writes require the durable approval gate from Step 20.
**Try it yourself:** Follow the Google Cloud checklist in docs/PHASE2_SETUP.md, save the downloaded Desktop client JSON as backend/credentials.json, then run `uv run python -m scripts.google_auth` from backend. Add `--with-sheets` if Sheets access is wanted. Run `uv run python -m scripts.check_setup` for read-only connectivity checks.
**Gotchas:** An API key cannot authorize access to a private calendar; OAuth consent is required. External apps in Google's Testing mode can have short-lived refresh tokens. Windows needs the tzdata package for IANA zones. The process lock cannot stop another calendar application from inserting an overlapping event between our final check and write. Recurring-event edits are deliberately refused.
**Measured:** Tests cover timezones, all-day events, pagination, conflict rejection, ETag handling, refresh persistence and missing permissions. No real Google account was authorized and no real event was created during this build.
**Interview line:** "The model proposes a structured event, but tested application code normalizes times, checks availability and handles OAuth; the final conflict check happens after approval because availability can change while the user decides."

## Step 22: one approval flow across CLI, voice and call controls (Phase 2 · 2026-10-12)
**Files:** backend/koe/agent.py · backend/koe/text_agent.py · backend/koe/voice_call.py · backend/scripts/chat.py · backend/tests/test_approvals.py · backend/tests/test_text_agent.py · backend/tests/test_voice_call.py · backend/tests/conftest.py · frontend/src/call/useCall.ts · frontend/src/App.tsx · frontend/src/index.css · docs/PHASE2_SETUP.md
**What it does:** Adds a bounded text tool loop and connects the shared approval gate to typed replies, completed voice transcripts and Confirm/Cancel buttons. The call panel displays the actual stored proposal summary and expiry. Hosted calls require the private application token before opening a Gemini session.
**Core concept:** *Authorization comes from the user input boundary.* The model cannot approve its own tool call. Exact confirmation phrases resolve the current displayed proposal; partial transcripts and ambiguous sentences do not. Buttons send the particular action ID, and the database checks conversation ownership before execution. Gemini's model content is preserved between text-tool rounds, including its thought signatures.
**How it connects:** CLI or browser user input → conversation context → shared approval handler → atomic database claim → Calendar writer → authoritative result back to the UI and model. A separate queue records voice transcripts without inserting database requests into the audio relay path.
**Try it yourself:** Run `uv run python -m scripts.chat` after completing setup, ask to create a clearly timed event, inspect the proposal and reply `no` first. For the browser, enter KOE_ACCESS_TOKEN from backend/.env into the private access-token field before calling Koe. Confirm a real booking only when its displayed details are correct.
**Gotchas:** A model saying "approved" has no authority. Only a complete user utterance or explicit UI action can claim a proposal. Tokens stay in backend/.env and browser component memory, not URLs or frontend build settings. The home dashboard's sample data is still a placeholder; the call panel carries live proposals.
**Measured:** Final backend suite: 81 passed, with one existing Starlette deprecation warning; Python compilation passed. Frontend production build and lint passed. Browser checks at 1280 px and 375 px found no horizontal overflow or console warnings/errors on the home/access-token interface. Live authenticated calls and an approved booking still need the user's credentials; no end-to-end booking latency was measured.
**Interview line:** "I kept the authorization decision outside the model and reused the same durable gate for text, speech and buttons, while preserving the existing low-latency voice relay."

## Frontend slice: mascot profiles and dedicated Settings (2026-10-12)
**Files:** frontend/src/App.tsx · frontend/src/mascot/catalog.ts · frontend/src/mascot/MascotView.tsx · frontend/src/mascot/mascot.ts · frontend/src/settings/SettingsPage.tsx · frontend/src/settings/settings.css · frontend/public/mascot/aoi.vrm · frontend/public/mascot/kobashi.vrm · frontend/tests/mascot-preferences.test.mjs · .gitignore · docs/SPEC.md · docs/DECISIONS.md · change log.md
**What it does:** Adds Aoi and Kobashi alongside Kami and Miku, with a dedicated Settings → Profile page. Try one live mascot at a time, wave, trigger expressions or call moods, and inspect portrait/full-body views before explicitly choosing. Home renders the saved choice and retains theme/layout controls. Existing concurrent dashboard/call changes are preserved.
**Core concept:** Separate the temporary preview from the applied preference. Local Settings state lets users explore safely; only Choose updates App and localStorage. One shared rendering component owns model readiness, retry and disposal, so leaving a page cannot leave an extra animation loop or WebGL scene running.
**How it connects:** SettingsPage → preview MascotView → createMascot.ready; Choose → App state + koe-mascot → Home MascotView → the existing useCall mood/audio hooks. No new backend route or dependency. Hash navigation keeps direct Settings reloads simple.
**Try it yourself:** Run npm run dev from frontend, open Settings, preview all four, try Wave hello and Thinking, then choose Aoi or Kobashi. Return Home and reload. Change theme/layout on Home and revisit Settings. Full before/after details and integration notes are in change log.md.
**Gotchas:** Preferences are browser-local, not account-synced. A blocked storage write shows an explicit visit-only message. Settings is unavailable during a call. The four public VRMs are now allowed by .gitignore and must be included when committing; design sources remain ignored. The Graphify executable/interpreter path was stale, so source was inspected after consulting the existing report.
**Measured:** Seven frontend tests passed (four dashboard, three mascot persistence/assets). Production build passed. Lint passed with the pre-existing Date render-purity warning. All four VRMs loaded in the browser; saved Aoi survived reload, and previewing Miku left the applied Kobashi unchanged. Settings widths 320, 768, 1024 and 1440 px had no horizontal overflow and only one canvas. Light/dark and keyboard preview checks passed. Authenticated calls were not re-run. Vite retains its existing large lazy-renderer chunk warning.
**Interview line:** "I separated preview state from applied preferences and centralized the WebGL lifecycle, so users can explore avatars without changing their companion or keeping hidden renderers alive."


## Step 23: authenticated live dashboard and Day view (Phase 3 · 2026-10-12)
**Files:** backend/koe/events.py · backend/koe/dashboard.py · backend/koe/main.py · backend/koe/agent.py · backend/koe/voice_call.py · backend/koe/github_hooks.py · backend/koe/store.py · backend/tests/test_events.py · backend/tests/test_store.py · backend/tests/test_approvals.py · backend/tests/test_voice_call.py · backend/tests/conftest.py · frontend/src/dashboard/{state.ts,useDashboard.ts,Dashboard.tsx} · frontend/src/App.tsx · frontend/src/index.css · frontend/package.json · frontend/tests/dashboard.test.mjs · docs/SPEC.md · docs/PLAN.md · docs/ARCHITECTURE.md · docs/DECISIONS.md · docs/PHASE2_SETUP.md · docs/RESEARCH_SOURCES.md · README.md
**What it does:** Replaces all sample dashboard rows with today's Calendar, the review queue and open PRs with CI/review status. Adds real tool/approval/alert activity, pending actions and turn-latency percentiles. Connect dashboard reads data without a microphone or Gemini call. During a call, Day/Chat switches between these panels and the transcript. Missing account setup produces an explicit service message.
**Core concept:** *Publish once, fan out without waiting.* Every authenticated dashboard has a bounded queue. Tools, approvals, alerts and latency measurements publish to the hub synchronously; a slow browser gets a complete snapshot when it falls behind. This keeps dashboard delivery out of the audio critical path. A reducer reconstructs the browser state from either snapshots or incremental events.
**How it connects:** Existing Calendar/GitHub read functions → shared background refresh → authenticated /ws/events → useDashboard → panels. Shared agent execution → tool/proposal/claim/result events → activity. Call latency → event hub → p50/p95. Saved Supabase activity and pending display fields hydrate reconnects. Original-call Approve/Reject still goes through /ws/call and the atomic SQL gate; the events socket accepts refresh only.
**Try it yourself:** Run the backend/frontend normally, enter KOE_ACCESS_TOKEN from backend/.env and press Connect dashboard. Missing Google/Supabase credentials can wait: their panels show setup instructions. Once connected, ask Koe about today's events or PRs; choose Day while speaking to inspect updates. A proposal from another CLI/call has no write controls. Refresh reads automatically every minute; manual reads are coalesced for 30 seconds.
**Gotchas:** The hub requires one backend worker. Live activity without Supabase disappears on restart, and durable webhook processing is still Phase 5. A slow background refresh must not overwrite a newer conversational result; tests cover that race. Cancellation emits a failed end event and still propagates, so a panel does not remain highlighted forever. Pending-card expiry is checked locally for display and again in PostgreSQL before execution. Tokens never enter URLs, localStorage or the frontend bundle.
**Measured:** 93 backend tests passed; Python compilation passed. All seven current frontend tests passed (four new dashboard reducer/percentile tests and three mascot tests from the concurrent frontend slice). Production build passed. Lint completed with the existing App Date render-purity warning; the existing lazy mascot chunk-size warning remains. Isolated browser checks verified authentication, missing-service errors, fixture Calendar/PR rows, incoming alerts, other-conversation proposals without approval buttons, and fixture latency reduction. Shoji and Engawa at 1280 px and 375 px had no horizontal overflow; browser console had no warnings/errors in the checked session. Test servers used temporary fixture credentials and no live APIs, then were stopped and their temporary config removed. No real booking, message send or new production latency measurement was performed.
**Interview line:** "I separated the dashboard's read-only event stream from the call's authorization path, bounded each client's queue so slow UI delivery cannot hold up audio, and protected live data from stale background refreshes."

## Frontend revision: visual companion studio (2026-10-13)
**Files:** frontend/src/settings/{SettingsPage.tsx,settings.css,useExpandedPreview.ts} · frontend/src/mascot/{catalog.ts,MascotView.tsx,mascot.ts} · frontend/public/mascot/portraits/*.jpg · frontend/tests/mascot-preferences.test.mjs · docs/SPEC.md · docs/DECISIONS.md · change log.md
**What changed:** Replaced the first text-heavy, stacked Settings layout with one adaptive preview pane. Real screenshots replace mascot initials. The portrait picker sits on the left on desktop and below the model on phones. Framing, expansion, Say hi, turntable, zoom and Choose sit inside the viewer; descriptive cards and separate mood/expression button groups are removed.
**How it works:** Full body expands the same canvas, using actual mesh bounds to keep head and feet in view. Inspection allows persistent 360-degree rotation, vertical pan and 1–2.5× zoom. Arrow keys and Home support keyboard inspection. Expanded mode contains focus, locks background scrolling, closes with Escape and restores focus. Home's framing, gestures and saved-selection behavior remain intact.
**Try it yourself:** Open Settings, tap any portrait, select Full body, then drag horizontally to turn or vertically to move the model. Zoom in for details or use auto rotate. Say hi or tap the model for reactions. Choose applies the companion; browsing portraits alone does not.
**Measured:** Seven frontend tests pass; TypeScript/Vite production build passes. Lint has only the existing App Date render-purity warning. All four live models and portraits load. Checked widths 320, 375, 768, 1024 and 1440 px without horizontal overflow or overlapping controls. At 1440×1000, the expanded canvas is 1288×832; at 375×844 it is 375×592. Light/dark, zoom, drag, keyboard inspection, focus containment and Escape were checked. Expansion retains one canvas. Four JPEG portraits total approximately 96 KiB. Existing renderer chunk warning remains; no dependencies or backend changes.
**Handoff:** `change log.md` now describes both the original architecture change and this visual revision, with before/current behavior and integration notes for the paused session. Existing concurrent dashboard/backend work is preserved; no commit or deployment was made.

### Follow-up: keep the mascot vertically centered (2026-10-13)
Removed the vertical camera offset from dragging and Up/Down keyboard input after it allowed the mascot to leave the preview pane. Horizontal rotation, turntable, zoom, tap reactions and framing remain. The visible hint and canvas accessibility instructions now describe rotation only. This supersedes the vertical-pan behavior documented above; current behavior is also recorded in `change log.md` and SPEC.

Verified the original displacement before the fix, then long upward/downward drags after the fix on desktop and at 375×844. The figure stays centered; horizontal dragging still rotates it and zoom still reaches 2.5×. Production build and all seven existing tests pass; lint retains only the existing App Date warning.

## Step 24: PR evidence and shipped history (Phase 4 · 2026-10-13)
**Files:** backend/koe/tools/github_work.py · backend/tests/test_phase4_github.py · docs/SPEC.md · docs/DECISIONS.md · docs/RESEARCH_SOURCES.md
**What it does:** Adds PR summaries, authored merged PRs and default-branch commit history. Summary coverage includes head SHA, included/changed files, missing patches and truncation. Today and this week start in the configured timezone. PRs and commits are separate overlapping evidence, never an hours estimate.
**Core concept:** An AI summary is only as good as its evidence. Build bounded source JSON from GitHub, recheck the revision, then ask a tool-free model for a structured summary and inferred risks. Truncate by serialized UTF-8 bytes, accounting for Unicode and JSON escapes. This keeps input bounded without claiming omitted code was reviewed.
**How it connects:** The shared registry exposes these reads to voice and CLI. Existing Gemini configuration powers the nested summarizer; existing httpx connections power GitHub REST. Fixed-origin numbered pagination prevents following a Link URL to another host with credentials.
**Try it yourself:** After filling GitHub/Gemini settings, ask “Summarize PR 42 in owner/repo” or “What did I ship today?” Setup and limits are in PHASE4_SETUP.md.
**Gotchas:** Missing GitHub patches do not necessarily mean a binary file. Changed heads require a fresh read. Search indexing can lag and capped/incomplete history is labeled partial. Risk notes are inferences, not tests or a merge recommendation. No merge tool exists.
**Interview line:** “I bounded the evidence sent to the model, verified the source revision and exposed coverage so users can distinguish a useful summary from a complete review.”

## Step 25: append-only Notion log and approved Sheets hours (Phase 4 · 2026-10-13)
**Files:** backend/koe/tools/{notion.py,sheets.py} · backend/koe/{config.py,google_auth.py} · backend/.env.example · backend/tests/{test_phase4_logs.py,test_google_auth.py} · docs/PHASE4_SETUP.md
**What it does:** Queries one Notion daily page by Date and creates/appends plain-text bullets. Exact existing entries are skipped. Adds a configured Sheets row writer with date/client/hours/note/action ID, strict header validation and destination binding. Existing Google OAuth gains an explicit optional Sheets scope check; it never silently expands Calendar consent.
**Core concept:** Read before appending, but be honest about external transactions. One process lock prevents concurrent log requests racing the page query. Notion cannot enforce our unique daily-page rule atomically with Supabase; duplicate/partial/malformed reads fail closed and uncertain writes require inspection. Sheets RAW values store user text literally rather than interpreting formulas.
**How it connects:** Notion follows the SPEC own-log exception. Sheets enters the shared approval gate; only the stored proposal reaches the internal writer. The spreadsheet and tab are configuration, not model-selected destinations. The action ID is an audit column, not an upstream idempotency key.
**Try it yourself:** Later, connect Koe Daily Log with one title and a Date property. Enable Sheets in the same Google project, reauthorize with --with-sheets, prepare A1:E1 headers and fill GOOGLE_SHEETS_ID. Ask to log 1.25 hours with a client/date/note; inspect and approve the preview.
**Gotchas:** Every hours entry needs a new confirmation. Missing credentials remain setup errors. Writers do not automatically retry uncertain POST/PATCH requests. A read timeout cannot turn into an empty daily page. Do not infer billable hours from commits.
**Interview line:** “I separated append validation from authorization, bound each approved row to its destination and used literal values so user text cannot become a spreadsheet formula.”

## Step 26: shared Phase 4 approval and channel wiring (2026-10-13)
**Files:** backend/koe/{agent.py,text_agent.py,events.py,voice_call.py} · backend/scripts/chat.py · backend/tests/{test_approvals.py,test_agent.py,test_text_agent.py,test_events.py} · frontend/src/call/useCall.ts · frontend/src/dashboard/state.ts · frontend/src/index.css · README.md · docs/{PLAN.md,ARCHITECTURE.md,TECH_STACK.md}
**What it does:** Registers all ten planned tools. Calendar, PR comments and each Sheets entry share proposal → preview → explicit response → atomic claim → execute. The full comment/note and target are shown. Success/cancel wording now covers all writers; only a Calendar write dirties the Calendar panel. Multiline approvals preserve whitespace in Chat and Day.
**Core concept:** Model intent is not authorization. A tool can prepare a proposal, but only the application can bind the user's next explicit response to the saved action and claim it once. A second identical hours request is a new action and needs a new yes.
**How it connects:** The same registry/declarations feed CLI and Live voice. Existing dashboard events show proposals and authoritative results. Other-conversation proposals stay read-only. The prompt directs shipped-history reads into factual daily Notion entries with source links and partial-result labels; no hours are inferred.
**Try it yourself:** Use the Phase 4 setup guide when ready. “Comment on owner/repo PR 42…” and “Log 1.25 hours…” should show full proposals, then wait for yes/no or buttons. Reject one and verify no service write occurs.
**Gotchas:** Real service verification is deferred until credentials arrive. The implementation task sent no real comment, calendar invite or hours entry. No dependencies were added and no additional database migration is needed. Existing concurrent mascot/settings changes were preserved.
**Browser evidence:** An isolated React fixture rendered the actual Dashboard and approval styles. Full multiline note/comment text retained pre-wrap; only the current call had Approve/Reject. A fake approval changed fixture status only. Desktop and 375 px had no horizontal overflow; checked console had zero errors/warnings. The temporary fixture files were removed and test server stopped. Production build passed and seven frontend tests passed; existing App Date purity and mascot chunk-size warnings remain.
**Interview line:** “I extended one authorization path across three services while keeping full previews and per-action confirmation consistent in voice, CLI and dashboard.”

**Final Phase 4 verification:** 126 backend tests passed in 23.77 seconds, including the added malformed-read, concurrent daily-log and uncertain-append cases. Python compilation and scoped diff whitespace checks passed. The suite retains the upstream Starlette/httpx TestClient deprecation warning; no dependency was changed to address it. Seven frontend tests and production build passed; lint exits successfully with the existing App Date warning. Live account acceptance remains unchecked in PLAN.md. New environment placeholders were appended only if absent; existing values were preserved and no secrets were printed. No commit or deployment was made in the shared dirty working tree.

## Step 27: a desk for the mascot, and poses from VRoid Studio  (Phase 3 · 2026-10-13)
**Files:** frontend/src/mascot/mascot.ts (desk framing, chin/stretch poses, pose blending) · frontend/src/mascot/vroidpose.ts (new) · frontend/src/mascot/poses/README.md (new) · frontend/tests/vroidpose.test.mjs (new) · frontend/src/App.tsx + index.css (desk card) · frontend/public/mascot/kami.vrm (updated model)
**What it does:** On Home she now stands behind a desk card instead of being cut off by the bottom of the screen: the camera frames her from her hair to her waist, and the waist lands exactly on the desk's top edge. The desk shows her name, status and a Say hi button, and slides away when a call shows her full figure. She has two new moves (hand on chin while Koe runs a tool, and a stretch), and any pose saved from VRoid Studio as a `.vroidpose` file and dropped into `src/mascot/poses/` becomes one of her idle poses.
**Core concept:** *Coordinate systems.* VRoid Studio is built on Unity, which uses a left-handed coordinate system; three.js is right-handed. A rotation stored as a quaternion (x, y, z, w) is mirrored across one axis when you change handedness, which here means negating y and z: (x, −y, −z, w). After that, a VRoid bone name like `LeftUpperArm` maps to the VRM bone `leftUpperArm`, except the thumbs, which VRM 1.0 renamed. A pose is *absolute* (where each bone should be) while the built-in gestures are *offsets*, so the blender computes (pose − rest) × strength per bone and eases it in and out.
**How it connects:** `import.meta.glob('./poses/*.vroidpose', { query: '?raw', eager: true })` bundles every pose file at build time → `parseVroidPose` → a 5 s gesture in the idle pool. The desk height (24%) is `DESK` in mascot.ts and `--desk-h` in CSS; the camera uses it to put her waist on the desk edge.
**Try it yourself:** VRoid Studio → Photo Booth → Poses & Animations → Posing → pick a pose → Save current pose → put the file in `frontend/src/mascot/poses/` → reload Home and wait for her idle routine (6 to 12 s). `npm test` runs the parser tests.
**Gotchas:** Poses only rotate bones; sitting or crouching poses need the hips lowered and won't look right while she stands. The head is left to the app so she keeps eye contact. VRoid's preset poses: check VRoid Studio's terms before shipping them publicly; poses you make yourself are yours.
**Measured:** 10 frontend tests pass (3 new for the parser: handedness conversion, thumb renaming, bad input). Desk at 1280×800: 512×192 px, centred under her; her hanging hands fall within its width at that scale.
**Interview line:** "VRoid exports poses as Unity quaternions; converting handedness is just negating two components, which let me reuse any pose made in VRoid Studio on the web mascot without a new library."

## Step 28: a calmer Settings page  (Phase 3 · 2026-10-13)
**Files:** frontend/src/settings/SettingsPage.tsx (rewritten) · frontend/src/settings/settings.css (rewritten) · frontend/src/settings/useExpandedPreview.ts (deleted)
**What it does:** Settings now looks like Home: a short list of companions on the left (round portrait, name, "Current" on yours) with one button, and the model standing in a flat viewer on the right. One small toolbar (Portrait / Full body, Say hi, Rotate) replaces about ten controls spread over four corners. Zoom moved to the scroll wheel; drag to turn and arrow-key rotation stay. The separate expanded mode is gone, because the viewer is already large.
**Core concept:** *Subtract until it breaks.* Each control was asked "is this needed every visit?"; the answers decided what stayed visible, what moved into a gesture (zoom → scroll), and what went (expand, a 10 px hint row). React's own wheel listener is passive, so it can't stop the page from scrolling; a native listener with `{ passive: false }` can.
**Try it yourself:** open Settings, pick a companion, scroll over her to zoom, drag to turn her, then press "Use …".
**Measured:** 10 frontend tests and the production build pass. At 1280 px and 375 px: no sideways scroll; the toolbar stays on one 40 px row on a phone.
**Interview line:** "I cut the settings viewer from ten scattered controls to one toolbar by moving zoom into a gesture and removing a mode the layout no longer needed."

## Step 29: calmer skirts  (Phase 3 · 2026-10-13)
**Files:** frontend/src/mascot/mascot.ts
**What it does:** Kobashi's skirt (and every VRoid skirt) no longer floats up and flares when she turns, hops or shifts her weight; it sways a little and stays down.
**Core concept:** *Spring bones.* Hair and clothes in a VRM hang on chains of "spring bones", tiny physics simulations. Each joint has a stiffness (how hard it springs back to its rest shape), a drag (damping: how fast motion dies out) and a gravity. Kobashi's export had drag 0.05 and no gravity, so the skirt kept swinging like it was underwater. At load time, every joint whose bone name contains "Skirt" gets 2.5× stiffness, drag ≥ 0.5 and gravity ≥ 0.4 (the `SKIRT` tuning knobs).
**Try it yourself:** Settings → Kobashi → Full body → drag her round fast. Raise `SKIRT.drag` for even less movement.
**Measured:** a fast 300 px drag spun her almost all the way round; mid-spin, the skirt stays in a closed bell shape. 10 frontend tests pass.
**Interview line:** "Clothing on the avatar is spring-bone physics; damping the skirt chains at load time fixed it for every model without re-exporting anything."

## Step 30: one layout, real icons, and a dashboard that fits on a screen  (Phase 3 · 2026-10-13)
**Files:** frontend/src/App.tsx · frontend/src/index.css (rewritten) · frontend/src/dashboard/Dashboard.tsx (rewritten) · frontend/src/settings/{SettingsPage.tsx,settings.css} · frontend/package.json (+ `@phosphor-icons/react`) · docs/{TECH_STACK,SPEC,DECISIONS}.md
**What it does:** Only the Engawa layout remains (she stands left, your day on the right). The header is a small pill of icon buttons: Home, Settings, theme (sun/moon). Call, Mute, End call, Send, Say hi and the Settings toolbar get icons too. The home dashboard is no longer six stacked sections: it's one card with four tabs (Today, GitHub, Approvals with a count, Activity with response time), a fixed height that scrolls inside, and a Live/Offline dot with a refresh icon. The access-token field became one Connect row that disappears once the dashboard is live.
**Core concept:** *Progressive disclosure.* Show one thing at a time and let the user ask for more: tabs keep every piece of information one tap away without stacking it all on the page. The tabs follow the WAI-ARIA tabs pattern: `role="tablist"`/`tab`/`tabpanel`, only the selected tab is in the Tab order, and the arrow keys move between tabs. On phones the tab labels hide to save space, so each tab carries an `aria-label`. Icons come from one family in one weight (Phosphor, light) through a single `IconContext`, so they all look like they belong together.
**How it connects:** `Dashboard` still reads the same `useDashboard` state and is reused in the call panel's Day view. `IconContext.Provider` in App sets size 18 and light weight for every icon.
**Try it yourself:** open Home: everything fits one screen on a laptop. Click the tabs or use the arrow keys. Toggle the theme with the sun/moon.
**Measured:** at 1280×800 the page is 797 px tall (fits); at 1440×900, 897 px. No sideways scroll at 375, 1280 or 1440 px. 10 frontend tests and the build pass; no console errors.
**Interview line:** "I replaced a long stack of dashboard sections with an accessible tabbed card of fixed height, so the home screen fits a laptop window without hiding anything."

## Step 31: talk to Koe on WhatsApp  (Phase 5 · 2026-10-13)
**Files:** backend/koe/whatsapp.py · backend/koe/text_agent.py (busy errors) · backend/tests/test_whatsapp_turns.py (new) · backend/tests/test_whatsapp.py · backend/tests/test_text_agent.py · docs/{PLAN,SPEC,DECISIONS}.md
**What it does:** A WhatsApp text or voice note from your number now goes through the same agent as the CLI (GitHub, Calendar, Notion, Sheets, approval gate) and Koe replies. Voice notes are downloaded from Meta and transcribed by Gemini first. When Koe proposes a write (a meeting, a PR comment, an hours entry), the reply carries **Confirm** and **Cancel** buttons; tapping one resolves exactly that action, the same way saying "yes" does. Each turn logs how long every stage took.
**Core concept:** *Acknowledge fast, work in the background.* Meta wants a 200 within a second, but a model turn takes seconds, so the webhook answers immediately and hands the message to a background task. A per-sender `asyncio.Lock` makes messages from one person run one after another (a quick second message can't race the first one's approval). *Tokens only go where they belong:* the voice-note download URL comes from Meta's API, but the code still checks it is on a Meta host before attaching the access token, the same rule as the GitHub tools' fixed-origin pagination.
**How it connects:** `POST /webhooks/whatsapp` → `handle_message` (background) → text, or `download_media` → `transcribe` → `text_agent.chat` (tools, approval gate) → `send_text` or `send_buttons`; a button's id `approve:<action id>` → `agent.confirm`.
**Try it yourself:** `uv run pytest -q tests/test_whatsapp_turns.py`. For real use: Meta must finish business verification (SERVICES_AND_COSTS.md), then point the webhook at `/webhooks/whatsapp` through cloudflared and message your business number.
**Gotchas:** Real sends are still blocked by Meta (business verification). Free-tier Gemini sometimes answers 503 "high demand": the reply now says "Gemini is busy right now" instead of a vague failure, and the cause is logged. A restart forgets WhatsApp chat history and any open buttons (Phase 6 adds persisted memory).
**Measured (real Gemini, Meta faked):** voice note transcription of a 3.4 s OGG/Opus note: 6.5 s and 4.9 s, word for word ("Am I free at 7 tomorrow evening? Book a call with Rahul."); a third attempt hit a 503. Text turns: 8.0, 5.0 and 3.8 s, then 2.5 s once the HTTP client was reused (a new client per message cost ~0.6 s of TLS setup; first message after start ~1.7 s once). The SPEC's 3–4 s voice-note target is not met yet; the one-call audio path is the next lever. 137 backend tests pass (11 new).
**Interview line:** "WhatsApp messages are acknowledged instantly and processed in a per-sender queue through the same agent and approval gate as voice, with reply buttons bound to the exact pending action."

## Step 32: the Koe app: install Koe on your phone, chat by voice, get notifications  (Phase 5b · 2026-10-13)
**Files:** backend/koe/app_channel.py (new) · backend/koe/{main,config,github_hooks}.py · backend/tests/{test_app_channel.py (new),conftest.py} · frontend/public/{manifest.webmanifest,sw.js,icons/*} (new) · frontend/src/chat/{ChatPage.tsx,chat.css,api.ts,recorder.ts} (new) · frontend/src/pwa.ts (new) · frontend/src/{App.tsx,main.tsx,settings/SettingsPage.tsx} · frontend/{index.html,vite.config.ts} · .gitignore (backend/data/) · docs/{SPEC,PLAN,DECISIONS,TECH_STACK}.md
**What it does:** Koe is now an app you can put on your phone without any store: Settings → This device → **Install app** (on iPhone: Share → Add to Home Screen). It opens on a WhatsApp-style **Chat** with Kami as the avatar. Type, or tap the mic and send a voice note; Koe answers a voice note with a voice note in its call voice, plus the text. Proposals come with **Confirm / Cancel**. Turn on **Notifications** and Koe's replies and GitHub alerts arrive on your phone like WhatsApp messages, even with the app closed. History is kept.
**Core concept:** *Progressive Web App + Web Push.* A web app becomes installable when it has a manifest (name, icons, start page, "standalone" display) and is served over HTTPS. A **service worker** is a small script the browser keeps registered even when the app is closed; it receives **push messages** and shows notifications. Push works through the browser vendor's free push service: the server signs each message with its own **VAPID** key pair (generated once into `backend/data/vapid.pem`) and encrypts it for that one device. Voice notes are recorded with the same AudioWorklet as calls and wrapped in a 44-byte **WAV header**, a format Gemini accepts, so nothing has to be transcoded.
**How it connects:** Chat → `/api/app/*` (Bearer `KOE_ACCESS_TOKEN`, fail closed) → text, or WAV → `whatsapp.transcribe` → the shared `text_agent` (tools + approval gate) → SQLite (`backend/data/app.db`) → reply (+ `speak`: Gemini Live reads it into a WAV) → `notify` → Web Push → `sw.js` → phone notification. GitHub alerts: `github_hooks.send_alert` → `app_channel.alert` → chat + push (WhatsApp still tried if configured).
**Try it yourself:** backend + `npm run dev`, then `cloudflared tunnel --url http://localhost:5173` and open the https URL on your phone in Chrome → Settings → enter the access token → Install app → Turn on notifications → Chat. Tests: `uv run pytest -q tests/test_app_channel.py`.
**Gotchas:** The built-in preview browser refuses service workers ("unknown error when fetching the script") even though `/sw.js` serves fine, so install and push can only be checked on a real phone or Chrome. Chrome needs HTTPS (the tunnel) except on localhost. iPhone shows notifications only after the app is added to the Home Screen (iOS 16.4+). The spoken reply is Gemini Live reading the text, so it may differ by a word or two. A server restart keeps the history but forgets open approvals.
**Measured:** Real models through the real endpoint (token and data folder temporary): a 3.4 s voice note was transcribed word for word; Koe answered correctly that the calendar isn't connected and asked for Rahul's email, with a spoken reply. Round trip 28–31 s while Gemini's free tier was answering 503 "high demand" (one turn got the polite busy reply). Spoken reply alone: 6.7 s for 3.5 s of audio. 147 backend tests (10 new), 10 frontend tests and the build pass. **Next latency lever:** return the text reply first and attach the voice note when it's ready.
**Interview line:** "Instead of a store app, I made the web app installable and push-capable: one codebase, a service worker for notifications, VAPID-signed Web Push from Python, and voice notes as WAV straight from the AudioWorklet."


## Step 33: Neon migration and the final sign-in plan (2026-10-13)
**Files:** backend/koe/{store,config,agent,dashboard,events}.py · backend/migrations/001_phase2.sql · backend/scripts/{migrate_store,verify_neon_store,verify_store_sql,check_setup}.py · backend/tests/{test_store,test_voice_call,conftest}.py · backend/{pyproject.toml,uv.lock,.env.example} · .gitignore · README.md · docs/{AUTH_FLOW,SPEC,ARCHITECTURE,TECH_STACK,SERVICES_AND_COSTS,PLAN,PROBLEM_STATEMENT,PHASE2_SETUP,PHASE4_SETUP,DECISIONS,RESEARCH_SOURCES}.md
**What it does:** Replaces the unavailable Supabase project with Neon PostgreSQL in Singapore, using the provided backend-only DATABASE_URL. Preserves the existing proposal/claim/finish interface, ten-minute expiry, owner/conversation isolation and audit transactions. The additive, rerunnable schema needs no Supabase roles. PUBLIC grants are revoked; RLS is enabled and the backend connection role owns the objects. The activity constraint is expanded to include the installed-app channel so chat approvals can now save successfully. Setup and error messages refer to Neon. Credentials are excluded from Settings representations and database error messages.
**Core concept:** The database and app sign-in are separate boundaries. Neon stores data, while FastAPI decides who can access it. The current KOE_ACCESS_TOKEN is a development app password. The recommended final flow is owner-only provider sign-in followed by a secure, expiring, revocable server session; the browser automatically authenticates chat/calls/dashboard with its HttpOnly cookie. Signing in does not grant Calendar/GitHub tool permissions or authorize writes. AUTH_FLOW.md explains onboarding, connection consent, allowlisting, logout and the required pre-hosting implementation; OAuth login is planned, not implemented in this migration.
**How it connects:** browser token check → existing FastAPI/agent → psycopg worker thread → parameterized PostgreSQL call → atomic function/audit transaction → existing frontend events. Connections commit/rollback/close through context managers. Worker threads keep blocking libpq I/O off Windows' default audio event loop. Neon pooled connections reject statement_timeout startup options, so the timeout is set locally inside each transaction. Ambiguous writes are never automatically retried.
**Try it yourself:** Open the running frontend (http://127.0.0.1:5174/) and use the existing token. Backend health is http://127.0.0.1:8000/health. From backend/, run `uv run python -m scripts.check_setup`; apply schema with `uv run python -m scripts.migrate_store`. `uv run python -m scripts.verify_neon_store` uses a fresh synthetic owner, checks real database behavior, then removes only those test rows. It does not execute any external tool. `uv run python -m scripts.verify_store_sql` uses a disposable local PostgreSQL cluster, never the live database.
**Measured:** 152 backend tests pass. Disposable PostgreSQL verifies schema reapplication, audit, one winner from four concurrent claims, owner/session isolation, expiry, rejection and denied untrusted-role access. The installed-app channel regression was reproduced before expanding the constraint. Live Neon verifies the real adapter, JSON arguments/results, idempotent proposals, concurrent claims, replay prevention, owner/session isolation, rejection, expiry and dashboard display-field filtering; synthetic records are removed. Running frontend/backend return HTTP 200. Through Vite's proxy, missing/wrong tokens get HTTP 401, the saved token gets HTTP 200; dashboard WebSocket accepts the saved token and rejects a wrong token with 1008; the voice socket rejects a wrong token before starting Gemini.
**Gotchas:** Manual token entry remains until the sign-in slice is implemented. Google Calendar is still unconnected (scripts.check_setup reports the missing Google consent); no real booking was made. Existing app chat SQLite, push subscriptions, VAPID keys and WAV files remain on local persistent disk. Voice latency has not been remeasured after migration. Use one backend worker. The schema role is private backend ownership, not public multi-user row policies. Historical Supabase build entries above describe the superseded design.
**Interview line:** "I migrated a personal agent from Supabase REST to managed PostgreSQL without weakening its approval gate, proved one-winner claims against the hosted database, and separated database credentials from the planned browser session login."


## Step 34: verify account configuration and normalize the Notion database ID (2026-10-13)
**Files:** backend/.env (private, ignored; NOTION_DATABASE_ID only) · docs/BUILD_LOG.md.
**What it does:** Checks the existing Google/Notion setup without printing credentials. The Notion environment value contained a full database URL; extract its UUID, verify that the existing token can retrieve that database, and save only the normalized UUID while preserving every other .env value. No Notion content/schema was changed.
**Core concept:** A resource ID identifies the database or spreadsheet; an OAuth token or integration token authorizes access. A correct URL/ID alone does not grant access. Calendar and Sheets share one Google Desktop OAuth client and local consent token in the current development setup.
**Measured:** Notion users/me, database metadata and its sole data source all returned HTTP 200. The data source has one title property but lacks a property named Date with type date, which Koe requires. NOTION_DATA_SOURCE_ID is optional because there is exactly one source. GOOGLE_CALENDAR_ID is primary; GOOGLE_SHEETS_ID, credentials.json and token.json are absent. No external writes were made and no secrets printed. The running backend must be restarted after remaining setup is completed to load changed environment values.
**Try it yourself:** Add the Date property in Notion; enable Calendar and Sheets APIs, create a Desktop OAuth client, save backend/credentials.json, then run scripts.google_auth --with-sheets from backend/. Create the Hours spreadsheet with the five required headers, put its spreadsheet ID in GOOGLE_SHEETS_ID, and restart the backend. See PHASE2_SETUP.md and PHASE4_SETUP.md.
**Interview line:** "I distinguish resource identifiers from authorization credentials and verify actual access and required schema instead of assuming that a populated environment setting means an integration is ready."

## Step 33: ready for Vercel, and what the WhatsApp webhook really needs  (Phase 5 · 2026-10-13)
**Files:** frontend/src/backend.ts (new) · frontend/src/{chat/api.ts,call/useCall.ts,dashboard/useDashboard.ts} · frontend/vercel.json (new) · frontend/.env.example (new) · backend/koe/{main,config}.py (CORS) · backend/.env.example · backend/tests/test_health.py
**What it does:** The frontend can now run on Vercel while the backend runs elsewhere: every API and WebSocket address goes through `backend.ts`, which uses `VITE_BACKEND_URL` when set and the same origin otherwise (local dev unchanged). The backend accepts calls from the configured frontend origin only (`FRONTEND_ORIGINS`).
**Core concept:** *Two servers, two jobs.* Vercel serves the static React build over HTTPS; the FastAPI backend does the work (Gemini, tools, WebSockets, webhooks). Meta's WhatsApp **callback URL must point at the backend** (`https://<backend>/webhooks/whatsapp`), never at the frontend. **CORS** (Cross-Origin Resource Sharing) is the browser rule that lets a page on one origin (`koe.vercel.app`) call an API on another only if that API says so in its response headers.
**Gotchas:** The WhatsApp token in `.env` belonged to a Meta app that has since been deleted (Graph error 190, "Application has been deleted"), and `WHATSAPP_APP_SECRET` was missing, so every webhook would be rejected as unsigned. A new app needs a new permanent token, its own Phone Number ID and its App secret. A local `vite build` takes ~2 min on Windows because of the 66 MB of mascot models; Vercel's builders don't have that problem.
**Measured:** 153 backend tests (1 new: CORS allows only the configured origin) and 10 frontend tests pass; production build passes.
**Interview line:** "The static frontend and the stateful backend are deployed separately, joined by an explicit backend URL and an origin allow-list, because Vercel can't proxy the WebSockets the voice call needs."

## Step 35: the backend gets a permanent address on Render  (Phase 7 prep · 2026-10-13)
**Files:** render.yaml (new) · docs/DEPLOY.md (new) · backend/scripts/vapid_key.py (new) · backend/koe/{config,app_channel,google_auth}.py · backend/.env.example · backend/tests/test_app_channel.py · frontend/src/{pwa.ts,chat/ChatPage.tsx,backend.ts}
**What it does:** `render.yaml` describes the backend as one free Render web service. It builds `backend/` with uv, starts uvicorn on Render's `$PORT`, checks `/health`, and redeploys on every push. Secrets are marked `sync: false`, so Render asks for them in its dashboard and they never touch Git. Three small changes make Koe survive Render's wiped disk:
- the push key comes from `VAPID_PRIVATE_KEY`;
- the phone re-sends its push subscription each time the app opens;
- a Google token refresh no longer fails when the token file is read-only.
**Core concept:** *Infrastructure as code + stateless servers.* A Blueprint is the server's setup written down in the repo, so it can be recreated in one click. Free hosts treat the disk as disposable ("ephemeral"), so anything that must last lives either in config (env vars, secret files) or in a real database (Neon). Whatever is only on disk gets rebuilt or re-sent.
**How it connects:** push to main → Render builds `backend/` → `https://<backend>.onrender.com` → Vercel's `VITE_BACKEND_URL` points the app at it; `FRONTEND_ORIGINS` lets the app in (CORS); Meta and GitHub webhooks call `/webhooks/whatsapp` and `/webhooks/github` on it.
**Try it yourself:** follow docs/DEPLOY.md. Then `curl https://<backend>.onrender.com/health` should print `{"ok":true}`. Locally: `uv run python -m scripts.vapid_key` prints a fresh key.
**Gotchas:** Render free sleeps after 15 min idle, and the first request takes up to about a minute; GitHub webhooks sent during that minute can be lost. The app's chat history and voice notes reset whenever Render restarts, until they move to Neon (PLAN Phase 7). A push subscription made against the laptop's key must be turned off and on once against Render's key.
**Measured:** 154 backend tests (1 new: push key from the environment) and 10 frontend tests pass; `uv lock --check` passes. Nothing is deployed yet, so there are no Render latency numbers.
**Interview line:** "I made the backend disposable: config and keys come from the host's environment, durable data lives in Postgres, and the client re-registers what the server may have forgotten, so a free host that wipes its disk still works."

## Step 36: WhatsApp wiring on Render: three silent breaks  (Phase 5 · 2026-10-13)
**Files:** backend/koe/whatsapp.py (`log_failed_deliveries`) · backend/koe/main.py (INFO logging) · backend/tests/test_whatsapp.py · Meta account config (no code)
**What it does:** Meta webhooks now reach Koe on Render. Failed deliveries of Koe's replies are logged with Meta's own error code, and Koe's INFO lines (latency stages) show in Render's logs.
**Core concept:** *Every hop can fail silently.* A WhatsApp round trip has four independent switches, and each one failed without an error:
1. The webhook URL is verified (Meta → App → WhatsApp → Configuration).
2. The WhatsApp Business Account (WABA) is **subscribed to this app**: `POST /{waba-id}/subscribed_apps`. Ours was only subscribed to Meta's internal "WA DevX" app.
3. The app secret is set under the exact name Koe reads. `.env` had `WHATS_APP_SECRET`, Koe reads `WHATSAPP_APP_SECRET`, and Render had none, so signed events got 401.
4. The send API's "accepted" isn't "delivered". The real result arrives later as a `statuses[].status = "failed"` webhook, which Koe used to drop unread.
**Try it yourself:** Message the test number. In the Render logs, look for `POST /webhooks/whatsapp 200`, then Koe's `koe.whatsapp` lines. A `WhatsApp delivery failed: <code> <title>` line names Meta's reason.
**Gotchas:** Meta's health check (`GET /{phone-id}?fields=health_status`) showed:
- the WABA **BLOCKED** for business-initiated messages (141006, a payment-method error);
- the business **LIMITED** (141010, not verified).

Replies within 24 h of your own message are a different category. A correct app secret can be proven without revealing it: Graph accepts an `appsecret_proof` (an HMAC of the token) only when it was made with the right secret.
**Measured:** 155 backend tests pass. A local send was accepted by Meta. A correctly signed empty event got 401 on Render before the secret was set and 200 after. Meta's POSTs arrived about 10 s apart: your message, then the receipt for the reply. **Live result (12:03):**
- Koe's side works end to end: `model_done` 8098 ms and `reply_sent` 8927 ms after the webhook.
- Meta then rejected delivery: `131031 Business Account locked`. Koe can't fix that; only Meta can unlock the account.
**Interview line:** "I traced a 'no reply' bug across four silent hops: webhook verification, the account-to-app subscription, the signing secret's name, and asynchronous delivery receipts. Then I made the last hop log Meta's own error code."

## Step 37: scan a QR code, get Koe on your phone  (Phase 5b · 2026-10-13)
**Files:** frontend/src/install/{InstallPage.tsx,install.css} (new) · frontend/public/install-qr.svg (new) · frontend/src/{App.tsx,chat/api.ts,settings/SettingsPage.tsx} · backend/koe/app_channel.py (`POST /api/app/push/test`, `notify` returns a count) · backend/tests/test_app_channel.py
**What it does:** `koe-pi.vercel.app/#install` is a setup portal. On the laptop it shows a QR code; scan it with the phone camera. On the phone the same page has four steps, each turning into a ✓ only after a real check:
1. install the app;
2. connect: the token is tried against the Render backend;
3. notifications: turn them on, then **Send a test**, a real push from the backend;
4. open the chat and send a voice note.
**Core concept:** *A setup flow that verifies itself.* Each ✓ comes from the real system rather than from a button press:
- `api.messages(0)` proves the token and that the backend is reachable;
- `/push/test` proves the whole push path: backend → Google's push service → the service worker → a notification on screen.

A QR code is just a URL drawn as squares. Since the URL is fixed, the image is generated once and served as a static file, so no library is needed.
**How it connects:** QR → `#install` → `useInstall()` (beforeinstallprompt) → `saveToken` + `GET /api/app/messages` → `enablePush()` → `POST /api/app/push/subscribe` → `POST /api/app/push/test` → `notify()` → `sw.js` shows it → `#chat`.
**Try it yourself:** Open `https://koe-pi.vercel.app/#install` on the laptop and scan the QR with the phone. Then on the phone: Install → paste the token → Connect → Turn on → Send a test → Open chat.
**Gotchas:**
- Render's free plan sleeps, so the first Connect can take up to a minute.
- If the site's domain changes, the QR must be regenerated; the command is in the comment at the top of `InstallPage.tsx`.
- On iPhone, notifications only work after Add to Home Screen.
- The built-in browser pane blocks notifications, so step 3 says "Blocked" there.
**Measured:** 156 backend tests and 10 frontend tests pass; types check. The laptop layout at 1280 px puts the QR on the left (280 px) and the steps on the right, with no horizontal overflow. The phone layout at 600 px is a single column with the QR hidden.
**Interview line:** "I made phone onboarding self-verifying: each step is checked against the real backend and push service, so a green tick means the whole path works, not just that a button was pressed."

## Step 38: no echo on voice notes, no glitch when a call starts  (Phase 5b · 2026-10-13)
**Files:** frontend/src/chat/ChatPage.tsx (`VoiceNote`) · frontend/src/call/player.ts (`LEAD_SECONDS`) · frontend/public/manifest.webmanifest (`start_url: "/"`) · frontend/index.html (favicon) · docs/SPEC.md
**What it does:**
- A voice note plays once, even if you tap again while it downloads. Starting one note pauses any other.
- Koe's voice in a call starts 150 ms later, but cleanly.
- The installed app opens on Home.
- The site's favicon is Kami's portrait until the Koe logo arrives.
**Core concept:**
- *Measure before fixing.* The recorded WAV from the hosted app was analysed: no repeated 40 ms chunks and no echo peak (autocorrelation 0.14, which is normal for speech). So the echo wasn't in the audio. It was **two copies playing at once**. The play button was async: the first tap was still downloading from Render, so a second tap created a second `Audio`.
- *Jitter buffer.* Streamed audio arrives in bursts. If the first chunk is scheduled to start "now", the next one can arrive late, and the gap is heard as a glitch. This was worse at call start, while the mascot loads. Scheduling the first chunk of each turn 150 ms ahead gives later chunks time to arrive. Once audio is flowing, nothing changes.
**How it connects:** Each `/ws/call` audio chunk goes to `player.play()`. If the queue had run dry, it starts at `currentTime + 0.15 s`; otherwise it starts right after the previous chunk.
**Try it yourself:** Tap a voice note twice quickly: it shows "Loading…", then plays once. Start a call and listen to the first words. Install the app: it opens on Home.
**Gotchas:** The 150 ms applies only after silence, so barge-in and steady speech are unaffected. A note that fails to download goes back to the play icon, so you can retry.
**Measured:** Hosted voice note #5: 208 chunks, 0 identical in a row, 0 silent, autocorrelation 0.14 at 44 ms (no echo). 10 frontend tests pass; types check. The call fix still needs your ears: listen to the first second of a call.
**Interview line:** "I measured the 'echo' before touching code. The recording was clean, so the bug was concurrency: a second tap during an async download started a second player. Separately, I added a small jitter buffer so streamed speech doesn't stutter at the start of a turn."

## Step 39: a plan for friends, and the public Guide, Privacy and Terms  (Phase 5c, task 1 · 2026-10-13)
**Files:** docs/ACCOUNTS_SPEC.md (new) · docs/{PLAN,DECISIONS,SPEC,AUTH_FLOW}.md · frontend/src/pages/{Layout,Guide,Privacy,Terms}.tsx + pages.css (new) · frontend/src/main.tsx · frontend/vercel.json · frontend/src/install/{InstallPage.tsx,install.css}
**What it does:**
- Writes the spec for turning Koe into an invite-only app that friends can use: Google sign-in, per-user data and connections, a Gemini quota.
- Ships its first slice: `/guide`, `/privacy` and `/terms`, readable without signing in.
**Core concept:**
- *Capability map.* One big request ("make it usable by others") becomes modules with a one-way dependency order: pages → identity → user-data → connections → quota → admin. Each module ships and is verified alone.
- *Real URLs for legal pages.* Google, Meta and Notion ask for a privacy-policy URL before they approve an OAuth app. So these pages use paths, not `#hash` routes. Vercel serves `index.html` for those paths, and `main.tsx` picks the page from `location.pathname`.
- *A privacy policy is a technical document.* It lists exactly what the code stores and who processes it, including that Gemini's free tier may use content to improve Google's products. It has to change whenever the code does.
**How it connects:** `main.tsx` → `/guide | /privacy | /terms` render `Layout` + content; anything else renders `App` (hash routes inside). The footer links all three; the Install page links the Guide.
**Try it yourself:** Open https://koe-pi.vercel.app/guide, then /privacy and /terms, signed out, on the phone and the laptop.
**Gotchas:**
- `CONTACT_URL` points at the GitHub issues page until Koe has its own domain and email.
- The Guide marks unbuilt features as "Coming soon"; update it in the same commit as each feature.
- An app route added later must not reuse these three paths.
**Measured:** No horizontal overflow at 320 px or 1280 px (the reading column is 760 px). Footer links work. Light and dark themes both render, with no console errors. 10 frontend tests pass; types check.
**Interview line:** "Before adding multi-user auth, I wrote a capability map with a dependency order and shipped the decision-free slice first: the public policy pages that the OAuth providers require."

## Step 40: the app chat survives restarts and knows whose it is  (Phase 5c, task 5 · 2026-10-13)
**Files:** backend/migrations/002_app_chat.sql (new) · backend/koe/app_channel.py (storage section) · backend/koe/store.py (`TABLES`) · backend/scripts/migrate_store.py (applies every migration in order) · backend/tests/{conftest.py,test_app_channel.py} · docs/{SPEC,DECISIONS,PLAN}.md
**What it does:**
- Chat messages, voice-note audio and push subscriptions now live in Neon, so a Render restart no longer erases them.
- Every row records its owner. Today that's the one configured owner; after sign-in it will be the signed-in person.
- Without `DATABASE_URL`, the same code falls back to a local SQLite file, so tests and offline development still work.
**Core concept:**
- *Stateless servers.* Render's free disk is temporary, so anything that must last goes to a real database.
- *Multi-tenancy by column.* Each table has `owner_id`, and every query filters on it, including the voice-note download. Guessing another person's file name returns 404.
- *Connection reuse.* A database connection costs a TLS handshake plus authentication, which takes about 1 s to Singapore. One open connection makes each query take about 120 ms instead. If Neon drops an idle connection, Koe reconnects; only reads are retried, because a write whose commit is uncertain must never run twice.
**How it connects:** `/api/app/*` → `add_message` / `list_messages` / `save_voice` / push → `sql()` → `asyncio.to_thread` → Neon (or SQLite). `speak()` builds the WAV in memory and saves it as a row.
**Try it yourself:**
- `uv run python -m scripts.migrate_store` applies 001 and 002.
- `uv run pytest -q tests/test_app_channel.py` includes the owner-isolation test.
- On the phone: send a message, redeploy Render, and the chat is still there.
**Gotchas:**
- Render runs in the US and Neon in Singapore, so each query from Render pays about 170 ms per network round trip. Moving the Render service to Singapore (a new service, same blueprint) would cut that.
- Voice audio in Postgres is fine at this scale (about 48 KB per second of Koe's voice; Neon's free plan has about 0.5 GB). Object storage is the upgrade if it ever grows.
- Old local SQLite chats aren't copied; on Render they had already been wiped.
**Measured (laptop → Neon):** first query 951 ms (connect), then 119 ms per query, 324 ms for a 200 KB voice note, 966 ms to reconnect after a forced drop. Round trip, owner scoping and cleanup all verified with a throwaway owner. 157 backend tests pass (1 new).
**Interview line:** "I moved the chat off an ephemeral disk into Postgres with an owner column on every row, proved isolation with a test, and measured connection reuse taking queries from about 1.1 s to about 120 ms."

## Step 41: a complete Notion workspace with safe agent changes (2026-10-13)
**Files:** backend/koe/{notion_service,notion_api,text_fallback}.py (new) · tools/notion.py · agent.py · store.py · text_agent.py · frontend/src/notion/ (new) · App.tsx · chat/ · pages/{Guide,Privacy}.tsx · tests and verification scripts · PRODUCT.md · docs/NOTION_PLAN.md and setup/architecture/spec.

**What it does:** Notion has a dedicated workspace with connection diagnostics, search, record-type filtering, pagination, notes preview, task/note/meeting forms, approved edits/trash and persisted recent activity. Home, Chat, Notion and Settings share navigation. The root keeps the call hook and panel mounted while changing pages, with compact call controls off Home. Chat releases an unfinished voice-note microphone when leaving its page.

**Core concept:** A reliable assistant needs deterministic controls alongside its model. The workspace calls authenticated APIs directly, so a model quota does not block managing records. Both the UI and the model use the same durable proposal → explicit confirmation → atomic claim → external operation → outcome path. Notion pages are scoped to the configured data source; stale revisions and changed destinations are rejected. Original notes are preserved, and trash is reversible. Notion meeting records document time; Calendar owns real reservations and invitations.

**How it connects:** `#notion` → `/api/notion` → scoped Notion service for reads, or agent approval gate → Neon → Notion for mutations. Agent adds notion_read/save/archive (13 total tools). Workspace approvals use a stable owner-scoped conversation and restore after restart. Daily logs keep the own-log exception and exact-entry deduplication; type/legacy-title filters prevent tasks on the same date from being mistaken for daily logs. The filter stays within Notion's two-level compound limit. Existing untyped notes display as notes; only the matching legacy daily title is inferred as a daily log.

**Optional model fallback:** Existing httpx supports OpenRouter free text models only if a key is configured. It switches on an initial Gemini 429/503 before tools execute, never replays writes, and keeps the same approval rules. Rohit will supply a key later; it is inactive now. Voice remains Gemini Live. Privacy and setup pages disclose optional provider processing; no new runtime dependency or paid model added.

**Try it yourself:** Open `http://127.0.0.1:5174/#notion`. Choose New record → Task/Note/Meeting → Preview change → Confirm change. Select the saved row to preview it, append notes with Edit record, or prepare Move to trash. Ask Koe to list tasks or prepare a task when Gemini is available. The configured database is already prepared with the missing Koe type/status/action ID properties; existing fields retained.

**Measured:** 231 backend tests pass; 12 frontend tests, TypeScript and production build pass. Lint has three existing warnings; the existing mascot chunk warning remains. Real Notion/Neon acceptance passed for connection/schema, no record before approval, create/read/update with original notes retained, replay rejection, reversible trash, Meeting date range, Note and daily-log exact-repeat deduplication. Temporary pages were trashed and isolated verification audit/approval rows removed. A separate live owner-scoped activity SQL read passed without printing contents. Desktop 1280px and mobile 390px browser checks passed using synthetic data, no horizontal overflow or console errors; screenshots saved in the task's visualization directory.

**Gotchas:** Live Gemini selection could not be verified: it returned 503 UNAVAILABLE. `scripts.verify_notion_agent` uses synthetic responses only, blocks service reads/writes and saves no real approval. `scripts.verify_notion_workflow` verifies real APIs with temporary records. Optional OpenRouter is tested with mocked responses until a key arrives. Live call audio across navigation still needs a listening check. One backend worker is required. Notion has no atomic conditional page update, and metadata/notes use separate requests; partial or uncertain success requires inspecting Notion before another proposal. Preview shows up to 500 top-level blocks; nested/non-text content opens fully in Notion. Public per-user OAuth/connection setup remains the separate accounts plan, not completed by this owner-workspace slice.

**Interview line:** "I made the model and the workspace share a durable approval gate, proved real writes happen only after confirmation, and kept the product usable through deterministic controls when the model provider returned 503."

## Step 41: Continue with Google, on the server  (Phase 5c, task 2 · 2026-10-13)
**Files:** backend/koe/auth.py (new) · backend/koe/db.py (new: the shared Neon/SQLite runner, moved out of app_channel) · backend/migrations/003_accounts.sql (new) · backend/tests/test_auth.py (new) · backend/koe/{config,main,app_channel}.py · backend/tests/conftest.py · backend/.env.example · frontend/vite.config.ts (`/auth` proxy) · .gitignore (`client_secret_*.json`)
**What it does:** `/auth/google/start` sends you to Google's sign-in page. `/auth/google/callback` turns Google's answer into a Koe session, but only for invited emails: the owner (`KOE_ADMIN_EMAIL`) or rows in `koe_invites`. `/auth/status` says who is signed in, and `/auth/logout` ends the session. `current_user` is the dependency that per-user endpoints will use. Nothing in the app requires it yet; the frontend switch is task 3.
**Core concept:** *OpenID Connect authorization-code flow.*
1. Koe makes three random values: a **state** (stops forged callbacks), a **nonce** (stops a replayed ID token) and a **PKCE verifier**. The verifier's SHA-256 "challenge" goes to Google, and only Koe's server knows the verifier itself.
2. Google returns a one-time code. Koe swaps it, together with the verifier and the client secret, for an **ID token**: a JWT signed by Google.
3. `google-auth` checks the token's signature, expiry, issuer and audience. Koe then checks the nonce, that the email is verified, and that it's on the invite list.
4. The session is a random token in an **HttpOnly, SameSite=Lax cookie**. The database keeps only its SHA-256, so a stolen copy of the database can't be replayed as a login.
**How it connects:** browser → `/auth/google/start` → accounts.google.com → `/auth/google/callback` → `koe_users` / `koe_sessions` (Neon, or SQLite locally, via `db.sql`) → cookie → `current_user` (task 3 puts it on `/api/*` and on the WebSocket tickets).
**Try it yourself:** `uv run pytest -q tests/test_auth.py` runs 11 tests:
- the owner keeps their id;
- a friend gets a new id;
- a stranger gets no account and no session;
- an unverified email is refused;
- a forged state or a replayed nonce is refused;
- `next` never leaves Koe;
- a forged Host header can't steer Google's redirect;
- logout requires Koe's own Origin, and a replayed cookie stops working;
- an expired session is signed out.
**Gotchas:**
- The downloaded `client_secret_*.json` sat in `backend/` without being git-ignored. It is now ignored, and its values live only in `.env`.
- Google matches the redirect URI exactly, so the server only builds it for `KOE_PUBLIC_URL` or `http://localhost:5173`.
- While the Google app is in **Testing**, every friend must also be a test user in Google Cloud.
**Measured:** Two deliberate breaks were caught: removing the invite check failed a test, and removing the nonce check failed the new replay test. With a real request, Google returned its normal "Sign in … to continue" page with no `redirect_uri_mismatch` or `invalid_client`. Migration 003 is applied to Neon. 220 backend tests pass.
**Interview line:** "I implemented Google sign-in as an OIDC code flow with PKCE, state and nonce, an invite allow-list, and hashed server-side sessions in HttpOnly cookies. Every rejection path is tested, and the tests are proven to fail when a check is removed."

## Step 42: the mascot brings Calendar and Sheets into the call (2026-10-13)
**Files:** backend/koe/call_work.py (new) · voice_call.py · frontend/src/call/{workState.ts,WorkPanel.tsx,work.css} (new) · useCall.ts · App.tsx · index.css · backend/tests/test_call_work.py (new), test_approvals.py, conftest.py · frontend/tests/call-work.test.mjs (new) · SPEC/ARCHITECTURE/DECISIONS.

**What it does:** During a call, actual Calendar/Sheets tool events automatically select a work window beside the mascot. Calendar shows returned events/free windows and a proposed or confirmed slot on a timezone-aware timeline. Sheets shows the exact hours row, destination tab and confirmed row number/range. Chat and Day remain accessible; each service retains its latest result for the call. No additional Google requests, new tools or dependencies are introduced.

**Core concept:** *The UI follows evidence.* A tool start opens the service, a durable proposal shows waiting, a decision shows checking/saving, and only the application's executed outcome shows saved. Backend events use a bounded display projection, not raw stored arguments. An uncertain write shows its inspect-before-retry error; it never plays a success animation. Earlier availability is cleared after a booking, and a moved event's old occurrence is removed from the displayed snapshot.

**How it connects:** Gemini tool call → voice_call → call_work display projection → authenticated call WebSocket → useCall/workState reducer → CallPanel/WorkPanel. Approval preview/progress/result derives from the original stored normalized proposal. Existing action-ID controls and explicit spoken yes/no remain the only confirmation paths. The reducer ignores stale tool results and unrelated tools, retains both service views, and clears for a new call. Approval buttons remain outside the scrollable full-summary area, keeping them reachable on mobile.

**Try it yourself:** Reload `http://127.0.0.1:5174/`, start a call, and ask “Check my Calendar for today” or “Find a 45-minute slot tomorrow evening.” Calendar opens when the tool starts. Ask to book a specific meeting: review the dashed proposed slot and full summary, then confirm or cancel. Ask “Log 1.5 hours for Acme today, note: reviewed the booking flow.” Sheets opens with the proposed row; after confirmation Google returns its row number/range. Service buttons also let you revisit either view manually. Sheets currently supports the existing approved client-hours tool, not arbitrary spreadsheet editing.

**Measured:** 235 backend tests passed at the initial verification point; 18 frontend tests, TypeScript/build passed. Browser checks used the actual CallPanel and reducer with synthetic events: Calendar read/free/proposal/save, Sheets proposal/save/cancel, service switching, retained Calendar view, desktop 1280px and mobile 390px. No console errors or horizontal page overflow; Confirm/Cancel remained inside the mobile viewport. Screenshots are in the task visualization directory. No real meetings, invitations or Sheets rows were created. Existing lint warnings and mascot bundle-size warning remain. A concurrent database extraction exposed a temporary-directory isolation issue during the full suite; the test fixture now isolates the database module's data directory too.

**Final verification:** The combined backend suite, including the concurrently added auth tests, passed 246 tests. The final production build and lint completed; only the three existing lint warnings remain. Both local servers returned HTTP 200. The mascot stays in its thinking state while the application confirms and saves a Google change, then reacts to the actual outcome.

**Limits:** These are API-driven previews of the latest tool result, not embedded Google applications or live synchronized documents. Calendar preview caps at 100 entries with explicit truncation and labels all-day events separately; short/overlapping timed events use lanes and full hover descriptions. A live Gemini/microphone listening check still depends on provider availability. No new secrets are needed for the UI; existing Calendar/Sheets OAuth and sheet configuration are required for real operations.

**Interview line:** "I made a voice agent's work visible by projecting real tool and approval events into Calendar and Sheets windows, while keeping pending and confirmed changes visibly distinct."

## Step 42: no more access token: Continue with Google everywhere  (Phase 5c, tasks 3+4 · 2026-10-13)
**Files:** frontend/src/{session.ts,signin.tsx,signin.css} (new) · frontend/src/{main.tsx,backend.ts,App.tsx,chat/api.ts,call/useCall.ts,dashboard/useDashboard.ts,settings/SettingsPage.tsx,install/InstallPage.tsx,pages/Guide.tsx,pages/Privacy.tsx} · frontend/{vercel.json,vite.config.ts} · backend/koe/{auth.py,app_channel.py,dashboard.py,voice_call.py} · backend/tests/{test_auth.py,conftest.py}
**What it does:**
- Opening Koe shows **Continue with Google**. Once signed in, Home, Chat, calls, the dashboard, Install and Settings all work with no token to type.
- Settings shows the account and a **Sign out** button.
- `KOE_ACCESS_TOKEN` still works, for local development and scripts.
- Only the owner gets past sign-in for now. Every tool still uses the owner's GitHub, Calendar and Notion, so an invited friend sees "not ready yet" until per-person connections exist (task 6).
**Core concept:**
- *First-party cookies through a proxy.* Vercel rewrites `/api/*` and `/auth/*` to Render (with caching off), so the browser only ever talks to `koe-pi.vercel.app`. The sign-in cookie therefore belongs to that site and works on phones, where third-party cookies are blocked.
- *Tickets for WebSockets.* Vercel's proxy doesn't carry WebSockets, so calls and the dashboard connect to Render directly, where that cookie isn't sent. The page first `POST`s `/api/ws-ticket` (through the proxy, with the cookie) and gets back a random 60-second ticket that works once. It then sends that ticket as the socket's first frame.
- *A marker instead of a token.* After sign-in, the place that used to store the token holds `"session"`. Every existing code path keeps working: HTTP sends the cookie, and WebSockets swap the marker for a ticket.
**How it connects:** `main.tsx` → `SignInGate` → `GET /auth/status`.
- Signed out: the sign-in screen → `/auth/google/start` → Google → `/auth/google/callback` → cookie.
- Signed in: `App`. The dashboard and call run `wsCredential("session")` → `/api/ws-ticket` → `wss://…onrender.com/ws/*` → `auth.ws_owner(ticket)`.
- `/api/*` → `auth.http_owner` checks the cookie, or else `KOE_ACCESS_TOKEN`.
**Try it yourself:** Open https://koe-pi.vercel.app, then Continue with Google, then Call Koe. Settings → Sign out returns you to the sign-in screen.
**Gotchas:**
- Locally, Vite's proxy must send `X-Forwarded-Host` (`xfwd: true`), or the backend can't tell the page is on `localhost:5173`. `KOE_BACKEND=http://localhost:8001 npx vite` points it at another backend.
- Render needs `GOOGLE_WEB_CLIENT_ID`, `GOOGLE_WEB_CLIENT_SECRET`, `KOE_ADMIN_EMAIL` and `KOE_PUBLIC_URL`.
- The tests blank the Google client ID, just as they blank the access token, so `.env` can't leak into them.
**Measured:** 223 backend tests and 18 frontend tests pass. In the browser, using a temporary test session (deleted afterwards):
- the sign-in screen appears signed out;
- "Continue with Google" reaches Google's page with the registered `localhost:5173` callback;
- signed in, Home shows no token form and the dashboard goes Live over a ticket (`POST /api/ws-ticket` 200);
- Chat loads with no token card;
- Sign out returns to the sign-in screen, and the server reports `user: null`.
**Interview line:** "I removed the shared password by putting the API behind the frontend's own origin, so the session cookie is first-party, and by trading that session for one-time tickets on the WebSockets the proxy can't carry."

## Step 43: Settings → Connections: your own Google Calendar and Sheets  (Phase 5c, task 6 · 2026-10-13)
**Files:** backend/koe/{connections.py,identity.py} (new) · backend/migrations/004_connections.sql (new) · backend/tests/test_connections.py (new) · backend/koe/{auth.py,google_auth.py,app_channel.py,db.py,config.py,main.py} · backend/pyproject.toml + uv.lock (`cryptography` listed directly) · backend/tests/conftest.py · frontend/src/settings/{Connections.tsx (new),SettingsPage.tsx,settings.css} · frontend/src/pages/Guide.tsx · docs/DEPLOY.md
**What it does:** Settings gets a **Connections** list. **Connect** next to Google opens Google's consent screen for Calendar and Sheets together, and comes back with "Google connected". From then on the calendar and timesheet tools use that account. **Disconnect** deletes Koe's copy and revokes it at Google. The owner still falls back to the local `token.json`; anyone else never does.
**Core concept:**
- *Sign-in ≠ access.* Signing in asks Google only "who is this?" (`openid email profile`). Connecting asks for `calendar.events` + `spreadsheets` with `access_type=offline`, which makes Google send a **refresh token**. That's a long-lived key Koe can swap for a fresh 1-hour access token whenever it needs one. Both flows reuse the same registered callback; a field in the short-lived flow cookie (`purpose`) tells them apart.
- *Encryption at rest.* The tokens are sealed with **Fernet** (AES + an HMAC that detects tampering) before they reach Neon. The key is derived from `KOE_SECRET_KEY`, which exists only in `.env` and Render. A copy of the database alone is useless. Losing or changing the key just means reconnecting.
- *Whose request is this?* A context variable (`identity.OWNER`) is set when a request is authenticated. It follows the request into the worker thread where `google_auth.credentials()` runs, so the tools load the caller's own connection without passing a user id through every function.
**How it connects:** Settings → `/auth/google/connect` → Google consent → `/auth/google/callback` (`purpose=connect`) → `connections.save` (encrypted) → `/?connected=google#settings`. Later: the agent → calendar/sheets tool → `google_auth.credentials()` → `connections.google_credentials()` → refresh if needed → Google API.
**Try it yourself:** Signed in on Koe, open Settings → Connections → Connect → allow both. Then ask "what's on my calendar today?". `uv run pytest -q tests/test_connections.py` runs 7 tests.
**Gotchas:**
- The Google Cloud project behind the web client needs the **Google Calendar API** and **Google Sheets API** enabled.
- `KOE_SECRET_KEY` must be identical in `.env` and on Render, because both use the same Neon database.
- Under the dev Vite server, a 204 reply must have *no* body. FastAPI sent `null`, the browser aborted the response, and the list didn't refresh. The endpoint now returns an empty `Response(204)`.
**Measured:**
- 7 new tests: encryption and a changed key; the connect URL; stored encrypted; unticked permission; the tools use and refresh the connection; a friend never falls back to the owner's calendar; disconnect revokes. Removing the friend guard fails its test.
- 230 backend tests and 18 frontend tests pass.
- Google accepted the real connect request (its sign-in page, with no `invalid_scope` or redirect errors).
- In the browser, with a temporary test account (deleted afterwards): the list renders, the notice shows once, and the connected state plus Disconnect work. Disconnect takes about 5 s because of Google's revoke call, so the button says "Disconnecting…".
**Interview line:** "I separated identity from authorization: sign-in uses minimal OpenID scopes, while each service is a separate incremental-consent connection whose refresh token is Fernet-encrypted at rest and loaded per request through a context variable."

## Step 44: "Create my timesheet": no Sheet ID to copy  (Phase 5c, task 7 · 2026-10-13)
**Files:** backend/migrations/005_prefs.sql (new) · backend/koe/{connections.py,db.py,tools/sheets.py} · backend/tests/{test_connections.py,conftest.py} · frontend/src/settings/Connections.tsx
**What it does:** Once Google is connected, Settings → Connections shows **Timesheet → Create my timesheet**. Koe creates "Koe timesheet" in *your* Google Drive, with an **Hours** tab and exactly the five headers the timesheet tool checks for. It remembers the sheet for you, and the button becomes **Open**. Logging hours then goes to your own sheet, and every row still needs your OK. Only the owner can still fall back to `GOOGLE_SHEETS_ID` from `.env`.
**Core concept:** *Make the setup step a button.* One `spreadsheets.create` call with the header row inside the request body replaces "make a sheet, type five headers exactly, copy the ID out of the URL, paste it into .env". The sheet's ID is stored per person in `koe_prefs`, a small key/value table. It's cached in memory, because the tool validates a proposal outside any worker thread.
**How it connects:** Settings → `POST /api/connections/google/timesheet` → `google_auth.credentials()` (your connection) → Sheets API → `koe_prefs.google_sheets_id`. Later: `sheets.prepare_hours()` → `timesheet_id()` → your sheet.
**Try it yourself:** Connect Google, then Create my timesheet, then Open: the headers are already there. Ask Koe "log 2 hours for Acme today", then Confirm, and a new row appears.
**Gotchas:**
- The Google Sheets API must be enabled in the client's Cloud project, or Google refuses with an error, which the page shows.
- The prefs cache is per process. Tests reset it in `conftest.py`, so one test's sheet can't leak into another.
**Measured:** 2 new tests: the request carries the headers and your token, the ID is stored and used by the tool, and a friend without a timesheet is refused rather than given the owner's. 232 backend tests and 18 frontend tests pass.
**Interview line:** "I replaced a five-step manual setup with one API call that creates a correctly shaped spreadsheet in the user's own Drive, and stored the result as a per-user preference with an owner-only fallback."

## Step 45: everyone's activity, approvals and conversation are their own  (Phase 5c, task 5 · 2026-10-13)
**Files:** backend/koe/{store.py,app_channel.py,dashboard.py,voice_call.py} · backend/tests/{test_isolation.py (new),conftest.py}
**What it does:**
- The activity log, pending approvals and daily notes in Neon are stored under the person who is asking, not the one configured owner.
- The Koe app keeps one conversation per person: their history, working memory and open approvals.
- Calls and the dashboard record who connected (from their one-time ticket), so a call's tools and records belong to that person.
**Core concept:** *The owner comes from authentication, never from input.* `identity.OWNER` is set where a request or socket is authenticated. That's the session cookie or ticket, or the access token for the owner. Storage reads the owner from there. The browser and the model can't choose whose data they touch, so approving someone else's action fails: the database function checks owner + conversation.
**How it connects:**
- `auth.http_owner` / `auth.ws_owner` → `identity.OWNER` → `store.rpc(p_owner=…)` → `koe_propose_action` / `koe_claim_action` (owner-checked SQL).
- `app_channel.chat()` → `CHATS[owner]`.
**Try it yourself:** `uv run pytest -q tests/test_isolation.py` runs two tests:
- proposals and claims carry the asking person's owner id;
- two people chatting get separate histories and separate approval contexts.
**Gotchas:**
- `whatsapp.py` and `github_hooks.py` still act as the owner, which is correct: WhatsApp and GitHub alerts are owner-only channels for now.
- The Notion workspace (another session's work in progress) still uses the configured owner. It should switch to `identity.owner_id()` when it's committed.
- Friends stay blocked at sign-in until their own connections exist, so this is groundwork that's already enforced.
**Measured:** 234 backend tests pass. Reverting the store to the fixed owner fails the new test.
**Interview line:** "Multi-tenancy is enforced where identity is established: a context variable set at authentication flows into every storage call, so no request body or model output can pick whose rows it touches."

## Step 46: a daily limit on the shared Gemini key, or bring your own  (Phase 5c, task 10 · 2026-10-13)
**Files:** backend/koe/usage.py (new) · backend/migrations/006_usage.sql (new) · backend/tests/test_usage.py (new) · backend/koe/{whatsapp.py,app_channel.py,voice_call.py,connections.py,db.py,config.py} · backend/tests/{conftest.py,test_voice_call.py} · backend/.env.example · frontend/src/settings/Connections.tsx
**What it does:**
- Friends using Koe on the owner's free Gemini key get `KOE_DAILY_TURNS` (default 60) turns a day. A turn is a message, a voice note, or starting a call.
- Past the limit, the chat explains how to continue, and a call closes with the same message.
- In Settings → Connections, a friend can paste their **own free Gemini key**. Koe checks it with Google, stores it encrypted, and from then on uses it for that person with no limit.
- The owner is never limited.
**Core concept:**
- *Quota on a shared resource.* An atomic upsert, `insert … on conflict do update set turns = turns + 1 returning turns`, counts per person per day in Asia/Kolkata. Two quick requests can't both read "59" and both pass.
- *Per-person clients.* `whatsapp.gemini()` returns one reused client per key, so the app chat, voice-note transcription and spoken replies all follow the person's key without changing their call sites. Calls get the same key.
**How it connects:**
- `/api/app/messages` and `/voice` → `usage.spend()` → `koe_usage`; then `whatsapp.gemini()` → `usage.gemini_key()` → the person's own key (an encrypted connection) or the shared one.
- Settings → `PUT /api/connections/gemini` → Google `models.list` check → `connections.save` (encrypted).
**Try it yourself:** `uv run pytest -q tests/test_usage.py` runs 4 tests:
- the limit applies to a friend but not to the owner;
- an own key lifts the limit and is the key used;
- a wrong key is refused before it's stored, and a right key is stored encrypted;
- over the limit, the chat answers without calling Gemini.
**Gotchas:**
- The call tests used to patch `voice_call.settings`, which went away when the module stopped needing it. They now patch `koe.config.settings`.
- The own-key cache is per process, and tests reset it in `conftest.py`.
- Friends are still kept out at sign-in until their own GitHub/Notion connections exist, so the limit has no effect yet.
**Measured:** 238 backend tests and 18 frontend tests pass. Migration 006 is applied to Neon.
**Interview line:** "I metered a shared free-tier API per user with an atomic upsert counter, and let users bring their own key, validated against the provider before it's encrypted and routed per request."

## Step 47: connect your own GitHub and pick your repositories  (Phase 5c, task 8 · 2026-10-13)
**Files:** backend/koe/{auth.py (GitHub connect + callback),connections.py (token/login/repos, repo picker API, revoke),dashboard.py,tools/github.py,tools/github_work.py,config.py} · backend/tests/{test_github_connect.py (new),test_events.py,conftest.py} · frontend/src/settings/{Connections.tsx,settings.css} · frontend/src/pages/Guide.tsx · backend/.env.example · docs/DEPLOY.md (§7)
**What it does:**
- Settings → Connections → GitHub → **Connect** goes to GitHub's authorize page and back.
- **Choose** lists your repositories (most recently pushed first). Tick up to 20 and Save.
- The PR tools, "what did I ship", PR comments and the dashboard's PR panel then use *your* token, *your* login and *your* repositories.
- Disconnect revokes the grant at GitHub.
- The owner can still fall back to `GITHUB_TOKEN`/`GITHUB_REPOS` from `.env`. Anyone else gets "connect GitHub", never the owner's token.
**Core concept:**
- *OAuth App + PKCE.* GitHub's web flow sends a `state` (forgery guard) and a PKCE challenge. The code is exchanged with the client secret and the verifier, asking for JSON (`Accept: application/json`). GitHub OAuth App tokens don't expire by default, so there's no refresh step, unlike Google.
- *Where to put per-person defaults.* The token lives encrypted in `koe_connections`. The chosen repositories are a plain preference in `koe_prefs`, because they aren't secret. One cache per process keeps the tools from hitting the database on every call.
**How it connects:**
- Settings → `/auth/github/connect` → github.com/login/oauth/authorize → `/auth/github/callback` → token exchange → `GET /user` (login) → `connections.save`.
- Tools → `connections.github_account()` / `github_repos()`.
**Try it yourself:**
- Create the OAuth App (DEPLOY.md §7), then Connect, then Choose, then ask "any PRs waiting for my review?".
- `uv run pytest -q tests/test_github_connect.py` runs 4 tests:
  - connect sends PKCE and the right scope, and the token is stored encrypted;
  - repos are listed and chosen;
  - tools use the caller's token, and a friend never gets the owner's;
  - disconnect revokes with basic auth.
**Gotchas:**
- GitHub OAuth Apps can have several callback URLs, so the live site and localhost can share one app.
- The dashboard test expected the old "add GITHUB_TOKEN" wording. It now checks the new "Settings → Connections → GitHub" message.
**Measured:**
- Turning the owner-only fallback into "everyone" fails the friend test.
- 242 backend tests and 18 frontend tests pass.
- In the browser with a temporary test account (deleted afterwards), the Connections section shows Google and GitHub connected, Notion "Coming soon", Timesheet, Repositories → Choose, and the Gemini key form. The dashboard stays Live.
**Interview line:** "Every integration follows the same pattern: OAuth with PKCE, an encrypted token per user, non-secret choices as preferences, and tools that resolve credentials from the request's identity with an owner-only fallback, which a test proves can't leak."

## Step 48: the chat wasn't broken, Gemini was busy: a real fallback chain  (2026-10-13)
**Files:** backend/koe/gemini.py (new) · backend/tests/test_gemini.py (new) · backend/koe/{text_agent,whatsapp,app_channel,voice_call,usage,config}.py · backend/.env.example · backend/tests/{conftest,test_app_channel,test_isolation,test_usage,test_voice_call,test_whatsapp_turns}.py
**What it does:** Koe's text answers, voice-note transcription and spoken replies no longer fail when one Gemini model is overloaded or one key runs out. Calls start on a key that isn't resting.
**Core concept:** *Read the error code before choosing a fallback.*
- **429** RESOURCE_EXHAUSTED means *this key's* quota is used up, so switch key.
- **503** UNAVAILABLE ("high demand") means *the model* is overloaded for everyone, so switch model. A second key gets the same 503.

A failed key or model "rests" (10 min / 2 min), so the next turn doesn't wait on it again. Google's SDK retries 503s by itself for minutes, so each attempt is now single and short, and Koe chooses where to go next.

The OpenRouter backup never ran, because `.env` said `OPEN_ROUTER_API_KEY` while the setting read `OPENROUTER_API_KEY`. Both spellings are accepted now.
**How it connects:** `text_agent.chat()` → `gemini.generate()` (round 0 may switch; later tool rounds stay on that model) → OpenRouter if every Gemini option fails → "busy" message. `whatsapp.transcribe()` → `gemini.generate()`. `speak()` and calls → `gemini.live_client()`.
**Try it yourself:** `uv run pytest -q tests/test_gemini.py` runs 5 tests.
**Gotchas:** A turn keeps one model after it starts using tools, because the model's own tool calls and thought signatures are in the history.
**Measured (live, both keys):**
- gemini-3.8-flash: 503.
- gemini-3.6-flash: OK in 2.4–3.1 s. gemini-3.5-flash: OK 2.7 s. gemini-3-flash-preview: OK 1.7 s.
- gemini-3.7-flash took 185 s with the SDK's retries.
- A real chat turn now: 11 s, with the notice "gemini-3.8-flash is busy; using gemini-3.6-flash".
- OpenRouter: OK in 4.6 s.
- 273 backend tests pass.
**Interview line:** "I distinguished per-key quota errors from model-wide overload and routed each to the right fallback, with circuit-breaker rests and the SDK's hidden retries turned off, so a busy model costs seconds instead of minutes."

## Step 49: real end-to-end test, and making a turn fast  (2026-10-13)
**Files:** backend/koe/{gemini.py,store.py,text_agent.py,agent.py} · backend/tests/{test_gemini.py,test_store.py,test_isolation.py,conftest.py}
**What it does:**
- Tested Koe end to end against the owner's **real** accounts, through the same HTTP API the app uses, then removed every test item:
  - Calendar read;
  - finding a free slot;
  - booking a "Koe E2E test" event (proposal → Confirm → checked directly in Google Calendar: 16:00–16:15 IST, no attendees → deleted);
  - a timesheet row (proposal → Confirm → checked directly in Google Sheets, row 3 with the action ID → deleted);
  - a Notion task (proposal → Confirm → checked directly in Notion, Type Task, Status Open → moved to trash through Koe with approval).
- Then made turns faster. One reused Neon connection for the activity/approval store (it opened a new one per write, ~1.3 s each). Activity records are written in the background. Each Gemini attempt is capped at 15 s, an overloaded model rests 5 min, and the model that answered last is tried first. Later tool rounds may fall back too, because a turn begun on gemini-3.6-flash (with thought signatures) finished correctly on gemini-3.5-flash and gemini-3-flash-preview.
**Core concept:** *Measure the whole turn before optimising.* Logging every model attempt (model, key, result, seconds) showed where time went:
- busy models that hang ~42 s before a 504;
- a key out of quota (429 in 0.6 s);
- ~1.3 s for every activity-log write.

Each had its own fix. No guessing.
**How it connects:** `text_agent.chat()` → `gemini.generate()` (logs `koe.gemini: <model> on key N: ok|503|504|429 in Xs`) → tools → `store.rpc()` on the reused connection (one transaction per call; a failed write is never retried). Activity records go through `store.record_later()`.
**Gotchas:**
- On Windows Git Bash, a command-line argument like `/status` is silently rewritten into a Windows path (`C:/Program Files/Git/status`), so the first Notion API check returned 404 from the test harness, not from Koe. Use `MSYS_NO_PATHCONV=1`.
- Free-tier Gemini was congested during the test (503/504 on most models), so turns still took 22–59 s, though they no longer fail. At calmer times gemini-3.8-flash answers in ~3 s.
**Measured:**
- activity write 1.37 s → 0.43 s on a reused connection, and it's no longer on the turn's critical path;
- approve → execute: 8.3 s (Calendar), 6.7 s (Sheets), 9.5 s (Notion);
- 274 backend tests pass.
**Interview line:** "I tested the agent end to end against real Calendar, Sheets and Notion, verified every write at the source and cleaned up. Then I instrumented each model attempt and removed per-write connection setup to cut the parts of the latency I control."

## Step 50: a calmer Settings, a real Dashboard page, and a footer  (2026-10-13)
**Files:** frontend/src/dashboard/DashboardPage.tsx (new) · frontend/src/dashboard/dashboard.css (new) · frontend/src/AppFooter.tsx (new) · frontend/src/dashboard/{Dashboard.tsx,state.ts,useDashboard.ts} · frontend/src/App.tsx (nav, routing, Home markup, footer only) · frontend/src/settings/{SettingsPage.tsx,Connections.tsx,settings.css} · frontend/src/chat/chat.css (old `.device*` rules removed) · frontend/src/index.css · frontend/src/notion/notion.css · frontend/src/install/install.css · frontend/src/pages/Guide.tsx · docs/SPEC.md §6 · docs/DECISIONS.md
**What it does:**
- **Settings:** the companion studio is untouched (the viewer, Portrait/Full body, Say hi, Rotate, the list and the Use button). Everything that was squeezed under it into a 340px column now has its own sections below it: **Account**, **Connections**, **Your Gemini key** and **This device**. Each section has a title and one line of context on the left, and a card of rows on the right. Every row has the same shape: icon, name, one-line status, one action. Timesheet sits under Google, and Repositories (with its checklist) sits under GitHub, because each belongs to that service.
- **Dashboard:** a new page at `#dashboard` (the four-squares icon in the nav). It shows a grid of panels on desktop (Today, Approvals, Waiting for your review, Your pull requests, Activity), two columns on tablets and one column on phones. Home keeps the mascot, the greeting and Call, plus a slim **Today** card (the next 3 events and what's waiting) with an **Open dashboard** link.
- **Navigation:** a **?** button in the top bar opens the Guide. A footer on Home, Dashboard, Notion and Settings links to the Guide, Install the app, Privacy and Terms.
- **Notion:** layout only. The page uses the full width again, the heading weight matches the other pages, and panels are flat surfaces with consistent corner radii instead of a border drawn on top of a fill.
**Core concept:**
- *One data source, many views.* The dashboard WebSocket lives in `App` (`useDashboard`). Home's summary, the Dashboard page and the call's Day card all read the same `data`, so opening the Dashboard never opens a second socket.
- The list pieces (`TodayList`, `PRList`, `ApprovalList`, `ActivityFeed`) are shared by the compact tabbed card and the full page, so both always show the same thing.
- *A row pattern* (icon, name, status, action) makes a settings page scannable: your eye runs down the left edge for names and the right edge for buttons.
**How it connects:** `App` → `useDashboard()` → `{data, connected}` → `TodaySummary` (Home) / `DashboardPage` (#dashboard) / `Dashboard` (call → Day). Approve/Reject on the Dashboard page calls the live call's `decide`, the same path the call panel uses. Settings rows call the same endpoints as before (`/api/connections…`, `/auth/<provider>/connect`, and the push and install helpers).
**Try it yourself:** run `npm run dev` and sign in. Click the four-squares icon (Dashboard) and the ? icon (Guide), then scroll to the bottom of Home or Settings to see the footer. Narrow the window to 375px to see the panels stack.
**Gotchas:**
- Hash routing: an in-page anchor like `#connections` would switch the app back to Home, so the Settings sections aren't linked with anchors.
- The footer needs every page to be at least one screen tall, so `.app` is now a flex column (except on Chat). An auto margin in a flex column shrinks a box to its content, which is why the Notion and Install pages also need `width: 100%`.
- On Home the footer stays in the right-hand column, so it never covers her desk.
**Measured:**
- `tsc -b`, `npm run lint` (0 errors, 4 existing warnings), `npm test` (18 pass) and `npm run build` all pass.
- Headless Chrome screenshots at 1280px and 375px, in light and dark, of Home, Dashboard, Settings, Notion and Install. Settings was also captured with a mocked Google + GitHub connection, to check the Timesheet and Repositories rows and the checklist.
**Interview line:** "I split one overloaded screen into a mascot-first Home, a dedicated dashboard and a sectioned settings page. All three read one shared WebSocket state through shared list components, so the views can't drift apart."

## Step 51: close backend fallback gaps and identify live deployments (2026-10-13)
**Files:** backend/koe/{gemini,text_agent,app_channel,store,main,config}.py · tools/github_work.py · backend_status.py (new) · backend/tests/test_backend_reliability.py (new) and provider/PR regression tests · backend/.env.example · render.yaml · backend documentation. No frontend files changed.

**What it does:** Exhausted Gemini 500/504 and transport failures now reach the existing free text fallback before tools execute. Each model/key generation chain has a 30-second total budget, in addition to the existing 15-second SDK attempt timeout. PR summaries use the same bounded Gemini helper and caller's credential selection while preserving their structured, tool-free analysis. Cold credential lookups run off the event loop. Voice-note retries discard incomplete audio from the failed key, avoiding a duplicated prefix.

**Core concept:** *Test failure paths, not just successful requests.* Ten new regressions initially reproduced missing fallback coverage, an unbounded generation chain, partial audio retention, missing audit lifecycle control and missing deployment diagnostics. Auth/request errors remain separate from availability errors. A model/provider fallback never resets the agent loop or repeats an executed tool. Existing approval rules remain unchanged.

**Audit lifecycle:** Best-effort activity logging has a 128-task backlog and a five-second shutdown drain. It keeps the original caller's context, reports saturation and consumes unexpected task failures without logging their private bodies. Proposal/claim/finish still execute synchronously through the durable store. In-flight SQL cannot be forcibly cancelled by cancelling its worker-thread await; existing database timeouts bound it, and it is never replayed.

**Deployment:** `/health` still returns `{"ok":true}` and adds a validated revision header. New owner-authenticated `/api/backend/status` reports key/configuration presence booleans, generation limits and audit backlog, with no-store caching and no provider/database calls. Anonymous/friend access is denied; credential values and user records never appear. The Blueprint now lists optional second-Gemini/OpenRouter credentials without values. Same-project Google keys share quota, so comments and setup instructions no longer promise an independent allowance from a second key.

**Live finding:** Public Render health/schema returned 200 and exposed Notion/Connections routes. Owner-authenticated Notion status returned connected=true and workflow_ready=true. The prior pre-Notion deployment diagnosis is therefore out of date; the exact live revision and fallback-key presence remain unknown until diagnostics are deployed. No Render environment/deployment changes, model-quota-consuming acceptance repeats, real bookings, spreadsheet writes or Notion records were performed. One initial synthetic regression bypassed the mocked helper and reached Google using the invalid test credential; direct SDK client construction is now explicitly blocked in that test.

**Verification:** All 289 backend tests passed (76.39 seconds); 43 focused reliability/provider/PR tests also passed. uv's lock consistency check resolved 71 packages offline, source compilation passed, and an isolated Uvicorn process started with dummy credentials. Its health returned 200, anonymous diagnostics 401, authenticated diagnostics 200 with no-store headers. The isolated process was stopped after the check. Git diff confirms no frontend changes. The existing Starlette/httpx deprecation warning remains. Validation completed locally before publication; the existing app servers were left undisturbed while the UI helper completes its work. The user subsequently authorized pushing the completed changes to GitHub.

**Try it yourself:** Run `uv run pytest -q` from backend. After deploying, compare `(Invoke-WebRequest 'https://koe-backend-dt5m.onrender.com/health').Headers['X-Koe-Revision']` with the intended commit. Use the existing owner authentication to read `/api/backend/status`; do not put credentials in URLs. Deployment steps and the current live probe findings are in DEPLOY.md.

**Interview line:** "I reproduced provider and shutdown edge cases with synthetic regressions, bounded work without replaying tools, and added secret-free deployment evidence so a healthy old build cannot be mistaken for the latest backend."

## Step 52: deterministic GitHub reports (2026-10-13)
**Files:** DETERMINISTIC_FEATURES.md, SPEC.md, DECISIONS.md; github_work.py, new github_stats.py, agent.py, new test_github_stats.py.

**What it does:** Exact yesterday and exclusive-end date ranges; Python-calculated counts by selected repository; opt-in bounded additions/deletions/net changes; current and longest contribution streak within an explicit window. No model performs arithmetic. GitHub contribution days are not a commit-only streak. Default-branch commits and merged PRs remain separate measures.

**Core concept:** Trust evidence coverage, not a plausible answer. Duplicate pages are deduplicated, dates are filtered locally, missing commit details remain unknown, and missing contribution days fail instead of being filled with zero. The agent exposes these reads through the shared text/Live registry.

**Verification:** Six new regressions failed before implementation; 17 focused GitHub tests then passed using synthetic API responses. Windows sandbox temp-directory failure required running pytest outside the filesystem sandbox; no real provider calls or account changes were used. Full-suite verification follows the remaining slices.

**Try it yourself:** Ask “What did I ship yesterday?”, “Show my commits by repository yesterday, including added/deleted lines”, or “What is my contribution streak over the last 30 days?” Results disclose their window and scope. No UI changes.

**Interview line:** "The model selects the metric, while Python computes it from bounded, deduplicated evidence and reports what it could not verify."

## Step 53: approved Calendar details and reminders (2026-10-13)
**Files:** tools/calendar.py, agent.py, test_calendar.py, test_agent.py and the feature checklist.

**What it does:** Optional description/location and up to five popup/email reminders, with integer lead times between 0 and 40320 minutes. Every changed field appears in the existing approval summary. Omitted fields preserve existing/default settings; empty strings clear text and an empty reminder list disables notifications. Calendar list responses expose existing details/reminder settings.

**Core concept:** Omitted and empty values are different intents. Python validates both and builds the exact API payload; the LLM cannot bypass approval or change notification rules. Existing overlap rechecks, stable action IDs and event-version checks remain.

**Verification:** Eight new regressions first failed on unsupported arguments. Focused Calendar/approval/call tests exercise exact payloads, invalid reminders and preservation versus clearing. No invitations or events were sent to real accounts. Notification delivery depends on Google/device settings; this is not a guaranteed phone alarm.

**Try it yourself:** “Book a review tomorrow at 7 PM for 30 minutes, at the library, and remind me 15 minutes before.” Koe must present the complete proposal before writing.

**Interview line:** "A voice request becomes a typed, approved Calendar payload with explicit preservation and clearing semantics."

## Step 54: optional Sheets columns (2026-10-13)
**Files:** tools/sheets.py, agent.py, new test_sheet_fields.py and the feature checklist.

**What it does:** sheets_schema reads the configured timesheet's actual headers (up to AZ). The existing five base columns remain; up to 20 existing optional columns can be filled by exact name with literal text, finite numbers or booleans. The proposal previews every value and freezes the header order; execution rereads it and rejects schema/destination changes before appending. No columns or existing rows are edited.

**Core concept:** Map names to verified column positions rather than asking the model for spreadsheet coordinates. Python builds the ordered row; RAW input prevents user text from being interpreted as a formula. Missing optional fields stay blank in the new row. Required fields and the action ID cannot be overridden.

**Verification:** Eight new regressions first failed; 42 Sheets/log/approval tests passed after implementation, using synthetic API responses. Unknown/reserved/nested/nonfinite fields, duplicate headers and schema changes are covered. No real rows were written.

**Try it yourself:** Add optional headers such as Project, Billable or Amount after the five base columns in your sheet. Ask “Log one hour for Client tomorrow; Project Koe and Billable true.” Koe reads the schema and presents the complete approved row.

**Interview line:** "Optional spreadsheet fields are bound to verified headers and a frozen approval, not model-invented cell addresses."

## Step 55: typed optional Notion properties (2026-10-13)
**Files:** notion_service.py, tools/notion.py, notion_api.py, agent.py, new test_notion_fields.py and the feature checklist.

**What it does:** notion_schema and owner-authenticated GET /api/notion/schema expose editable existing property names, types and option names. notion_save accepts up to 20 optional values: text, finite number, checkbox, ISO date/offset timestamp, HTTP(S) URL, email and existing select/multi-select/status options. Python resolves property/option IDs, freezes the requested property's schema/source with the proposal, and rechecks before writing. Existing record reads expose optional values. Unrelated properties remain untouched.

**Core concept:** The model supplies intent, not Notion API objects. Python rejects invented properties/options, computed results and tracking-field overrides before proposing. The approved values are the values sent. Notion remains owner-only until per-user Notion OAuth is implemented; that restriction is enforced in tool routing and the service boundary.

**Verification:** Sixteen new regressions first failed; 94 Notion/workspace/API/approval tests then passed with synthetic responses. Tests cover all supported scalar types/options, stale property IDs, invalid values, read-only fields, proposal previews and owner isolation. No real Notion records were created.

**Try it yourself:** Add a Priority select property with a High option in Notion, then ask “Create a review task for tomorrow with Priority High.” Koe discovers the existing property and previews its exact value for approval.

**Interview line:** "Schema discovery becomes a typed approval contract, so optional fields cannot silently change meaning before execution."

## Step 56: review boundaries and verify the integration batch (2026-10-13)

### Follow-up phase, 2026-10-14: schema/row slices
Sheets column creation passed 43 focused tests after nine new failures established the missing behavior. Stable row discovery/editing then passed 52 focused tests after nine more regressions. New edits use unique action IDs, typed row/header versions and Google developer metadata; sparse RAW updates preserve unrequested cells/formulas and tracking IDs. A synthetic move immediately before the value write still edits the correct row. No real Sheets writes, UI edits or Render changes were made. The schema/row contract and known external-editor race limit are in SCHEMA_ROW_EDIT_PLAN.md.

Next phase: approved schema creation and safe Sheets row editing is tracked in [SCHEMA_ROW_EDIT_PLAN.md](SCHEMA_ROW_EDIT_PLAN.md), requested 2026-10-14. Render deployment is handled by the user.
**Files:** GitHub history/statistics, Sheets/Notion validators, shared declaration, regression tests and integration docs.

**What it does:** Adds a 30-second total history deadline and a 15-second optional line-detail deadline, preserving completed detail reads with explicit partial coverage. Cold GitHub credential/preferences reads run off the event loop. Contribution requests use UTC bounds and provider calendar labels, return compact summaries by default, and mark a one-day empty window's prior streak unknown. Extreme integer inputs are rejected before float conversion. URLs reject whitespace/control characters. Returned commit IDs are validated before detail endpoints are built.

**Core concept:** Unknown, partial and complete are separate states. Time budgets stop slow reads from consuming an unbounded turn; missing days/details never become plausible numbers. Optional field contracts also survive JSON persistence and execute exactly once through the existing approval path.

**Verification:** The first full run passed 327 tests. Five additional review regressions then reproduced deadline, streak-window and extreme-integer bugs; they passed after fixes. Two further tests cover complete optional Sheets/Notion proposal → JSON roundtrip → approval → real adapter → no replay flows. Final full backend suite: **334 passed**, one existing Starlette/httpx deprecation warning, 105.72 seconds. Read-only real-account probes succeeded: GitHub yesterday activity/count/line read 6.18 s, contributions 4.02 s, Sheets schema 4.59 s, Notion schema 2.97 s. These are individual measurements, not percentile claims. No LLM calls, real writes, credentials/scopes/dependency changes, UI edits, server restarts or deployments were made.

**Startup check:** An isolated TestClient returned health 200 and anonymous Notion schema 401. All 17 shared function declarations validated/serialized through the installed Google SDK. External integrations were disabled for that startup check. Diff review and a scan against local credential values found no frontend edits or exposed secrets.

**Try it yourself:** Follow the examples and feature statuses in DETERMINISTIC_FEATURES.md. New code is saved in local commits; GitHub publication and hosting are separate from this implementation request. The current running processes were left undisturbed.

**Interview line:** "I put evidence coverage and latency budgets into the backend contract, then verified both failure boundaries and complete approved writes without consuming model quota."
