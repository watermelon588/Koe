# Architecture: Koe (声)

## 1. The big idea: one brain, many entrances
The **agent core** (system prompt, tool registry, approval gate, memory) is written once. The web call, WhatsApp and GitHub webhooks are just different **entrances** to it. That's why something done on WhatsApp in the morning is known on the web call in the evening.

```
┌──────────────────────── BROWSER (React, on Vercel) ────────────────────────┐
│  ┌───────── Call panel ─────────┐   ┌─────────────── Dashboard ───────────┐ │
│  │  Mascot (SVG, Web Audio)     │   │ Today: Calendar timeline            │ │
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
│        store.py (SQLite: activity, pending_actions, daily_notes)            │
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
| Agent core | `backend/koe/agent.py` | System prompt, **tool registry** (name → function + JSON schema + `needs_approval`), context builder (today's summary), text-mode agent loop for WhatsApp/evals |
| Approval gate | inside `agent.py` + `store.py` | Write tools → pending action → resolve on approve/reject/expiry |
| Web call | `backend/koe/voice_call.py` | `/ws/call`: browser audio ⇄ Gemini Live; handles tool calls, barge-in, session resumption, latency timestamps |
| WhatsApp | `backend/koe/whatsapp.py` | Webhook verify + receive, media download, background processing, send text/buttons/templates |
| GitHub hooks | `backend/koe/github_hooks.py` | Verify signature, dedupe delivery, map events → alert rules |
| Tools | `backend/koe/tools/*.py` | Thin, tested wrappers around each API; enforce timezone, double-booking and diff limits |
| Store | `backend/koe/store.py` | SQLite via stdlib `sqlite3`: activity, pending_actions, daily_notes |
| Events | `backend/koe/events.py` | In-process pub/sub (`asyncio.Queue` per dashboard client) → `/ws/events` |
| Evals | `backend/evals/` | Scripted requests → agent (text mode) → score tool choice, args, end state, latency |
| Frontend | `frontend/src/` | Call panel (mic capture via AudioWorklet, playback queue), mascot, dashboard panels |

## 3. Flow A: live web call (the latency-critical path)
```
1. User clicks Call → browser asks for mic → opens wss://…/ws/call
2. Backend opens a Gemini Live session (system prompt + today's context + tool schemas)
3. Browser AudioWorklet captures mic → 16 kHz mono PCM16 chunks (~20–40 ms) → WS → backend → Gemini
4. Gemini detects end of speech (server-side voice activity detection) and starts streaming 24 kHz audio back
     backend → WS → browser playback queue → speaker; analyser drives the mascot's mouth
5. If Gemini emits tool_call(calendar_find_free …):
     backend sends {"type":"thinking","tool":…} to /ws/events → mascot "thinking", panel highlights
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

## 6. Data model (SQLite)
```sql
activity(id, ts, channel, kind, summary, payload_json, latency_json)
   -- channel: web|whatsapp|github  kind: message|tool|alert|approval
pending_actions(id, created_ts, expires_ts, channel, tool, args_json, status, result_json)
   -- status: pending|approved|rejected|expired|executed|failed
daily_notes(date, summary)            -- rolled-up context fed into new sessions
github_deliveries(delivery_id, ts)    -- webhook dedupe
```

## 7. Repo layout
```
Koe (声)/
├── CLAUDE.md
├── docs/                  # these documents
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   ├── koe/
│   │   ├── main.py  config.py  agent.py  store.py  events.py
│   │   ├── voice_call.py  whatsapp.py  github_hooks.py
│   │   └── tools/  github.py  calendar.py  notion.py  sheets.py
│   ├── evals/             # cases.yaml + run.py
│   └── tests/
└── frontend/              # Vite + React + TS
    └── src/  App.tsx  call/ (audio worklet, ws client)  mascot/  panels/
```
Keep it flat. Split a file only when it passes about 400 lines, and log the split.

## 8. Deployment
| Stage | Backend | Frontend | Public URL for webhooks |
|---|---|---|---|
| Dev (Phases 1–6) | Laptop, `uvicorn --reload` | `npm run dev` | `cloudflared` quick tunnel (URL changes per run; update Meta/GitHub webhook URLs) |
| Prod (Phase 7) | **Azure for Students** small Linux VM: `uvicorn` under `systemd`, **Caddy** for automatic HTTPS on the free `*.cloudapp.azure.com` DNS name | **Vercel** free | The VM's HTTPS URL (stable) |

Why not Render free: it sleeps after 15 min idle (about 1 min cold start), the filesystem is wiped on restart (SQLite lost), WebSocket support on free is disputed, and GitHub webhooks (10 s timeout, no auto-retry) would be lost. See SERVICES_AND_COSTS.md.

## 9. Security (minimal but real)
- Webhook signature verification (Meta + GitHub).
- WhatsApp sender allow-list.
- The dashboard and `/ws/*` require a single shared secret (`KOE_ACCESS_TOKEN`) sent by the frontend. This is single-user, so no login system; it just stops strangers from using your agent once it's public.
- Least-privilege tokens: GitHub fine-grained token (read PRs/contents/checks on selected repos, write to issues/PR comments only); Google OAuth scopes limited to Calendar events and Sheets.
