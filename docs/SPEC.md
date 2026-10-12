# Spec: Koe (声)

> **Status:** v0.1, 2026-10-12. This file is the contract. Change it before changing behavior, and log the change in [DECISIONS.md](DECISIONS.md).

## 1. Objective
A single-user, voice-first agent for a developer founder. It works across GitHub, Google Calendar, Notion and Google Sheets, through two channels: a **live web voice call with a mascot** and **WhatsApp**. Every write that affects others or the calendar waits for the user's approval. Accuracy and latency are measured.

### User stories
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
- **Phase 2 authentication:** when `KOE_ACCESS_TOKEN` is configured, the first browser frame must be `{"type":"auth","token":"…"}` within 10 seconds. Supabase-enabled browser calls require this app token. Close code `1008` indicates missing/invalid authentication. The token never goes in the URL; Supabase secrets never go in the browser.
- **Phase 2 approval:** backend sends `{"type":"approval_pending","id":"UUID","summary":"…","expires_ts":"…"}`. Browser may reply `{"type":"approval","action_id":"UUID","approve":true|false}`. Backend sends `approval_result` with authoritative `status`/`error` and any remaining `pending_action`. A complete, explicit spoken/typed yes or no also resolves the original conversation's proposal; model/tool text cannot authorize it.
- **Close codes:** normal hang-up = 1000. `1011` with a `reason` such as `"Gemini error: …"` = the call failed; show the reason.
- Unknown event types must be ignored (more come in Phase 3: dashboard events on `/ws/events`).

**Allowed WhatsApp senders:** only numbers in `ALLOWED_WHATSAPP_NUMBERS` (env). Everything else is ignored and logged.

### `/ws/events` dashboard protocol (Phase 3)
- The first frame is `{"type":"auth","token":"…"}` within 10 seconds. `KOE_ACCESS_TOKEN` is required even without Supabase. No dashboard data or external reads happen before authentication; invalid/missing tokens close with `1008`.
- Backend sends a `snapshot` with today's Calendar, review queue, open PRs, recent activity, pending approvals and measured turn latencies. Incremental events are `panel`, `tool`, `approval_pending`, `approval_progress`, `approval_result`, `alert` and `latency`; each carries an ID, timestamp and optional original session/channel.
- Browser may send `{"type":"refresh"}` for a read-only refresh. Refreshes are coalesced and limited to once per 30 seconds across clients, with a 60-second automatic refresh while connected. Missing services show explicit setup errors; there is no sample data fallback. Panels show their last update and become stale on disconnection.
- This single-process, single-owner stream uses bounded client queues. Slow clients receive a fresh snapshot instead of blocking audio/tool work. Restart/reconnect reloads recent saved activity and pending proposals from Supabase when configured; read panels are fetched again. No Redis or new dependency is needed.
- Dashboard approvals are informational outside their original conversation. Approve/Reject in the live call's dashboard view sends the existing `/ws/call` action-ID control; the events socket cannot authorize writes or approve another conversation's proposal. Expired cards are disabled locally and remain subject to the database expiry check.
- During calls a Day/Chat switch keeps the dashboard accessible alongside the current call controls. The existing audio-driven mascot states remain on `/ws/call`; dashboard alerts can trigger a brief reaction only when idle.

## 3. Tools (the agent's whole surface: 10 tools)
All tools live in one registry and are shared by both channels. Each tool returns JSON. On failure it returns `{"error": {"code", "message", "hint"}}` instead of raising, so the model can recover.

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

Also in scope: `calendar_list(date)`, a read tool. **Count: 10 tools max.** Adding one needs the user's approval.

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
- Tools marked **write: approval** never execute directly. The agent core creates a **pending action** (stored in Supabase PostgreSQL) and asks:
  - **Web call:** Koe asks out loud ("Book 7:00–7:30 with Rahul. Shall I?"). A spoken yes or no resolves it, and the dashboard shows Approve/Reject buttons too.
  - **WhatsApp:** an interactive message with **Confirm / Cancel** buttons.
- Pending actions expire after 10 minutes.
- A restricted SQL function atomically claims the action before external execution. Only its owner and original conversation may resolve it. Claim/result-recording uncertainty never triggers an automatic write retry. The backend is still a single-user application; Supabase Auth login is a separate UI/auth slice.
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
- **UI:** two layouts on the home route, switchable in the header (`?ui=`): **Shoji** (she stands right; a call slides a panel in from the right and she steps left, full figure) and **Engawa** (she stands left; a call raises a sheet on the right). Dark theme by default, light theme grey not white; flat backgrounds, light type, one accent per mascot. The call panel holds the live transcript, a text box (typed chat), mute and end. Don't ship the name "Miku": teal twin-tails + that name reads as Hatsune Miku (trademark).

## 7. Memory
- **Supabase PostgreSQL**: `koe_activity` (actions/messages with channel and latency), `koe_pending_actions`, `koe_daily_notes`, `koe_github_deliveries`. Backend-only access through Supabase REST; no database secrets in the browser.
- At the start of every web call or WhatsApp turn, the agent gets a **short summary of today's activity across both channels**, plus the last few WhatsApp turns. This is what lets the channels share one memory.
- No vector database or long-term memory in v1.

## 8. Latency instrumentation
Every turn records timestamps, stored in `activity` and shown on the dashboard:
- **Web call:** `user_speech_end → first_audio_out` (headline metric), plus `tool_start/tool_end` for each tool.
- **WhatsApp:** `webhook_received → media_downloaded → model_done → tools_done → reply_sent`.

## 9. Limits and safety
- Max call length is set by Gemini Live's free-tier session cap. Use session resumption to continue transparently.
- WhatsApp: process at most 1 message at a time per sender (queue the rest), and acknowledge webhooks within 1 s (return 200 immediately, process in the background).
- Validate every webhook: Meta (`X-Hub-Signature-256`) and GitHub (`X-Hub-Signature-256`, HMAC with the secret).
- Secrets live only in `.env` (git-ignored). `.env.example` lists the variable names.

## 10. Acceptance criteria (v1 done)
- [ ] Web call: natural conversation with the mascot. Barge-in works. p50 speech-end → first audio measured and shown.
- [ ] All 10 tools work by voice on the web and by WhatsApp voice note or text.
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
- Notion logs append bullets to one page per Date in the configured data source. Exact repeated entries are skipped; duplicate daily pages or incomplete reads fail closed. This own-log write follows the existing low-risk exception. Use one backend worker; Notion writes are not transactional with Supabase.
- Sheets uses existing Google OAuth with additional Sheets consent. Require headers Date, Client, Hours, Note, Koe action ID in A1:E1. Append RAW values to avoid interpreting text as formulas. Bind proposals to the configured spreadsheet and tab; the internal action ID is an audit field.

## Frontend profile settings — 2026-10-12

Visual revision: Settings uses one viewport-adaptive companion studio, actual VRM portrait thumbnails, and controls overlaid on the viewer. Full-body framing automatically expands the same canvas to a large inspection pane. Inspection supports persistent 360-degree rotation and zoom. Vertical placement stays fixed; left/right arrows rotate and Home resets rotation. Keep only framing, expand/close, wave, turntable, zoom and explicit Choose controls; remove descriptive card copy and the separate expression/mood button groups. Expanded view supports Escape, focus containment and restoration. Home rendering and saved selection semantics remain unchanged.

The dedicated `#settings` page owns mascot selection: Kami, Miku, Aoi and Kobashi. Users preview one live VRM at a time, try gestures, expressions and call moods, and explicitly apply their choice. Browsing previews does not change the home mascot. The selected mascot persists locally on this browser/device, with Kami as the fallback. The home page retains layout and theme controls but has no mascot picker. Settings cannot interrupt an active call. No backend profile, voice or account behavior changes in this slice.
