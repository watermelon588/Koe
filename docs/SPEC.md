# Spec: Koe (声)

## Connection and GitHub scope repair — 2026-10-18
Connections must distinguish unavailable backend support, missing provider setup, and a connected account. A frontend against a pre-Docs backend must not offer a consent loop. Docs readiness is based on returned granted scopes, with explicit callback feedback and uncached refresh. Show the owner's existing GitHub/Notion server connections truthfully. GitHub users can connect their own account through OAuth or a validated personal token entered in Settings, stored encrypted only on the backend. They can choose specific repositories or all repositories accessible to that credential; apply that choice to every GitHub repository tool. Account-wide reads are bounded and disclose incomplete coverage. Never report unavailable or unselected repositories as zero activity. Resolve the actual GitHub identity for legacy server tokens, inspect branch history with SHA deduplication, and disclose any missing branches. Provide the agent a read-only connection-status tool. Preserve unrelated design work and existing approval gates.

## Google Docs integration — 2026-10-18
Use the existing per-person Google OAuth connection, with an explicit optional Docs consent upgrade (documents + drive.file). Existing Calendar/Sheets grants remain usable. Docs supports bounded app-accessible document discovery through Drive, reading any user-accessible Doc by exact link/ID, approved creation with plain text, appending and exact single-passage replacement in a selected tab. No standalone Drive manager, sharing, deletion or arbitrary batch API is exposed. All writes use the shared persisted approval gate. Edits freeze the read revision and tab and send requiredRevisionId to Google; stale changes must be reread and proposed again. Never retry uncertain writes. If creation succeeds but content insertion fails, return the created document link with an explicit partial failure. Tokens stay encrypted server-side; caller identity and Google account are checked again at execution. Read data is untrusted and bounded. Chat and live calls share tools and the existing workspace/approval UI, with original Docs artwork. Docs list covers files accessible through drive.file, not the user's entire Drive; a pasted Docs link supports other documents via documents permission. Setup, limitations and verification live in GOOGLE_DOCS.md.

> **Status:** v0.1, 2026-10-12. This file is the contract. Change it before changing behavior, and log the change in [DECISIONS.md](DECISIONS.md).

## 1. Objective

Production Spotify setup diagnostics (2026-10-17): the existing owner-only backend status reports configuration presence and enablement as booleans, including Spotify credentials, callback, encryption readiness and approved voice flag. It never returns secret values. Music's example artist is keshi.

A single-user, voice-first agent for a developer founder. It works across GitHub, Google Calendar, Notion and Google Sheets, through two channels: a **live web voice call with a mascot** and **WhatsApp**. Every write that affects others or the calendar waits for the user's approval. Accuracy and latency are measured.

### Backend reliability pass (2026-10-13; UI frozen)

- Exhausted transient Gemini errors (429/500/503/504 and transport failures) can reach the configured free text fallback only before any tool executes. Bound the Gemini generation chain as well as individual attempts; never restart or replay a tool turn. Invalid credentials/arguments are not treated as overload.
- Voice-note retries discard incomplete audio from the failed attempt before recording a replacement.
- Background best-effort audit writes have a bounded backlog and a shutdown drain. Durable proposal/claim/finish writes remain synchronous and are never retried automatically.
- Preserve `/health`'s existing body; expose a validated deployment revision header and authenticated owner-only configuration-presence diagnostics. Never expose secrets, user records, token prefixes or provider exception bodies. Deployment checks are read-only unless separately authorized.
- Frontend/UI files remain unchanged. No extra paid service or runtime dependency is introduced.

### User stories

Schema/row editing phase (2026-10-14): [SCHEMA_ROW_EDIT_PLAN.md](SCHEMA_ROW_EDIT_PLAN.md) defines approved optional column/property creation and existing Sheets row editing. Stable IDs, typed snapshots, exact previews, stale checks and bounded scans are enforced by Python. External-editor races are documented honestly; no remote compare-and-set is claimed. UI and hosting stay unchanged.

Integration expansion (2026-10-13): [DETERMINISTIC_FEATURES.md](DETERMINISTIC_FEATURES.md) defines the implementation order and acceptance contract for exact GitHub history/statistics/streaks, Calendar details/reminders and typed optional Sheets/Notion fields. Python validates and executes; the LLM chooses tools and explains evidence. The UI remains frozen. Queued features are not advertised as implemented.

Calendar follow-up (2026-10-14): [CALENDAR_EXTENSIONS.md](CALENDAR_EXTENSIONS.md) defines bounded daily/weekly and all-day creation, unique asynchronous Meet requests, versioned event reads, explicit single/instance/whole-series cancellation and exact approvals. External invitation tests remain synthetic. The frontend integration contract is [FRONTEND_BACKEND_HANDOFF.md](FRONTEND_BACKEND_HANDOFF.md).

1. *At my desk*, I click **Call** and ask "What's my day?". Koe speaks a summary of today's meetings, PRs waiting on me, and my open PRs' CI status, while the dashboard highlights each item.
2. *At my desk*, I say "Summarize PR #42, is it risky?" and get a spoken summary with the main risk.
3. *Walking*, I send a WhatsApp voice note: "Am I free at 7? Book a call with Rahul." Koe replies with the slot and **Confirm / Cancel** buttons; I tap Confirm and it's booked.
4. *Anytime*, when CI fails on my PR or someone requests my review, I get a WhatsApp alert.
5. *Evening*, I ask "What did I ship today?". Koe lists merged PRs and commits, writes the Notion daily log, and (after I approve the hours) adds a Sheets timesheet row.
6. *Next morning on the web call*, Koe knows what I did on WhatsApp yesterday (shared memory).

## 2. Channels
| Channel | Direction | Transport | Model |
|---|---|---|---|
| **Web call** | User ⇄ Koe, live audio | Browser ⇄ FastAPI over WebSocket (`/ws/call`), PCM16 audio (see wire format below) | Gemini Live native-audio model (speech-to-speech, tool calling) |
| **Dashboard events** | Koe → browser | WebSocket (`/ws/events`), JSON | — |
| **Koe app** (installable web app on the phone) | User ⇄ Koe | `/api/app/*` (HTTPS, access token): text and WAV voice notes in; replies stored in `backend/data/app.db` | Gemini (transcription + text agent); Koe's voice replies via Gemini Live |
| **Push notifications** | Koe → phone | Web Push (VAPID, `pywebpush`) to the installed app's service worker: Koe's replies and GitHub alerts | — |
| **WhatsApp in** | User → Koe | Meta webhook `POST /webhooks/whatsapp` (text, audio, button replies) | Gemini (standard) with audio input |
| **WhatsApp out** | Koe → User | Meta Send API (text, interactive buttons, templates for alerts) | — |
| **GitHub events** | GitHub → Koe | Webhook `POST /webhooks/github` (HMAC-SHA256 verified) | none (rules decide what to alert) |

### `/ws/call` wire format (implemented, Phase 1)
- **Browser → backend, binary:** raw PCM16, **16 kHz**, mono, little-endian, ~40 ms per frame (640 samples). Text frames carry chat, authentication and explicit approval control below.
- **Backend → browser, binary frames:** Koe's voice. Raw PCM16, **24 kHz**, mono, little-endian, any length. Play back-to-back.
- **Backend → browser, text frames:** JSON control events:
  | Event | Meaning | Browser should |
  |---|---|---|
  | `{"type":"interrupted"}` | User talked over Koe (barge-in) | Stop and drop all queued audio at once |
  | `{"type":"latency","ms":1650}` | This turn's "you stopped speaking → Koe's first audio", measured at the backend | Show it (latency readout) |
  | `{"type":"tool","name":"github_my_prs","phase":"start"}` | Koe started a tool | Show "thinking" (mascot state, panel highlight) |
  | `{"type":"tool","name":"github_my_prs","phase":"end","ms":640,"ok":true}` | Tool finished (`ok:false` = it returned an error) | Back to speaking / show error |
  | `{"type":"transcript","role":"user"|"koe","text":"…"}` | A piece of what was said (Gemini Live audio transcription, both directions); pieces arrive in order | Append to the current chat line of that speaker |
  | `{"type":"turn_complete"}` | Koe finished its reply | Close the current chat line |
- **Browser → backend, text frames:** `{"type":"text","text":"…"}` = a typed chat message, sent into the same Live session (`send_realtime_input(text=…)`); trimmed, capped at 2000 characters; anything malformed is ignored, never fatal.
- **Phase 2 authentication:** when `KOE_ACCESS_TOKEN` is configured, the first browser frame must be `{"type":"auth","token":"…"}` within 10 seconds. Neon-enabled browser calls require this app token. Close code `1008` indicates missing/invalid authentication. The token never goes in the URL; Neon secrets never go in the browser.
- **Phase 2 approval:** backend sends `{"type":"approval_pending","id":"UUID","summary":"…","expires_ts":"…"}`. Browser may reply `{"type":"approval","action_id":"UUID","approve":true|false}`. Backend sends `approval_result` with authoritative `status`/`error` and any remaining `pending_action`. A complete, explicit spoken/typed yes or no also resolves the original conversation's proposal; model/tool text cannot authorize it.
- **Close codes:** normal hang-up = 1000. `1011` with a `reason` such as `"Gemini error: …"` = the call failed; show the reason.
- Unknown event types must be ignored (more come in Phase 3: dashboard events on `/ws/events`).

### Live workspace: watch Calendar, Sheets and Notion work (2026-10-13, replaces "Calendar and Sheets work during calls")
- **What:** one `LiveWorkspace` panel (`frontend/src/workspace/`) shows what Koe read, proposed or wrote in Google Calendar, Google Sheets or Notion, so "did it really save?" has one visible answer. The **app chat** shows it as a right side panel (≥900px; the chat moves left to make room) or a bottom sheet (phones), opened automatically by a turn that touched one of those services, closable, reopened from the chat header. A **call** shows it inline as the call panel's *Workspace* tab (it replaces the Calendar/Sheets tabs), opened automatically by the call's own tool events. Motion is GSAP: transform/opacity only, none under `prefers-reduced-motion`.
- **States per service:** checking → proposal (*waiting*: the exact event/row/record, marked pending; nothing is saved) → *saving* (decision being checked) → *saved* (only after an executed approval result, or a successful own daily-log append) with a receipt of exact identifiers (Calendar: title, date, time range, time zone, event link; Sheets: row, range, tab; Notion: page title, type, link) and an **Open in …** link; or *cancelled* / *needs attention* with the provider's error and hint. A saved Notion record is re-read from `GET /api/notion/records/{id}`.
- **Decisions:** the panel's Confirm/Cancel call the existing controls only (chat: `POST /api/app/approvals/{id}`, the same as the bubble; call: the `/ws/call` `approval` frame). They show only when that surface can decide that action ID. No new approval path (§5).
- **Live view (optional toggle, lazy):** the real provider page in a sandboxed iframe, only for URL forms verified frameable (DECISIONS.md 2026-10-13): Sheets `…/spreadsheets/d/{id}/edit?rm=minimal`, Calendar `…/calendar/embed?src={account}&ctz=…&mode=WEEK` (account from `GET /api/connections`). It shows data only if the browser is signed in to Google and allows Google's cookies inside other sites; otherwise Google shows sign-in or nothing, and Koe's view plus Open stay available. Notion refuses framing (`X-Frame-Options: SAMEORIGIN`), so Notion has Koe's view only. A new proposal or failure always shows Koe's view (the pending item, or the error and hint); a saved receipt shows above the live view too. Never a token in a URL.
- **Chat data path:** `POST /api/app/messages`, `POST /api/app/voice` and `POST /api/app/approvals/{id}` return `workspace`: a list of events in the `/ws/call` shape (`tool` start/end with `operation_id`, `approval_pending`, `approval_result` with `status`), each with a `work` projection from `koe/call_work.py`. `GET /api/app/messages?after=0` returns the open proposal again after a reload (the panel stays closed until opened). Owner-scoped (each person's own chat); a typed yes/no also marks the proposal bubble's status. Not persisted: after a restart only the open proposal (if still in memory) comes back.

Earlier contract, still true inside the workspace:
- The call opens the workspace when that call actually invokes a Calendar/Sheets/Notion tool. Chat/Day remain accessible; each service keeps its latest work for this call. No keyword guessing or simulated task progress.
- Calendar shows returned events/free windows on a day timeline, the proposed booking as pending, and the confirmed booking only after an executed approval result. Show date/timezone, attendees and authoritative errors/conflicts. Sheets shows the exact proposed hours row and destination, then the confirmed row number/range and provider link. Existing tools and approval rules remain unchanged.
- Google tool events carry `operation_id` and a bounded `work` display projection. Approval pending/progress/result carry the original stored proposal's display projection and action ID. No OAuth tokens, credentials or arbitrary execution payloads are sent. Google links are HTTPS and host-validated.
- Confirm/Cancel still use the call action-ID control or explicit spoken yes/no. Pending slots/rows never appear saved. Saving means a decision is being checked. Errors explain uncertain outcomes. Panels clear on a new call and never trigger additional Google operations themselves.
- Desktop keeps the mascot alongside the work window; mobile uses the call sheet. Respect reduced motion and retain transcript, composer, mute/end and approval controls. Verify synthetic WebSocket sequences and browser layout; do not book real meetings or append real rows for UI testing.

**Allowed WhatsApp senders:** only numbers in `ALLOWED_WHATSAPP_NUMBERS` (env). Everything else is ignored and logged.

### `/ws/events` dashboard protocol (Phase 3)
- The first frame is `{"type":"auth","token":"…"}` within 10 seconds. `KOE_ACCESS_TOKEN` is required even without Neon. No dashboard data or external reads happen before authentication; invalid/missing tokens close with `1008`.
- Backend sends a `snapshot` with today's Calendar, review queue, open PRs, recent activity, pending approvals and measured turn latencies. Incremental events are `panel`, `tool`, `approval_pending`, `approval_progress`, `approval_result`, `alert` and `latency`; each carries an ID, timestamp and optional original session/channel.
- Browser may send `{"type":"refresh"}` for a read-only refresh. Refreshes are coalesced and limited to once per 30 seconds across clients, with a 60-second automatic refresh while connected. Missing services show explicit setup errors; there is no sample data fallback. Panels show their last update and become stale on disconnection.
- This single-process, single-owner stream uses bounded client queues. Slow clients receive a fresh snapshot instead of blocking audio/tool work. Restart/reconnect reloads recent saved activity and pending proposals from Neon when configured; read panels are fetched again. No Redis or new dependency is needed.
- Dashboard approvals are informational outside their original conversation. Approve/Reject in the live call's dashboard view sends the existing `/ws/call` action-ID control; the events socket cannot authorize writes or approve another conversation's proposal. Expired cards are disabled locally and remain subject to the database expiry check.
- During calls a Day/Chat switch keeps the dashboard accessible alongside the current call controls. The existing audio-driven mascot states remain on `/ws/call`; dashboard alerts can trigger a brief reaction only when idle.

## 3. Tools (the agent's whole surface: 13 tools)
### Confirmation repair (2026-10-16, findings slice S1)
- Recognize only complete, allowlisted affirmative/negative utterances of at most four words. Normalize case, whitespace, punctuation and curly apostrophes; support common English and Hindi responses. Conditional, mixed and embedded replies never authorize a write.
- During a call, the exact proposal becomes eligible after its `approval_pending` card is sent. Bind a spoken utterance to the proposal visible when its first transcript chunk arrives; a response started before the card or for an earlier proposal cannot approve a later action. Wait for the complete input transcript (`finished`, with model `turn_complete` as fallback), never a partial “yes”.
- Resolve through the existing conversation/action-ID gate and atomic store claim. Send the authoritative result to the model. If a completed response to a visible proposal is unclear, tell the model no approval was recorded and ask for a clear yes or the Confirm button; requested edits need clarification and their own proposal.
- This slice changes no tools, credentials, database schema or hosting. Synthetic transport tests prove behavior; real microphone/transcription acceptance remains a separate check.

All tools live in one registry and are shared by both channels. Each tool returns JSON. On failure it returns `{"error": {"code", "message", "hint"}}` instead of raising, so the model can recover.

### Approval and Activity presentation (2026-10-16, findings slice S2)
- Add an optional deterministic `display` block (`title`, up to four bounded plain-text `lines`, optional validated HTTPS provider `url`) to public proposals and approval outcomes. Derive it from the stored normalized action; it is presentation only and never execution input. Preserve the complete authoritative `summary` for audit/model use and a keyboard-accessible Details disclosure.
- Reuse the preview on the call, dashboard, app chat and Notion approval card. Saved dashboard/chat proposals regain their previews from owner-scoped stored actions after reload; execution arguments and private payloads never leave the backend. Older responses without `display` remain reviewable via the existing full summary.
- Activity shows concise operation/outcome text with an Open link, keeps errors visible, groups entries under Today/Yesterday/local dates, and formats timestamps as nonwrapping 24-hour time. No new dependency, migration, tool, external write or approval path.

| # | Tool | Args | Returns | Write? |
|---|---|---|---|---|
| 1 | `github_review_queue` | `repo?` | PRs where my review is requested: number, title, author, age, size | read |
| 2 | `github_my_prs` | `state="open"` | My PRs with CI status, review state, mergeable/conflicts, last update | read |
| 3 | `github_pr_summary` | `repo, number` | Description + changed files + diff (truncated) → `{summary, files_changed, risk_notes}` | read |
| 4 | `github_shipped` | `since` (ISO or "today"/"this week") | Merged PRs + commits by me across configured repos | read |
| 5 | `github_comment` | `repo, number, body` | Comment URL | **write: approval** |
| 6 | `calendar_find_free` | `date, duration_min, between?` | Free slots inside working hours | read |
| 7 | `calendar_upsert_event` | `title, start, end, attendees?, event_id?` (create or move) | Event link | **write: approval** |
| 8 | `notion_log` | `date, entries[]` | Notion page URL (daily dev log) | write (low-risk: own log, no approval) |
| 9 | `sheets_log_hours` | `date, client, hours, note` | Row number | **write: approval** |
| 10 | `calendar_list` | `date` | Events for the date | read |
| 11 | `notion_read` | `query?, kind?, cursor?, page_id?` | Scoped records or bounded page preview | read |
| 12 | `notion_save` | `title, date, kind?, status?, body?, end?, page_id?, expected_edited?` | Task/note/meeting record | **write: approval** |
| 13 | `notion_archive` | `page_id, expected_edited, title` | Reversible Notion trash | **write: approval** |

Also in scope: `calendar_list(date)`, a read tool. The user authorized the Notion workspace expansion on 2026-10-13: `notion_read`, `notion_save` and `notion_archive` extend the registry to 13 tools. See NOTION_PLAN.md. Notion saves tasks/notes/meeting records; Calendar remains the booking authority. Save/archive mutations require explicit approval; the existing own-daily-log exception remains append-only.

Rules baked into the tools (not left to the model):
- **Timezone:** every time is resolved in `Asia/Kolkata` unless the user says otherwise. Tools take and return ISO-8601 with offset.
- **No double-booking:** `calendar_upsert_event` re-checks free/busy right before writing and refuses on conflict.
- **Working hours** (configurable, default 09:00–21:00) bound `calendar_find_free`.
- **Repos:** GitHub tools work on `GITHUB_REPOS` (env list) plus PRs involving the user.
- **Diff limit:** `github_pr_summary` sends at most about 30 KB of diff to the model, and says when it truncated.
- **No merge tool exists.** The agent can't merge PRs.

## 4. Push alerts (GitHub → WhatsApp)
Handled by rules, not the LLM, for speed and zero cost:
| GitHub event | Condition | WhatsApp alert |
|---|---|---|
| `workflow_run` completed | conclusion = failure, on a PR, run triggered by me (Actions sends `check_suite` for the same failure too, so it isn't used: no double alerts) | 🔴 CI failed on #N (repo): failing check name |
| `pull_request` review_requested | requested reviewer = me | 👀 X requested your review on #N |
| `pull_request` closed + merged | author = me | ✅ #N merged |
| `pull_request_review` submitted | on my PR, state = changes_requested | ✏️ Changes requested on #N by X |

Alerts outside the 24-hour WhatsApp window use one approved **template** (`koe_alert`). Duplicate deliveries (same `X-GitHub-Delivery` ID) are ignored.

## 5. Approval gate (human in the loop)
- Tools marked **write: approval** never execute directly. The agent core creates a **pending action** (stored in Neon PostgreSQL) and asks:
  - **Web call:** Koe asks out loud ("Book 7:00–7:30 with Rahul. Shall I?"). A spoken yes or no resolves it, and the dashboard shows Approve/Reject buttons too.
  - **WhatsApp:** an interactive message with **Confirm / Cancel** buttons.
- Pending actions expire after 10 minutes.
- A restricted SQL function atomically claims the action before external execution. Only its owner and original conversation may resolve it. Claim/result-recording uncertainty never triggers an automatic write retry. The backend is still a single-user application; Provider login is a separate UI/auth slice.
- Every action (proposed, approved, rejected, executed, failed) goes to the activity log and the dashboard.

## 6. Mascot
- A chibi, anime-styled **3D VRM model** rendered with three.js + `@pixiv/three-vrm`, made in **VRoid Studio** (free, commercial use allowed). No paid assets. Rohit's own VRoid models are in use (pixiv's sample model is retired). How to build one: [MASCOT_GUIDE.md](MASCOT_GUIDE.md).
- **Latency rule:** the mascot must never delay the call. It loads in its own code chunk after the page, renders at ≤ 30 fps, pauses when the tab is hidden, and its main-thread cost is measured (BUILD_LOG "Step 13: 3D mascot spike" and Step 17).
- **States** (implemented, driven by `/ws/call` events, see §2; all motion is code, no animation files):
  | State | Trigger | Face | Motion |
  |---|---|---|---|
  | `idle` | no call | neutral | breathing, sway, blinking |
  | `listening` | call connected | `relaxed` 0.15 | head tilt toward the viewer, small nods |
  | `thinking` | `tool` start | neutral | head turns, eyes glance up and away |
  | `speaking` | Koe's audio | `aa` from output loudness (`AnalyserNode`) | lip sync, layered on any state |
  | `happy` (2.5 s) | `tool` end, `ok:true` | `happy` 0.7 | small hop, head tilt |
  | `sad` (2.5 s; 4 s on a failed call) | `tool` end `ok:false`, or close with a reason | `sad` 0.6 | head dips |
- **Animation files (`.vrma`)** are optional extras, not built yet. pixiv's free pack forbids redistributing the motions "in a way that can be extracted", which a public site would do, so they'd be local-only unless pixiv permits it.
- **Design:** two models ship, and the user picks one: **`kami` (default)** and `miku` (switch in the header, `?model=` in the URL). `akane` and the pixiv sample are retired (kept in `frontend/assets/mascot/`, not served). Name her before launch.
- **Shots:** `shot("bust" | "full", x)`. Home = half figure: hair to waist, and she stands behind a **desk card** that covers the bottom 24% of the stage (`DESK` in mascot.ts = `--desk-h` in CSS), so the screen edge never cuts her; the desk shows her name, status and a Say hi button. During a call = full figure, head to toe, and the desk slides away. `x` places her on screen (0 left … 1 right) with a camera view offset, so she is never centred on wide screens and the canvas never resizes mid-animation. Moves ease in-out over 0.9 s.
- **Alive, not posed (implemented):** relaxed fingers, slight elbow bend, arm sway, breathing, blinking; every 6 to 12 s an idle routine (look around, fix her hair, tilt her head, shift her weight, stretch, plus every VRoid pose in `src/mascot/poses/`; during a call only the quiet ones, never while she talks). Eyes and a little of the head follow the pointer anywhere on the page. **Touch zones** (raycast on tap only): hair → she fixes it, face → startled then smiles, hands → waves back, body → smiles and tilts her head. A sideways drag turns her (±0.9 rad) and she springs back. She waves when a call connects. While a tool runs (thinking) she rests her hand on her chin. **VRoid poses:** `.vroidpose` files saved from VRoid Studio's Photo Booth are parsed (Unity quaternion → three.js: (x, −y, −z, w), thumb joints renamed to VRM 1.0) and held for 5 s as idle poses; the head stays app-driven.
- **UI:** one layout, **Engawa**: she stands on the left behind her desk; on the right the greeting, Call, a one-line Connect (hidden once the dashboard is live) and a **slim Today summary** (the next few events, review/approval counts) that links to the **Dashboard page** (`#dashboard`). The Dashboard is its own page: a grid of panels on desktop (Today, Approvals with Approve/Reject for the live call's proposal, Waiting for your review, Your pull requests, Activity with response-time p50/p95), stacked on phones; Home and Dashboard share one `/ws/events` connection held in `App`. The call's Day view keeps the compact four-tab card. A call raises a sheet on the right while she shows her full figure. Header: Home, Dashboard, Chat, Notion, Settings, a Guide (?) link and theme as Phosphor icon buttons. A footer on Home, Dashboard, Notion and Settings links Guide, Privacy, Terms and Install the app. Settings: the companion studio on top, then calm sections below it (Account, Connections with Timesheet and Repositories inside their service, Your Gemini key, This device), each a row with icon, name, one-line status and one action. Dark theme by default, light theme grey not white; flat backgrounds, light type, one accent per mascot. The call panel holds the live transcript (or the Day card), a text box (typed chat), mute and end. Don't ship the name "Miku": teal twin-tails + that name reads as Hatsune Miku (trademark).

## 7. Memory
- **Neon PostgreSQL**: `koe_activity` (actions/messages with channel and latency), `koe_pending_actions`, `koe_daily_notes`, `koe_github_deliveries`. Supported activity channels include web, CLI, WhatsApp, GitHub and the installed app. Backend-only access through `DATABASE_URL` and parameterized SQL; no database secrets in the browser. Atomic proposal/claim/finish functions preserve the existing approval contract. App chat history, push subscriptions and voice files remain local in this storage migration.
- At the start of every web call or WhatsApp turn, the agent gets a **short summary of today's activity across both channels**, plus the last few WhatsApp turns. This is what lets the channels share one memory.
- No vector database or long-term memory in v1.

## 8. Latency instrumentation
Every turn records timestamps, stored in `activity` and shown on the dashboard:
- **Web call:** `user_speech_end → first_audio_out` (headline metric), plus `tool_start/tool_end` for each tool.
- **WhatsApp:** `webhook_received → media_downloaded → transcribed → model_done (includes tools) → reply_sent`; a button tap logs `tools_done → reply_sent`.

## 9. Limits and safety
- Max call length is set by Gemini Live's free-tier session cap. Use session resumption to continue transparently.
- WhatsApp: process at most 1 message at a time per sender (queue the rest), and acknowledge webhooks within 1 s (return 200 immediately, process in the background).
- Validate every webhook: Meta (`X-Hub-Signature-256`) and GitHub (`X-Hub-Signature-256`, HMAC with the secret).
- Secrets live only in `.env` (git-ignored). `.env.example` lists the variable names.

## 10. Acceptance criteria (v1 done)
- [ ] Web call: natural conversation with the mascot. Barge-in works. p50 speech-end → first audio measured and shown.
- [ ] All 13 tools work by voice on the web and by supported text/voice-note channels; live provider/channel acceptance remains required.
- [ ] Approval gate: 0 write actions without approval, proven by tests.
- [ ] The 4 GitHub alert types arrive on WhatsApp.
- [ ] Shared memory: the web call can answer "what did I do on WhatsApp today?".
- [ ] Eval suite (about 40 scripted requests on a test calendar and test repo) reports booking accuracy, tool-choice accuracy and latency. The results are in the README.
- [ ] Deployed: backend on Azure for Students VM, frontend on Vercel. Works with the laptop off.
- [ ] README, architecture diagram, demo video.

## 11. Testing strategy
- `pytest` for backend logic: time and slot math, double-booking refusal, approval gate, webhook signature checks, GitHub-event → alert rules. External APIs are faked at the HTTP boundary (`respx` for `httpx`).
- **Eval suite** (`backend/evals/`): scripted natural-language requests run through the real agent core (text mode) against a **dedicated test Google Calendar and a test GitHub repo**. It scores the tool chosen, the arguments, and the end state.
- Manual checklist per phase, recorded in BUILD_LOG.md.

## 12. Boundaries
- **Always:** approval for write tools · validate webhook signatures · log every action · measure latency · update docs + BUILD_LOG.
- **Ask first:** new dependency · new tool · changing approval rules · messaging anyone other than the user · deploying.
- **Never:** merge PRs · commit secrets · message numbers outside the allow-list · use paid services or services that need a card.

## 13. Open questions
1. ~~Output style~~: **Explanatory** (decided 2026-10-12, see DECISIONS.md).
2. Mascot design and name: decide at the start of Phase 3.
3. ~~Gemini Live model ID~~: `gemini-3.8-live`, 15 min audio sessions (verified 2026-10-12, SERVICES_AND_COSTS.md). Free-tier RPM/RPD aren't published; check AI Studio.
4. Will Meta approve the `koe_alert` template quickly? If not, alerts only arrive inside the 24-hour window. Check in Phase 5.
5. Google Sheets is included; the user confirmed approval before every entry on 2026-10-13.

## Phase 4 implementation contract — 2026-10-13

- Add the five already planned tools: PR summary, shipped history, PR comment, Notion daily log and Sheets hours. No new dependencies. Missing credentials return setup errors.
- PR summaries send at most 30,000 UTF-8 bytes of source JSON to Gemini, with explicit coverage/truncation and inferred risk notes. PR content is untrusted; the summarizer has no tools. Check the head revision before summarizing.
- Shipped history covers configured repositories and the authenticated author's merged PRs plus default-branch commits. Today/week use the owner's timezone. Pagination limits and incomplete results are disclosed; commits and PRs can overlap. Never infer hours.
- Comments are restricted to configured repositories. Show the complete comment and target before approval. Sheets shows date, client, hours, complete note and configured destination before every approval. Store normalized arguments; execute only through the existing atomic claim. Never retry an uncertain external write automatically.
- Notion logs append bullets to one page per Date in the configured data source. Exact repeated entries are skipped; duplicate daily pages or incomplete reads fail closed. This own-log write follows the existing low-risk exception. Use one backend worker; Notion writes are not transactional with Neon.
- Sheets uses existing Google OAuth with additional Sheets consent. Require headers Date, Client, Hours, Note, Koe action ID in A1:E1. Append RAW values to avoid interpreting text as formulas. Bind proposals to the configured spreadsheet and tab; the internal action ID is an audit field.

## Frontend profile settings — 2026-10-12

Visual revision: Settings uses one viewport-adaptive companion studio, actual VRM portrait thumbnails, and controls overlaid on the viewer. Full-body framing automatically expands the same canvas to a large inspection pane. Inspection supports persistent 360-degree rotation and zoom. Vertical placement stays fixed; left/right arrows rotate and Home resets rotation. Keep only framing, expand/close, wave, turntable, zoom and explicit Choose controls; remove descriptive card copy and the separate expression/mood button groups. Expanded view supports Escape, focus containment and restoration. Home rendering and saved selection semantics remain unchanged.

The dedicated `#settings` page owns mascot selection: Kami, Miku, Aoi and Kobashi. Users preview one live VRM at a time, try gestures, expressions and call moods, and explicitly apply their choice. Browsing previews does not change the home mascot. The selected mascot persists locally on this browser/device, with Kami as the fallback. The home page retains layout and theme controls but has no mascot picker. Settings cannot interrupt an active call. No backend profile, voice or account behavior changes in this slice.

## 14. Koe app (mobile channel, replaces WhatsApp while Meta needs business verification)
- **What it is:** the same web app, installable from an **Install app** button (Chrome's install prompt; on iPhone, Share → Add to Home Screen). No app store. Opens on **Home** (the mascot); **Chat** is one tap away: a WhatsApp-style conversation with Koe, the mascot as the avatar.
- **Phone setup page (`#install`):** on a laptop it shows a QR code for `https://koe-pi.vercel.app/#install`. On the phone the same page walks through four steps, each marked ✓ when verified:
  1. **Install** (Chrome's prompt, or the iPhone instructions).
  2. **Connect**: saves the token, then checks it against the backend.
  3. **Notifications**: turns them on and sends a real test push (`POST /api/app/push/test`).
  4. **Open chat.**
- **Messages:** text, or a **voice note** recorded in the app (16 kHz mono WAV). Voice notes are transcribed by Gemini and answered **with a voice note** in Koe's call voice (Gemini Live), plus the text. History, voice-note audio and push subscriptions persist in **Neon** (`koe_app_messages`, `koe_app_voice`, `koe_app_push`; migration 002) when `DATABASE_URL` is set, so a Render restart loses nothing; otherwise in `backend/data/app.db` (SQLite, local development). Every row has an owner (ACCOUNTS_SPEC.md).
- **Approvals:** a proposed write arrives as a message with **Confirm / Cancel**, resolved through the same gate as voice and CLI (§5).
- **Live workspace:** Calendar/Sheets/Notion work from a turn opens the side panel (bottom sheet on phones) with the exact proposal, then the confirmed result and an Open link (§2 "Live workspace").
- **Notifications:** every Koe reply and GitHub alert is pushed (Web Push, VAPID keys generated once into `backend/data/vapid.pem`). The service worker skips the notification when the chat is already open on screen.
- **Security:** every `/api/app` endpoint requires `KOE_ACCESS_TOKEN` (Bearer), fail closed, because the phone reaches the backend through a public tunnel. The token is remembered on the device. Voice notes ≤ 3 MB; text ≤ 2000 characters; voice files are served only by exact generated names.
- **Limits:** Koe's spoken reply is a reading of the text reply (it can differ slightly from the text). A server restart keeps the chat history but forgets the model's working memory and any open approvals (Phase 6 adds the persisted summary).


## Pre-hosting owner sign-in (planned, 2026-10-13)
**Superseded 2026-10-13:** Koe is becoming invite-only multi-user. The contract for sign-in, per-user data, connections, quota and the public Guide/Privacy/Terms pages is [ACCOUNTS_SPEC.md](ACCOUNTS_SPEC.md). The paragraph below is kept for history.

Manual `KOE_ACCESS_TOKEN` entry is a development mechanism. Before public hosting, replace it with provider login restricted to the owner and an expiring, revocable, HttpOnly session cookie across the dashboard, calls, chat and voice-note endpoints. This is not multi-user signup, does not expose database credentials, and does not replace tool-specific consent or explicit write approvals. The flow and acceptance requirements are in [AUTH_FLOW.md](AUTH_FLOW.md); this storage migration does not implement OAuth login.

## 15. Optional manual Spotify music — 2026-10-15

The owner-only Music page (`#music`) connects Spotify with a real cookie session, selects an owned private playlist, and offers manual SDK playback, typed search and preview-confirm private playlist creation/add/remove-all/reorder. Playback targets the session's registered **Koe Web Player** device. Short-lived SDK tokens stay in browser memory; credentials and mutation evidence are encrypted on the server. API contract: [spotify/API_CONTRACT.md](spotify/API_CONTRACT.md), version 1.0.0.

Calls, voice-note recording and stored replies share an audio coordinator. It drains sent playback commands and requires a verified pause before capture or speech, then disposes the SDK device. Web Locks and BroadcastChannel coordinate tabs. Persisted unverified-audio markers survive reload/crash; a released lock alone is insufficient. Unknown results block voice, and nothing automatically resumes music. Mutation request IDs survive reload and are inspected without retrying uncertain writes.

No Spotify metadata, tokens or audio enters the agent, transcripts, tools, activity or AI providers. There are no spoken Spotify commands. The official Spotify app/web fallback always explains that Koe cannot see or pause external playback.

Implemented and isolated-tested; **SPOTIFY_ENABLED defaults false**. Live acceptance still needs developer credentials/allowlist, exact callback origin, hosted migration and resolution of the combined manual-player/voice-app policy interpretation. See [setup and simulated preview](../backend/SPOTIFY_LOCAL_SETUP.md). Passing simulated browser tests does not claim real streaming or mobile-background acceptance.

## 16. Public homepage and original provider artwork — 2026-10-16

The public root `/` now introduces Koe before sign-in. Three user-requested variations share existing Geist typography and mascot assets: `?look=studio`, `?look=after-hours`, and `?look=field-notes`. The selector updates the URL and supports browser history. The product, original provider artwork, interactive illustrative workflows, truthful feature counts, planned integrations, companion previews, approvals/privacy, and FAQ are detailed in [HOMEPAGE.md](HOMEPAGE.md).

The existing Engawa workspace and all real actions remain behind the sign-in gate at `/app`. Existing `/#home`, `/#settings`, and other application hash bookmarks continue to work. Installed-app startup and successful sign-in target `/app`. Existing public Guide, Privacy and Terms pages remain public. Static route rewrite configuration includes `/app`; no hosting deployment is part of this change.

The homepage never reads accounts or calls provider APIs. Sample approvals only update local demo state. GitHub, Google Calendar, Notion and Sheets are implemented; Spotify is optional and setup-dependent. Google Docs and Drive are explicitly planned. Connection settings, Google sign-in, Spotify surfaces and the live workspace share locally stored original provider marks. GSAP transitions clean up and honor reduced motion. The existing VRM companion remains interactive.

**Homepage artwork follow-up (2026-10-16):** The supplied transparent mascot PNGs now provide the initial hero and companion previews, with different poses per variation. The interactive VRM is an explicit Try in 3D option; Back to artwork disposes it. Existing in-app mascot and call behavior remain unchanged. See HOMEPAGE.md and BUILD_LOG.md for provenance and verification.

**Final homepage selection (2026-10-16):** Studio is now the sole homepage. The design picker and alternate variations are removed. Only Kami, Mint and Kobashi appear in its companion gallery; the count and copy say three. Aoi remains available in the separate application catalog. Earlier variation query links resolve to Studio.

## 17. Studio design principles throughout the application — 2026-10-16

The user requests Studio's typography, spacing, composition and restrained surfaces throughout the frontend, with a small font-size increase. Preserve every existing dark/light background, surface, text and mascot accent token: this is a structural and typographic redesign, not a palette change. Use shared original provider logos wherever a service is represented, including navigation, dashboard, connection settings, page headings and live work views; action icons remain Phosphor.

The selectable application and homepage companions are Kami, Mei and Kobashi. Mei replaces both displayed Miku and Mint names; retain her existing internal `miku` model/storage identifier to preserve saved choices, runtime artwork and exact accent colors. Remove Aoi from the catalog and selection UI; an old Aoi preference falls back to Kami. Do not delete the user's original model/source files.

Home receives a contained companion scene and workspace summary; Dashboard, Chat, Notion, Music, Settings and Install share a coherent Studio layout, clear page headings, consistent panel shapes, more readable text and responsive navigation. Preserve existing authentication, calls, transcripts, approval gates, music/audio coordination, settings forms, API requests and keyboard behavior. No backend, dependency, account or deployment changes are required. Verification includes build/lint, preference regressions, existing frontend tests and isolated browser coverage of all major pages at desktop and mobile widths, including exact palette values.


### 17.1 Preserve the open companion and unify interactions (2026-10-16)

The companion on Home stands freely on the existing transparent viewport stage beside the greeting; remove the newly added enclosing scene card and redundant composition wrappers. Keep the original desk, camera placement, mobile stacking and full-figure call behavior. Settings previews also use an open transparent background. Keep the selected Studio homepage, exact existing app palettes, original service logos, Mei naming and three-companion catalog. Do not introduce a new visual direction.

All equivalent controls share Geist typography, a 15px action / 13px compact control scale, 160ms state transitions, subtle color/opacity hover feedback, 0.97 press feedback, consistent keyboard focus and inert disabled states. No button lifts or decorative hover shadows. Selected rows, approval outlines and mascot selection rings remain meaningful state indicators. Floating utilities share one elevation token. Verify actual computed styles and interactions across all routes, themes and responsive layouts.


### 17.2 Core application design rollback (2026-10-16)

The user's latest instruction supersedes the app redesign and interaction/typography changes in sections 17 and 17.1. Restore the core application's pre-homepage-work design from the original repository source: original Engawa layout, typography sizes, Phosphor icons, hover/press/shadow rules, page composition and original companion catalog. Keep the selected Studio landing page exactly as it currently appears, including its supplied artwork, original provider logos and Kami/Mei/Kobashi marketing choices. Scope landing-page typography and interaction CSS so it cannot alter the core app. Keep routing necessary for the landing page and /app. Preserve unrelated pre-existing backend, approval presentation and audit work. Make no further design improvements until the user specifies them.


### 17.3 Original provider logos only; separately approved voice/music control (2026-10-16)

Keep the restored core application layout, fonts, colors, mascot catalog and interaction rules. Replace third-party service symbols with their original local brand artwork across navigation, dashboard, settings, music, Notion, workspace and provider links; do not redesign containers.

Sign-in mascot styles apply only to the direct mascot image. The Google button's original mark stays 18px square with no mascot ring, clipping or inherited margins. Verify computed sizing and button fit at desktop/mobile widths in both themes; preserve the existing sign-in composition.

Music settings transport/server failures must show a recoverable loading error with an explicit Retry button, not claim the player is unimplemented. Retrying reads must not repeat writes, launch Spotify consent or start playback. A 401 remains a sign-in action, and known disabled/missing configuration states remain distinct.

A connected account with a saved playlist that becomes public, collaborative or no longer owned must remain connected. Clear the displayed stale playlist/tracks and return to eligible playlist selection with an explanation and existing preview-confirm private-playlist creation. Do not turn a playlist eligibility error into a network/sign-in error or change its privacy automatically.

SDK connection/device registration is preparation, not sent playback. If preparation fails before any transfer/play/local resume, an otherwise clean player must remain idle and must not falsely block voice. Prior playback evidence, unresolved sent commands and actual observed playback still block until verified paused. Retry only read-only device discovery for bounded readiness propagation; never retry uncertain playback writes automatically. A failed SDK connect must be retryable on the next explicit Play.

### 17.4 Music UX feedback — planned, not authorized to implement (2026-10-16)

**Subsequent authorization:** Rohit has now instructed implementation, committing/pushing the complete reviewed working tree and verifying local/live compatibility. The earlier hold below is historical. Same-page compact Call reuses the conversational agent; a requested playback finishes speech and ends the call before music, with that transition visible. Artist/title queries are resolved outside the model against the granted playlist; no catalog data is fed into the model. Missing matches suggest a search/add opportunity without automatic writes. Direct manual Add is an explicit music-only approval and remains idempotent. Shared Neon schema and hosted callback/feature configuration must be checked independently of code deployment.

The user explicitly says **do not build now**. Record the later target in [tasks/plan.md](../tasks/plan.md) and [tasks/todo.md](../tasks/todo.md): compact conversational assistant with Call directly on Music, no separate-window prerequisite, artist/random-artist and exact-song requests within the permitted playlist, a useful suggestion to add a missing song, real thumbnails in search, direct deliberate Add without a second dialog or oversized notification, reliable connection recovery, and a coherent Music-only visual/scrolling/GSAP treatment that preserves current Koe design principles. The assistant is a small instance, not a full-body scene. This changes the future desired Music experience, including its Add interaction; it does not remove other approval rules or authorize implementation, metadata-policy assumptions, mixed audio, account actions or deployment. Await an explicit start instruction.

The user explicitly confirms written Spotify approval for voice control and requests separate voice and music entities. Implement a separately gated music-control service with an owner-session-bound player connection and an explicit per-playlist user grant. Only play/resume, pause, bounded next/previous and volume commands are allowed; no voice playlist edits, Spotify search, catalog metadata, credentials or audio enter model context. The music tool is offered only to live web voice when the deployment flag records policy approval. Default is disabled. A model cannot grant itself permission.

Music remains paused while voice owns audio. A requested play during a call is acknowledged as queued, then the call ends after its response audio drains, releases audio ownership, and the explicitly requested music starts. No unrequested automatic resume, audio extraction, overlay or false success. Browser autoplay restrictions, unavailable service/player, stale/revoked grants, duplicate commands and uncertain/disconnected outcomes must be reported honestly. The restored design changes only by the necessary original-logo replacements and an explicit voice-permission control using existing component styles. Hosted migrations, account consent and real streaming acceptance are separate from isolated end-to-end tests.
### Music repair acceptance — 2026-10-17

Playback acceptance must tolerate delayed Spotify SDK state: after a single accepted play write, observe the requested track playing within a bounded window; never replay the write to obtain confirmation. Keep unresolved starts protected by the audio barrier even if an intermediate SDK event says paused. Voice handoff acknowledgements have a 25-second budget inside the existing 30-second route / 35-second browser budgets. Loader retries replace timed-out scripts. iOS volume uses physical device controls, with explicit guidance instead of a slider that falsely reports success. Do not change hosted settings or operate Render for this repair.

Authorized: repair Home/Music calls after reload with verified audio recovery under the cross-tab audio lock; never replay unknown writes. Inspect completed intents automatically. Open one cancellable playlist selector without stopping playback until a selection is committed. Provide inline private-playlist creation, artist suggestions with debounced Spotify search, compact volume controls, and canonical /app/music-style routes (legacy hashes migrate). Preserve existing theme/type/landing page. Verify browser desktop/mobile, audio handoff, playlist/search/mutations and backend contracts before reporting completion. Recovery may pause only a previously recorded Koe playback device; uncertain sent playback remains blocked with a useful explanation. Spotify metadata stays outside model context.


### GitHub workflow completion — 2026-10-18
GitHub reads use the signed-in person's account and selected repositories. Preserve explicit empty repository selection. Show yesterday's activity automatically on the dashboard with source-linked commits, local date boundaries, scope and observed time. Agent answers must read GitHub evidence rather than guess from memory. Add a bounded read-only commit detail tool for summaries (message, author, stats, changed files, source URL); content is untrusted and no patch instructions are executed. Partial repository failures retain accessible evidence and never present partial totals as complete. Preserve comment approval and no-merge rules. Music latency work is deferred; Google Docs creation/editing is selected for a later task, replacing the standalone Drive roadmap item.
