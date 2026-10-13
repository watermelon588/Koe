# Plan and timeline: Koe (声)

**Total:** about 4 weeks at 3–5 h/day (about 80–100 h). Start date: the first build session.
**Difficulty:** about 7/10. Hardest parts: real-time audio streaming and barge-in, time/timezone correctness, Google OAuth quirks, Meta setup.
**Rule:** every phase ends with a working, demoable slice, verified, logged in BUILD_LOG.md, and committed.

> **Current phase: Phase 2 storage migrated and verified live (2026-10-13).** Neon Singapore schema and adapter pass live approval/concurrency checks. Calendar tools, approval flow and text CLI are implemented. Google OAuth is still missing; complete consent and verify one intended approved booking before marking Phase 2 done. See [PHASE2_SETUP.md](PHASE2_SETUP.md). Phase 1 measured p50 ≈ 1.7 s, above the 1.5 s target.

> **Next slice built: Phase 3 live dashboard (2026-10-12).** At the user's request, implementation continued while credentials are deferred. Authenticated events, real read panels, activity, original-call approval controls and measured latency display are implemented. Local tests and isolated browser fixtures verify the wiring; real account data and an approved booking still await Phase 2 setup.

> **Phase 5b: Koe app built (2026-10-13).** Rohit has no business to verify with Meta, so the phone channel is Koe's own installable web app: chat with text and voice notes both ways, Confirm/Cancel approvals, push notifications for replies and GitHub alerts. WhatsApp code stays for later.

> **Phase 5 conversation built (2026-10-13).** WhatsApp text and voice notes run through the shared text agent and get replies; proposals carry Confirm/Cancel buttons; latency stages are logged. Verified with a faked Meta API plus real Gemini (transcription and replies). Real sending still waits on Meta business verification.

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
- [x] `store.py`: Neon psycopg adapter and PostgreSQL migration with restricted atomic approval functions (replaces SQLite by user request).
- [x] Tools: `github_review_queue`, `github_my_prs`, `calendar_list`, `calendar_find_free`, `calendar_upsert_event` wired to the registry; Calendar awaits real OAuth setup.
- [x] Approval gate: persisted proposal → explicit spoken/typed/UI confirmation → atomic claim → execute. Safety tests cover expiry, rejection, ambiguity, replay and storage errors.
- [x] Double-booking re-check + timezone, all-day event, pagination and event-move tests.
- [x] Text-mode agent loop and `python -m scripts.chat` CLI.
- [x] Neon migration/connection string verified live, including simultaneous claims and owner/conversation isolation.
- [ ] Live verification: Google consent, voice GitHub read and one approved booking on a test calendar.
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
- [x] `/webhooks/whatsapp`: GET verify, POST signature check, 200 fast, background processing, sender allow-list, one message at a time per sender.
- [x] Voice note: media download → Gemini transcription → agent core (text loop) → reply. Text messages use the same path; per-sender history (in memory).
- [x] Interactive Confirm/Cancel buttons → resolve pending actions (button id `approve:<id>` / `reject:<id>` → `agent.confirm`).
- [x] `/webhooks/github`: signature, dedupe, 4 alert rules (SPEC §4) → WhatsApp. (Real sends blocked by Meta, see SERVICES_AND_COSTS; dedupe is in memory until `store.py`.)
- [ ] Submit the `koe_alert` template to Meta (blocked: business verification).
- [x] WhatsApp latency stages logged (`received → media_downloaded → transcribed → model_done → reply_sent`, ms, to the log and activity store).
**Done when:** a voice note books a meeting in about 3–4 s end to end; a failing CI run on the test repo triggers a WhatsApp alert.

## Phase 5b: Koe app (installable, push notifications)
- [x] Installable web app: manifest, icons from the mascot, service worker, Install app button (iPhone: Add to Home Screen instructions).
- [x] Chat page: text + recorded voice notes; Koe replies to voice with voice; persisted history; Confirm/Cancel approvals; typing indicator.
- [x] `/api/app` backend: token-protected messages, voice upload/download, approvals, push subscription; SQLite history.
- [x] Web Push (VAPID) for Koe's replies and GitHub alerts; skipped while the chat is on screen.
- [ ] Live check on Rohit's phone over the cloudflared tunnel: install, enable notifications, send a voice note, receive a pushed reply.
**Done when:** with the app closed, a GitHub alert and a Koe reply arrive as phone notifications, and a voice note gets a spoken answer.

## Phase 5c: accounts, connections and guides (spec: [ACCOUNTS_SPEC.md](ACCOUNTS_SPEC.md))
Goal: an invited friend goes from link to working assistant without touching code. One vertical slice per task; checkpoint with Rohit after each group.

**Group 1: public pages (no login)**
- [x] 1. Path-routed public pages `/guide`, `/privacy`, `/terms` with a shared footer; Vercel SPA fallback. *Accept:* each loads signed-out at 375/1280 px, links work, content matches real data handling. *Verify:* tsc, lint, tests, browser check.
- **Checkpoint:** Rohit reads Guide/Privacy/Terms; links usable as the Google/Meta/Notion privacy-policy URL.

**Group 2: identity**
- [x] 2. *(backend done 2026-10-13: migration 003, `auth.py`, `db.py`, 11 tests; Google accepts the client)* Migration `003_accounts.sql` (users, invites, sessions) + `auth.py`: Google sign-in (PKCE/state/nonce, ID-token checks), allow-list, session cookie, logout, `current_user` dependency. *Accept:* invited → session; uninvited → no session; tests for each, with Google faked. *Needs Rohit:* a Google **Web** OAuth client + `KOE_SECRET_KEY`, `KOE_ADMIN_EMAIL`.
- [x] 3. *(done 2026-10-13)* Vercel rewrites `/api` + `/auth` → Render with `no-store`; frontend sign-in screen and logout; HTTP APIs accept the session (token still accepted in single-owner mode). *Accept:* sign in on the phone, chat works with no token typed.
- [x] 4. *(done 2026-10-13; friends are kept out until task 6)* WebSocket tickets (`POST /api/ws-ticket`, single use, 60 s, Origin check) for `/ws/call` and `/ws/events`; remove token UI from Home/Settings/Install. *Accept:* a call works signed-in; a reused ticket is refused.
- **Checkpoint:** end-to-end sign-in on laptop and phone; Rohit invites one friend.

**Group 3: per-user data**
- [ ] 5. *(storage done 2026-10-13; per-user conversation memory and approvals follow task 2)* App chat (messages, voice notes, push subscriptions) moves from SQLite to Neon with `owner_id` = user; conversations and pending approvals keyed by user. *Accept:* user B sees none of user A's chat/activity/approvals (tests); survives a Render restart.

**Group 4: connections**
- [x] 6. *(done 2026-10-13)* `connections.py` + encrypted token store + Settings → Connections list (connect / disconnect / status). Google Calendar connect; calendar tools use the caller's token. *Accept:* "what's on my calendar today?" uses the caller's calendar.
- [ ] 7. *(Sheets access comes with the Google connection; the "Create my Hours sheet" button is still to do)* Google Sheets: same consent; "Create my Hours sheet" button. *Accept:* sheet created with headers; a timesheet row needs approval.
- [ ] 8. GitHub OAuth App connect + repo picker; GitHub tools use the caller's token. *Needs Rohit:* GitHub OAuth App.
- [ ] 9. Notion public integration connect + "Create Koe Daily Log". *Needs Rohit:* Notion public integration (uses the privacy/terms URLs from task 1).
- **Checkpoint:** a friend connects all four from Settings with no code changes.

**Group 5: quota and admin**
- [ ] 10. Daily turn cap on the shared Gemini key + optional own key (encrypted). *Accept:* the cap message appears at the limit; an own key removes it.
- [ ] 11. Owner's Settings → People: invite/remove emails. *Accept:* an invited email can sign in, a removed one is signed out.

## Phase 6: shared memory
- [ ] Context builder: today's activity summary + last WhatsApp turns, injected into every new Live session and WhatsApp turn.
- [ ] End-of-day roll-up into `daily_notes`.
**Done when:** on the web call, "what did I do on WhatsApp today?" is answered correctly.

## Phase 7: evals, deploy, ship
- [ ] `evals/cases.yaml`: about 40 requests (normal + tricky: clashes, "next Tuesday", timezones, ambiguous names, PR questions) against the test calendar and test repo.
- [ ] `evals/run.py`: tool-choice accuracy, argument correctness, end-state checks, latency → `evals/report.md` + chart.
- [ ] Replace development token entry with owner-only provider sign-in and secure sessions across HTTP and WebSockets; verify expiry, logout and rejection of other accounts (AUTH_FLOW.md).
- [x] Temporary hosting: backend on Render free (`render.yaml`), frontend on Vercel (DEPLOY.md). Webhooks get stable URLs.
- [ ] Move the app chat (messages, voice notes, push subscriptions) from SQLite to Neon, so it survives Render's disk wipes.
- [ ] Deploy: Azure for Students VM (uvicorn + systemd + Caddy), Vercel frontend, update webhook URLs.
- [ ] README: problem, demo GIF/video, architecture diagram, metrics, setup, limits.
- [ ] Demo video (the `brag` skill can help).
**Done when:** all SPEC §10 acceptance criteria are checked.

## Buffer and v2 ideas (not this month)
Gmail triage · team mode · WebRTC/Pipecat transport if latency demands it · voice-note replies on WhatsApp · weekly report · Linear/Jira.
