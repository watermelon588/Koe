# Plan and timeline: Koe (声)

**Total:** about 4 weeks at 3–5 h/day (about 80–100 h). Start date: the first build session.
**Difficulty:** about 7/10. Hardest parts: real-time audio streaming and barge-in, time/timezone correctness, Google OAuth quirks, Meta setup.
**Rule:** every phase ends with a working, demoable slice, verified, logged in BUILD_LOG.md, and committed.

> **Current phase: Phase 2 implementation ready for live setup/verification (2026-10-12).** Supabase storage, Calendar tools, approval flow, and text CLI are implemented and tested locally. User must fill Supabase env values, apply the migration and complete Google OAuth; then verify one real approved booking before marking Phase 2 done. See [PHASE2_SETUP.md](PHASE2_SETUP.md). Phase 1 measured p50 ≈ 1.7 s, above the 1.5 s target.

> **Next slice built: Phase 3 live dashboard (2026-10-12).** At the user's request, implementation continued while credentials are deferred. Authenticated events, real read panels, activity, original-call approval controls and measured latency display are implemented. Local tests and isolated browser fixtures verify the wiring; real account data and an approved booking still await Phase 2 setup.

> **Phase 4 implementation built (2026-10-13).** PR summaries, shipped history, Notion daily log, approved PR comments and approved Sheets entries are implemented and tested with fake APIs. Live acceptance remains pending; credentials can be added later using [PHASE4_SETUP.md](PHASE4_SETUP.md).

## Overview
| Phase | Week | Goal | Demo when done |
|---|---|---|---|
| 0 | W1 d1–2 | Accounts, keys, scaffold | Each service answers one test call |
| 1 | W1 d3–5 | **Live voice call, no tools** (riskiest first) | Natural conversation in the browser, measured latency |
| 2 | W2 d1–3 | Agent core + GitHub read tools + Calendar tools + approval gate | "What's waiting for my review?" and "Book 30 min with Rahul at 7" by voice |
| 3 | W2 d4–7 | Dashboard + mascot + live events | Calendar and GitHub panels change live while you talk; mascot reacts |
| 4 | W3 d1–3 | PR summaries, "shipped today", Notion log, Sheets hours, `github_comment` | "What did I ship today?" writes the Notion log |
| 5 | W3 d4–7 | WhatsApp channel + GitHub webhook alerts | Voice note books a meeting in about 3–4 s; CI failure pings WhatsApp |
| 6 | W4 d1–2 | Shared memory across channels | Web call knows what you did on WhatsApp |
| 7 | W4 d3–7 | Evals, deploy (Azure + Vercel), README, demo video | Accuracy and latency numbers in the README; works with the laptop off |

## Phase 0: setup
- [ ] Create accounts and keys (SERVICES_AND_COSTS.md, "Accounts the user creates"). Gemini ✅ · GitHub ✅ · Notion ✅ · WhatsApp ✅ · **Google OAuth `credentials.json`: carried over to before Phase 2.**
- [x] `git init`, `.gitignore` (`.env`, `credentials.json`, `token.json`, `koe.db`, `node_modules`, `.venv`).
- [x] Backend scaffold: `uv init`, deps from TECH_STACK.md, `koe/main.py` with `/health`, `config.py`, `.env.example`.
- [x] Frontend scaffold: `npm create vite@latest frontend -- --template react-ts`.
- [x] One smoke script per service (Gemini text call, Calendar list, Notion read, GitHub `/user`, WhatsApp send "hello" to your number).
- [x] Record the verified Gemini Live model ID and free-tier limits in SERVICES_AND_COSTS.md.
- [x] Decide Learning vs Explanatory style (DECISIONS.md).
**Done when:** all smoke scripts pass (`uv run python -m scripts.smoke` from backend/).

## Phase 1: live voice call (no tools)
- [x] Frontend: mic permission → `AudioWorklet` → 16 kHz PCM16 chunks → `/ws/call`.
- [x] Backend: `/ws/call` ⇄ Gemini Live session (system prompt only); relay audio both ways.
- [x] Frontend playback: queue 24 kHz PCM chunks → speaker without gaps.
- [x] Barge-in: on Gemini "interrupted", flush the playback queue.
- [x] Latency: timestamp speech-end and first-audio-out; print p50/p95 per call. (Backend p50 ≈ 1.7 s, n=16. Over the 1.5 s target; tuning next.)
- [x] Session resumption when Gemini sends a GoAway (+ resume after unexpected drops; context compression).
**Done when:** a 3-minute natural conversation, interruptions work, p50 latency measured and written in BUILD_LOG.
**Risk:** audio format bugs (sample rate, endianness) cause chipmunk or static sound. Test with a known sine wave first.

## Phase 2: agent core + GitHub read + Calendar
- [x] `agent.py`: tool registry (schema + `needs_approval`), system prompt (persona, timezone, working hours, rules).
- [x] `store.py`: Supabase REST adapter and PostgreSQL migration with restricted atomic approval functions (replaces SQLite by user request).
- [x] Tools: `github_review_queue`, `github_my_prs`, `calendar_list`, `calendar_find_free`, `calendar_upsert_event` wired to the registry; Calendar awaits real OAuth setup.
- [x] Approval gate: persisted proposal → explicit spoken/typed/UI confirmation → atomic claim → execute. Safety tests cover expiry, rejection, ambiguity, replay and storage errors.
- [x] Double-booking re-check + timezone, all-day event, pagination and event-move tests.
- [x] Text-mode agent loop and `python -m scripts.chat` CLI.
- [ ] Live verification: Supabase migration/key, Google consent, voice GitHub read and one approved booking on a test calendar.
**Done when:** by voice, "what's waiting for my review?" is correct and "book 30 min with Rahul at 7" books after you say yes.

## Phase 3: dashboard + mascot
- [ ] Decide the mascot design and name with the user (SPEC §6).
- [x] `/ws/events` + `events.py` pub/sub; every registered tool call, approval and matched GitHub alert emits an event.
- [x] Panels: Today (Calendar), GitHub (review queue, my PRs + CI), Activity (with Approve/Reject for the original active call), Latency. Day/Chat switch keeps them accessible during calls; no sample rows remain.
- [x] Mascot states: idle / listening / thinking / speaking / happy / error, driven by call events + `AnalyserNode`; idle dashboard alerts trigger a brief reaction.
- [x] Access token on `/ws/events` (ARCHITECTURE §9). `/ws/call` authentication was brought forward into Phase 2 to protect the new writer.
- [ ] Live account verification: connected Calendar/GitHub panels update during a real call and an approved booking; requires deferred Phase 2 setup.
**Done when:** while talking, the panels update live and the mascot reacts in sync.

## Phase 4: deeper GitHub + Notion + Sheets
- [x] `github_pr_summary` (diff truncation, risk notes), `github_shipped`, `github_comment` (approval).
- [x] `notion_log` (daily page in the "Koe Daily Log" database), `sheets_log_hours` (approval).
- [x] Confirm Sheets: included, with approval before every entry (2026-10-13).

Implementation is verified locally against simulated API boundaries; live acceptance still waits for credentials. See [PHASE4_SETUP.md](PHASE4_SETUP.md).
- [ ] Live acceptance: real PR summary, shipped history → Notion, one intended approved comment and one approved timesheet entry.
**Done when:** "What did I ship today?" gives a correct list and writes the Notion log; "Summarize #42" is accurate on a real PR.

## Phase 5: WhatsApp + GitHub alerts
- [x] `/webhooks/whatsapp`: GET verify, POST signature check, 200 fast, background processing, sender allow-list. (Inbound messages are only logged until Phase 2's text loop exists.)
- [ ] Voice note: media download → Gemini with audio → agent core (text loop) → reply.
- [ ] Interactive Confirm/Cancel buttons → resolve pending actions.
- [x] `/webhooks/github`: signature, dedupe, 4 alert rules (SPEC §4) → WhatsApp. (Real sends blocked by Meta, see SERVICES_AND_COSTS; dedupe is in memory until `store.py`.)
- [ ] Submit the `koe_alert` template to Meta (blocked: business verification).
- [ ] WhatsApp latency stages logged.
**Done when:** a voice note books a meeting in about 3–4 s end to end; a failing CI run on the test repo triggers a WhatsApp alert.

## Phase 6: shared memory
- [ ] Context builder: today's activity summary + last WhatsApp turns, injected into every new Live session and WhatsApp turn.
- [ ] End-of-day roll-up into `daily_notes`.
**Done when:** on the web call, "what did I do on WhatsApp today?" is answered correctly.

## Phase 7: evals, deploy, ship
- [ ] `evals/cases.yaml`: about 40 requests (normal + tricky: clashes, "next Tuesday", timezones, ambiguous names, PR questions) against the test calendar and test repo.
- [ ] `evals/run.py`: tool-choice accuracy, argument correctness, end-state checks, latency → `evals/report.md` + chart.
- [ ] Deploy: Azure for Students VM (uvicorn + systemd + Caddy), Vercel frontend, update webhook URLs.
- [ ] README: problem, demo GIF/video, architecture diagram, metrics, setup, limits.
- [ ] Demo video (the `brag` skill can help).
**Done when:** all SPEC §10 acceptance criteria are checked.

## Buffer and v2 ideas (not this month)
Gmail triage · team mode · WebRTC/Pipecat transport if latency demands it · voice-note replies on WhatsApp · weekly report · Linear/Jira.
