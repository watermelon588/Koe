# Architecture: Koe (声)

## Versioned Calendar plans and conference readiness — 2026-10-14

`calendar.py` expands a small daily/weekly recurrence object into at most 20 exact occurrences and a canonical RRULE; all-day events use exclusive date ends. Every occurrence is checked against complete bounded event evidence. Shared proposals freeze configured Calendar/timezone and individual move/cancellation versions. Cancellation scope is explicit single/instance/whole series, validated against real IDs and organizer identity; DELETE uses If-Match and guest notifications. Recurring series/instance moves remain unsupported. Mutation responses are checked against approved event fields before a verified result.

Meet creation uses the persisted approval ID and `conferenceDataVersion=1`. Provider pending/failure is separate from event save; only actual allowlisted HTTPS Meet URLs are exposed. `calendar_get_event` rereads versions/recurring identity/conference status. Operation/scan deadlines, page/event/response bounds and off-loop TLS/credential work protect the call. No mutation retries. Bounded `call_work` projections extend Calendar data without exposing frozen execution arguments; cancellations invalidate availability and deterministic text explains outcomes. No frontend source changes. Contracts: [CALENDAR_EXTENSIONS.md](CALENDAR_EXTENSIONS.md), [FRONTEND_BACKEND_HANDOFF.md](FRONTEND_BACKEND_HANDOFF.md).

## Schema creation and stable Sheets edits — 2026-10-14

`sheet_workspace.py` owns bounded typed Sheets reads, column insertion and row updates. `sheets_find_rows` returns actual IDs and row/header versions; `sheets_update_row` stores an exact old/new preview and freezes the destination/tab/schema. At approval it rescans identity, rejects stale data and formula targets, then creates/reuses Google developer metadata and verifies that the anchor resolves to the same row/version. RAW values with null skips update only requested cells. Post-write reads verify the result. Metadata-based addressing follows structural row moves; it does not provide an external-editor transaction lock.

`sheets_add_columns` inserts new physical columns and literal headers in one atomic batch, shifting existing data/formulas instead of overwriting it. The canonical Sheets module supplies a shared per-tab write lock for append, schema and edit operations within this single-process backend. Typed reads are bounded to 5000 data rows/52 headers; response bodies and model output have explicit size limits.

`notion_schema.py` owns additive new property definitions, validating explicit names/types/options and freezing the complete existing schema/source. Approved execution patches only new properties and verifies existing definitions plus new types/options. All three writers run through the shared persisted approval gate. The Notion proposals API also accepts `notion_add_properties`. Model-facing arguments never accept raw snapshots, API payloads or arbitrary destinations. [SCHEMA_ROW_EDIT_PLAN.md](SCHEMA_ROW_EDIT_PLAN.md) documents scope, examples, verification and optimistic concurrency limits. UI and Render are untouched.

## Deterministic integration expansion — 2026-10-13

The shared tool registry now includes `github_activity`, `github_contributions`, `sheets_schema` and `notion_schema`. GitHub history has explicit exclusive-end boundaries; Python deduplicates and calculates counts/line changes/streaks. History reads have a 30-second total budget; optional commit detail reads have a 50-commit cap, four-way concurrency and a 15-second budget. Streaks use GitHub calendar dates with UTC request bounds; local-day shipped history uses the configured timezone. Contribution-day lists are opt-in to keep the model context compact.

Calendar details/reminders, optional existing Sheets columns and optional existing Notion properties extend the existing approved writers. The LLM never supplies raw API payloads or executes code. Python validates values and destinations, discovers real field definitions, freezes requested schema identity with the proposal and checks it again at execution. Tracking fields and computed Notion results cannot be overridden. Owner-only Notion schema discovery is also available at GET `/api/notion/schema`.

No frontend files, credentials, OAuth scopes or dependencies changed. [DETERMINISTIC_FEATURES.md](DETERMINISTIC_FEATURES.md) lists implemented capabilities, evidence, examples and explicitly queued extensions.

## Backend reliability update — 2026-10-13

All Gemini text generation, including structured tool-free PR analysis, uses `gemini.generate`: individual SDK attempts have a 15-second timeout and the complete model/key selection has a 30-second budget. Cold credential lookups run in a worker thread. Exhausted transient HTTP and transport failures can reach the existing OpenRouter text fallback only at the start of an agent turn; no tool turn is restarted or replayed. PR analysis retains its structured JSON schema and no-tools policy, using Gemini model/key fallback. Voice-note generation discards partial audio before trying a replacement key.

`store.record_later` has a 128-task best-effort backlog. Saturation is logged and skipped, unexpected task errors are consumed without private exception bodies, and the FastAPI lifespan drains for up to five seconds on shutdown. SQL already in a worker thread may finish after cancellation; connection/statement timeouts apply. Durable proposal, claim and finish writes remain awaited, atomic and never automatically retried.

`/health` preserves its response body and adds a validated `X-Koe-Revision` from Render's `RENDER_GIT_COMMIT`. Owner-only `/api/backend/status` reports configuration presence and bounded-work limits with no-store headers, without external service calls or secrets. It diagnoses what was deployed/configured, not provider availability or remaining quota. The frontend is unchanged in this pass.

## 1. The big idea: one brain, many entrances
The **agent core** (system prompt, tool registry, approval gate, memory) is written once. The web call, WhatsApp and GitHub webhooks are just different **entrances** to it. That's why something done on WhatsApp in the morning is known on the web call in the evening.

```
┌──────────────────────── BROWSER (React, on Vercel) ────────────────────────┐
│  ┌───────── Call panel ─────────┐   ┌─────────────── Dashboard ───────────┐ │
│  │  Mascot (3D VRM, three.js)   │   │ Today: Calendar timeline            │ │
│  │  🎙 mic → 16 kHz PCM16       │   │ GitHub: review queue · my PRs · CI  │ │
│  │  🔊 speaker ← 24 kHz PCM16   │   │ Shipped today (→ Notion log)        │ │
│  │  live transcript + latency   │   │ Activity feed + Approve/Reject      │ │
│  └──────────────┬───────────────┘   │ Latency panel                       │ │
│                 │                   └──────────────▲──────────────────────┘ │
└─────────────────┼──────────────────────────────────┼────────────────────────┘
       wss /ws/call (audio + control)       wss /ws/events (JSON events)
┌─────────────────▼──────────────────────────────────┴────────────────────────┐
│                  FASTAPI BACKEND (one Python process)                       │
│                                                                             │
│  voice_call.py ── relays audio ──► Gemini Live session (speech-to-speech)   │
│                                      │ tool_call(find_free, …)              │
│  whatsapp.py ◄── POST /webhooks/whatsapp (voice note / text / button)       │
│      └─► Gemini (audio in) ─────┐    │                                      │
│                                 ▼    ▼                                      │
│  github_hooks.py ◄── POST /webhooks/github ──► alert rules ──► WhatsApp     │
│                          ┌────────────────────┐                             │
│                          │     AGENT CORE     │  prompt · tools · approval  │
│                          │     agent.py       │  gate · context builder     │
│                          └─────────┬──────────┘                             │
│        tools/github.py  tools/calendar.py  tools/notion.py  tools/sheets.py │
│        store.py (Neon PostgreSQL via psycopg + atomic SQL functions)            │
│        events.py (in-process pub/sub → /ws/events)                          │
└─────────────────────────────────────────────────────────────────────────────┘
      ▲ HTTPS (dev: cloudflared tunnel · prod: Azure VM + Caddy)   │
 Meta WhatsApp Cloud API ◄───────── Send API ──────────────────────┘
      ▲                                     GitHub ──webhooks──▲
   Your phone 📱
```

## 2. Components

| Component | File(s) | Responsibility |
|---|---|---|
| App entry | `backend/koe/main.py` | FastAPI app, routes, startup (DB, config) |
| Config | `backend/koe/config.py` | Loads `.env` (`pydantic-settings`): keys, allow-lists, timezone, working hours |
| Agent core | `backend/koe/agent.py` + `text_agent.py` | Shared prompt, tool registry, conversation-scoped approval; bounded text loop for CLI and future WhatsApp/evals. Cross-channel context builder is Phase 6. |
| Approval gate | inside `agent.py` + `store.py` | Write tools → pending action → resolve on approve/reject/expiry |
| Web call | `backend/koe/voice_call.py` | `/ws/call`: browser audio ⇄ Gemini Live; handles tool calls, barge-in, session resumption, latency timestamps |
| WhatsApp | `backend/koe/whatsapp.py` | Webhook verify + receive, media download, background processing, send text/buttons/templates |
| GitHub hooks | `backend/koe/github_hooks.py` | Verify signature, dedupe delivery, map events → alert rules |
| Tools | `backend/koe/tools/*.py` | Thin, tested wrappers around each API; enforce timezone, double-booking and diff limits |
| Phase 4 tools | `tools/github_work.py`, `tools/notion.py`, `tools/sheets.py` | Bounded tool-free Gemini PR analysis, authored history, append-only daily log and approved comment/hours writes. Existing proposal/claim/finish path protects Calendar, comments and every Sheets row; Notion follows the own-log exception. |
| Store | `backend/koe/store.py` + `backend/migrations/001_phase2.sql` | Parameterized PostgreSQL calls; PostgreSQL persists activity and atomically proposes/claims/finishes approvals. Tables are backend-only. |
| Events | `backend/koe/events.py` | In-process pub/sub (`asyncio.Queue` per dashboard client) → `/ws/events` |
| Evals | `backend/evals/` | Scripted requests → agent (text mode) → score tool choice, args, end state, latency |
| Frontend | `frontend/src/` | Call panel (mic capture via AudioWorklet, playback queue), mascot, dashboard panels |
| Notion workspace | `notion_api.py`, `notion_service.py`, `frontend/src/notion/` | Authenticated source-scoped reads, additive schema setup, approved create/update/trash and persisted activity. UI proposals reuse the agent gate in a stable owner-scoped conversation, independently of chat/calls. |
| Optional text fallback | `text_fallback.py` | Existing httpx calls OpenRouter free models only after an initial Gemini 429/503, before tools execute. Same registry/gate; no replay or voice fallback. |

## 3. Flow A: live web call (the latency-critical path)
```
1. User clicks Call → browser asks for mic → opens wss://…/ws/call
2. Backend opens a Gemini Live session (system prompt + today's context + tool schemas)
3. Browser AudioWorklet captures mic → 16 kHz mono PCM16 chunks (~20–40 ms) → WS → backend → Gemini
4. Gemini detects end of speech (server-side voice activity detection) and starts streaming 24 kHz audio back
     backend → WS → browser playback queue → speaker; analyser drives the mascot's mouth
5. If Gemini emits tool_call(calendar_find_free …):
     backend sends {"type":"tool","name":…, "phase":"start"} on both event/call paths → mascot "thinking", panel highlights
     runs the tool (read: immediately · write: create pending action, Gemini asks the user aloud)
     returns the result to Gemini → Gemini continues speaking
6. Barge-in: user speaks while Koe talks → Gemini signals "interrupted" → backend tells the browser
     to flush its playback queue instantly
7. Every turn: timestamps saved (speech_end, first_audio_out, tool spans) → latency panel
```
**Latency budget (target p50 ≤ 1.5 s, speech end → first audio):** voice activity detection end-pointing about 300–500 ms · model first audio about 400–800 ms · network, browser ⇄ backend ⇄ Google, about 100–200 ms. A tool call adds its own time (300–800 ms). The agent speaks a short filler ("checking your calendar…") while it runs.

## 4. Flow B: WhatsApp voice note
```
0.0s  User sends a voice note → Meta POSTs /webhooks/whatsapp {type: audio, audio.id}
      Backend verifies signature, returns 200 immediately, queues background work
~0.5s GET media URL by ID → download .ogg (Opus)
~1.3s Gemini (standard) with the audio + today's context + tool schemas → tool calls
~2.0s Run read tools; for write tools → pending action → send Confirm/Cancel buttons
~2.5s Send reply text via the Send API
~3.0s Reply on the phone
Button tap → new webhook (interactive reply) → resolve pending action → execute → "✅ Booked"
```

## 5. Flow C: GitHub push alert
```
GitHub → POST /webhooks/github (event, delivery id, signature)
  → verify HMAC → dedupe by delivery id → match alert rule (SPEC §4)
  → log to activity + /ws/events → WhatsApp send (template if outside the 24 h window)
```
No LLM in this path: it's fast, free and deterministic.

## 6. Data model (Neon PostgreSQL)
```sql
koe_activity(id, owner_id, ts, session_id, channel, kind, summary, payload_json, latency_json)
koe_pending_actions(id, owner_id, session_id, channel, created_ts, expires_ts,
                    tool, args_json, summary, status, result_json)
  -- status: pending|executing|rejected|expired|executed|failed
koe_daily_notes(owner_id, date, summary)        -- Phase 6 roll-up
koe_github_deliveries(owner_id, delivery_id, ts) -- reserved for Phase 5 persistent dedupe
```
Migration: `backend/migrations/001_phase2.sql`. All four tables have RLS enabled and PUBLIC grants revoked. The backend database role owns the tables and functions and has implicit owner access; browsers never receive database credentials. This is backend-only storage, not per-user RLS for a public multi-user app. Restricted, security-invoker SQL functions atomically record proposals, claim approvals and record outcomes. The server fixes `owner_id` from configuration; a browser/model cannot select another owner. One active pending proposal is allowed per conversation, with a ten-minute expiry. A claim sets `executing` before Google is called, so concurrent confirmation cannot run it twice. External writes are not automatically retried if the outcome is uncertain.

Neon is independently hosted in Singapore; deploying/restarting FastAPI does not remove this data. Free compute scales to zero when idle and reconnects may incur a cold start. See SERVICES_AND_COSTS and PHASE2_SETUP. The server reads backend-only `DATABASE_URL`; psycopg connections run in worker threads with connection and per-transaction statement timeouts. Parameters remain bound values and uncertain writes are never retried. Browser calls currently use `KOE_ACCESS_TOKEN`. Owner-only provider sign-in and secure sessions must replace manual token entry before hosting; see [AUTH_FLOW.md](AUTH_FLOW.md). App chat SQLite, push subscriptions and local voice files remain unchanged and require persistent backend disk.

Google event writes use a final paginated overlap check and a one-process lock. Moving an event excludes its own old occurrence and uses If-Match to avoid overwriting a changed event. Google cannot atomically lock a free slot across other calendar clients. Actual voice latency remains to be remeasured with the hosted store; metadata logging uses a bounded background queue rather than blocking audio frames.

## 7. Repo layout
```
Koe (声)/
├── CLAUDE.md
├── docs/                  # these documents
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   ├── koe/
│   │   ├── main.py  config.py  agent.py  text_agent.py  google_auth.py  store.py  events.py
│   │   ├── voice_call.py  whatsapp.py  github_hooks.py
│   │   └── tools/  github.py  calendar.py  notion.py  sheets.py
│   ├── migrations/        # Neon SQL, applied with scripts.migrate_store
│   ├── scripts/           # consent, setup check, text CLI, smoke tests
│   ├── evals/             # cases.yaml + run.py
│   └── tests/
└── frontend/              # Vite + React + TS
    └── src/  App.tsx  call/ (audio worklet, ws client)  mascot/  panels/
```
Keep it flat. Split a file only when it passes about 400 lines, and log the split.

## Notion workspace flow

Home/Chat/Notion/Settings navigation persists. The root owns the call hook and keeps the CallPanel mounted while changing pages; a compact strip exposes mute/end/return off Home. Notion lists and previews call `/api/notion/*` directly and remain usable without an LLM. Service tokens remain backend-only; the browser supplies its existing Koe access token.

New/edit/trash → `agent.prepare_write` normalizes all values and fixes the destination → Neon durable proposal → full browser/model preview → explicit decision → atomic claim → scoped Notion operation → persisted outcome. The browser receives display fields, never stored execution args. Page parent and revision are rechecked before edits/trash. Creates carry the approval UUID in `Koe action ID`; uncertain writes never auto-retry. Notes are appended, not replaced. Daily logs retain their existing own-log exception and dedupe within daily-log records, independently of tasks/meetings. Calendar booking remains a separate approved tool.

Notion preview is bounded to 500 top-level blocks. Cross-client revision checks and separate metadata/block requests cannot provide a transactional Notion edit; partial or uncertain results require inspection. One backend worker remains required. Scope and acceptance: [NOTION_PLAN.md](NOTION_PLAN.md).

## Calendar and Sheets call work windows

`voice_call.py` sends Google tool start/end display data through `call_work.project`, which whitelists bounded inputs/results and excludes raw execution args and credentials. The exact stored proposal supplies pending/progress/result details. `useCall` feeds these frames to `call/workState.ts`; the existing CallPanel automatically selects Calendar or Sheets on each relevant event. It retains separate service views for this call and resets them for a new call. Manual tabs can return to transcript or Day without affecting audio.

`WorkPanel.tsx` renders a timezone-aware day timeline (events/free windows/proposed or confirmed slot) and a Sheets hours-row preview with the confirmed row/range. Confirmed Calendar writes invalidate the earlier free windows; moves remove the old occurrence from the displayed snapshot. No iframe, additional Google request, new tool or dependency is needed. Normalized data goes through the existing approval gate; the UI shows saving while the application checks a decision and saved only after an executed outcome. Partial/uncertain failures retain an inspect-before-retry message. The projection caps Calendar rows at 100 and explicitly marks truncation. This is a view of the latest tool result, not a continuously synchronized Google client.

## 8. Deployment
| Stage | Backend | Frontend | Public URL for webhooks |
|---|---|---|---|
| Dev (Phases 1–6) | Laptop, `uvicorn --reload` | `npm run dev` | `cloudflared` quick tunnel (URL changes per run; update Meta/GitHub webhook URLs) |
| Now (temporary) | **Render free** web service from `render.yaml` (sleeps when idle, disk wiped) | **Vercel** free | `https://<backend>.onrender.com` (stable). Steps: [DEPLOY.md](DEPLOY.md) |
| Prod (Phase 7) | **Azure for Students** small Linux VM: `uvicorn` under `systemd`, **Caddy** for automatic HTTPS on the free `*.cloudapp.azure.com` DNS name | **Vercel** free | The VM's HTTPS URL (stable) |

Render free is the temporary host (2026-10-13), chosen for a stable HTTPS URL today. Its WebSockets work over `wss` (https://render.com/docs/websocket). Its limits are why it isn't the final host: it sleeps after 15 min idle (about 1 min cold start), the filesystem is wiped on restart (local Google credential files would need secure reprovisioning), WebSocket support on free is disputed, and GitHub webhooks (10 s timeout, no auto-retry) would be lost. See SERVICES_AND_COSTS.md.

## 9. Security (minimal but real)
- Webhook signature verification (Meta + GitHub).
- WhatsApp sender allow-list.
- `/ws/call` checks a shared secret (`KOE_ACCESS_TOKEN`) in its first frame when configured, and requires it when Neon enables writes. `/ws/events` always requires that token before sending snapshots or reading services. This is single-user; Provider login is a later slice.
- Least-privilege tokens: GitHub fine-grained token (read PRs/contents/checks on selected repos, write to issues/PR comments only); Google OAuth scopes limited to Calendar events and Sheets.


## Dashboard implementation (Phase 3)

`dashboard.py` exposes the read-only `/ws/events` socket. It subscribes each authenticated browser to `events.py`'s bounded queue, sends the cached snapshot immediately, then refreshes today's Calendar and the two GitHub read panels concurrently. A process-wide lock coalesces refreshes for 30 seconds; the server repeats the read cycle every 60 seconds while clients are connected. A background read cannot overwrite a more recent conversational tool result. Successful approved Calendar writes invalidate the cache for the next refresh.

`agent.py` publishes tool start/end and proposal/claim/result events from the shared channel path. `voice_call.py` publishes measured turn latency and `github_hooks.py` publishes verified matched alerts. Publication uses nonblocking queue operations; a slow browser gets a current snapshot instead of holding up audio. The hub retains at most 100 activity/latency records and 100 pending display cards. It is process-local: run one Uvicorn worker until an external pub/sub service is deliberately introduced.

Neon hydration selects owner-scoped recent activity and pending display fields; stored arguments and backend credentials never go to the browser. Current-process activity takes precedence over saved rows from the same sessions to avoid showing the same operation twice. Without Neon, live activity lasts only until server restart. Matched webhook alerts are currently process-local; durable webhook processing remains Phase 5.

`frontend/src/dashboard/` owns snapshot/event reduction, reconnect backoff, panel rendering and nearest-rank latency percentiles. The home dashboard has no fictional fallback data. The call panel's Day/Chat switch shows the same panels while the audio conversation continues. Only a pending ID already present on that call's approval card gets controls; other conversation proposals are informational. `/ws/events` accepts refresh commands only, never approval or tool execution.
