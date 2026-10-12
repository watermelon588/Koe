# Plan and timeline: Koe (声)

**Total:** about 4 weeks at 3–5 h/day (about 80–100 h). Start date: the first build session.
**Difficulty:** about 7/10. Hardest parts: real-time audio streaming and barge-in, time/timezone correctness, Google OAuth quirks, Meta setup.
**Rule:** every phase ends with a working, demoable slice, verified, logged in BUILD_LOG.md, and committed.

> **Current phase: Phase 1 (started 2026-10-12).** Phase 0 done 2026-10-12, except Google OAuth (carried over, needed before Phase 2). Update this line as you go.

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
- [ ] Frontend: mic permission → `AudioWorklet` → 16 kHz PCM16 chunks → `/ws/call`.
- [ ] Backend: `/ws/call` ⇄ Gemini Live session (system prompt only); relay audio both ways.
- [ ] Frontend playback: queue 24 kHz PCM chunks → speaker without gaps.
- [ ] Barge-in: on Gemini "interrupted", flush the playback queue.
- [ ] Latency: timestamp speech-end and first-audio-out; print p50/p95 per call.
- [ ] Session resumption when Gemini sends a GoAway.
**Done when:** a 3-minute natural conversation, interruptions work, p50 latency measured and written in BUILD_LOG.
**Risk:** audio format bugs (sample rate, endianness) cause chipmunk or static sound. Test with a known sine wave first.

## Phase 2: agent core + GitHub read + Calendar
- [ ] `agent.py`: tool registry (schema + `needs_approval`), system prompt (persona, timezone, working hours, rules).
- [ ] `store.py`: SQLite tables (ARCHITECTURE §6).
- [ ] Tools: `github_review_queue`, `github_my_prs`, `calendar_list`, `calendar_find_free`, `calendar_upsert_event`.
- [ ] Approval gate: write → pending → spoken confirm → execute. Tests prove no bypass.
- [ ] Double-booking re-check + timezone tests.
- [ ] Text-mode agent loop (used later by WhatsApp + evals) and a tiny CLI to chat in text.
**Done when:** by voice, "what's waiting for my review?" is correct and "book 30 min with Rahul at 7" books after you say yes.

## Phase 3: dashboard + mascot
- [ ] Decide the mascot design and name with the user (SPEC §6).
- [ ] `/ws/events` + `events.py` pub/sub; every tool call, approval and alert emits an event.
- [ ] Panels: Today (Calendar), GitHub (review queue, my PRs + CI), Activity (with Approve/Reject), Latency.
- [ ] Mascot states: idle / listening / thinking / speaking / happy / error, driven by events + `AnalyserNode`.
- [ ] Access token on `/ws/*` (ARCHITECTURE §9).
**Done when:** while talking, the panels update live and the mascot reacts in sync.

## Phase 4: deeper GitHub + Notion + Sheets
- [ ] `github_pr_summary` (diff truncation, risk notes), `github_shipped`, `github_comment` (approval).
- [ ] `notion_log` (daily page in the "Koe Daily Log" database), `sheets_log_hours` (approval).
- [ ] Confirm with the user whether Sheets is still wanted (SPEC open Q5).
**Done when:** "What did I ship today?" gives a correct list and writes the Notion log; "Summarize #42" is accurate on a real PR.

## Phase 5: WhatsApp + GitHub alerts
- [ ] `/webhooks/whatsapp`: GET verify, POST signature check, 200 fast, background processing, sender allow-list.
- [ ] Voice note: media download → Gemini with audio → agent core (text loop) → reply.
- [ ] Interactive Confirm/Cancel buttons → resolve pending actions.
- [ ] `/webhooks/github`: signature, dedupe, 4 alert rules (SPEC §4) → WhatsApp; submit the `koe_alert` template to Meta.
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
