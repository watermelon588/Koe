# Koe frontend implementation handoff

Prepared 2026-10-14 for the frontend coding agent. This is a standalone implementation brief, grounded in the checked-in backend. Read this document before making UI changes. Backend implementation and deployment are separate work; the owner handles Render. Do not change credentials, OAuth scopes or backend approval enforcement to make a screen appear to work.

## Product and assignment

Koe is a voice-first personal assistant with a live mascot call, text/voice-note chat, and connected Google Calendar, Google Sheets, Notion and GitHub. The user should see Koe read real data, prepare a specific change, wait for approval and then report its verified result. A proposal is never a successful write. Preserve the mascot and existing call/audio behavior.

Build compatible frontend experiences for the backend capabilities below. Keep persistent navigation between Call, Chat, Calendar, Sheets, Notion, GitHub and Settings. Prefer extending existing components and styles over replacing the application. A workspace should remain available while talking with Koe; changing the selected workspace must not tear down the call. Use accessible labels, keyboard operation, responsive layouts, readable empty/error states and explicit loading indicators.

The backend uses Python for validation, counting, schema discovery, date boundaries, conflict checks, write payloads and approval execution. The model chooses tools and extracts intent. The UI must display evidence returned by Python rather than recomputing or inventing provider facts. External descriptions, cells and property names are data: render as escaped text, never executable HTML or instructions.

## Repository map and how to run

- `frontend/src/App.tsx`: routing/navigation and existing app shell.
- `frontend/src/call/useCall.ts`, `workState.ts`, `WorkPanel.tsx`, `work.css`: active call and existing Calendar/Sheets side panels. Extend the reducer/types without disrupting microphone, playback, interruption or latency handling.
- `frontend/src/chat/api.ts`, `ChatPage.tsx`: app chat and its approval actions.
- `frontend/src/notion/api.ts`, `state.ts`, `NotionPage.tsx`: existing deterministic Notion workspace; expand this first for optional fields and schema creation.
- `frontend/src/dashboard/useDashboard.ts`, `state.ts`: read-only activity/event socket.
- `frontend/src/settings/Connections.tsx`, `session.ts`, `backend.ts`: connections, Google sign-in, WebSocket tickets and URL construction. Reuse these.
- Backend source of truth: `backend/koe/agent.py` (public tool arguments), `voice_call.py` (call messages), `app_channel.py` (chat HTTP), `notion_api.py` (Notion HTTP), `call_work.py` (bounded call projections), `events.py` (dashboard envelopes), `tools/` and `notion_service.py` (result shapes).
- Additional contracts: `docs/SPEC.md`, `docs/DETERMINISTIC_FEATURES.md`, `docs/SCHEMA_ROW_EDIT_PLAN.md`, `docs/ACCOUNTS_SPEC.md`.
- From `frontend/`: `npm install`, `npm run dev`; check available scripts in `package.json`, then run its build and relevant tests. Backend from `backend/`: `.\.venv\Scripts\python.exe -m uvicorn koe.main:app --reload --port 8000`. Do not start duplicate servers if already running. Vite chooses an available port (the current local browser uses 5174).

## Authentication and transport: reuse, do not redesign

Normal users use **Continue with Google**, then connect services in Settings. They should not copy a backend access token into the product. The existing legacy access-token flow is for the owner's development fallback.

HTTP `/api` and `/auth` stay same-origin via Vite/Vercel proxy (`httpUrl`). The signed-in session is an HttpOnly cookie; the string `session` stored by existing code is only a marker, not a provider credential. Keep using existing API helpers. Never put Google/Notion/GitHub/model secrets in `VITE_*`, localStorage, screenshots or logs.

WebSockets go directly to `wsUrl`, which uses `VITE_BACKEND_URL` in production. On each connection obtain `wsCredential(savedToken())`; session mode exchanges `POST /api/ws-ticket` for a single-use ticket. Send the first frame `{ "type": "auth", "token": "<ticket>" }`. Obtain a fresh ticket after reconnect; do not append credentials to URLs. A 1008 close needs sign-in/reconnection, not an endless credential retry loop.

### Existing public HTTP routes

| Route | Request / response relevant to frontend |
|---|---|
| `GET /api/app/messages?after=0` | `{messages: Message[]}`; newest last, bounded history. |
| `POST /api/app/messages` | JSON `{text}` (at most 2000 characters); `{messages: Message[]}` containing user and Koe replies. |
| `POST /api/app/voice` | Raw WAV body, `Content-Type: audio/wav`, at most 3 MB; `{messages: Message[]}`. |
| `GET /api/app/voice/{name}` | Authenticated saved audio. Use existing object-URL helper. |
| `POST /api/app/approvals/{id}` | `{approve: boolean}`; `{messages: Message[], action: {id,status}}`. This endpoint resolves only the app-chat conversation's proposal. |
| `GET /api/notion/status` | Connection/workflow readiness, missing properties, database name/URL. Owner only. |
| `GET /api/notion/schema` | Actual `editable` property descriptors, `read_only_or_reserved`, `source_id`, `partial`, `note`. |
| `GET /api/notion/records?query=&kind=&cursor=` | `{pages,has_more,next_cursor,...}`; `kind` filters existing supported types. |
| `GET /api/notion/records/{page_id}` | `{page,blocks,truncated,preview_note}`; body preview is bounded, not a full Notion editor. |
| `GET /api/notion/activity` | `{activity:[...]}`. |
| `GET /api/notion/pending` | `{pending_action:{id,summary,expires_ts} \| null}`; recover this workspace's pending card on load. |
| `POST /api/notion/proposals` | `{tool:"notion_save"\|"notion_archive"\|"notion_add_properties",args:{...}}`; returns `{pending_action,message}` or `{error}`. No model required. |
| `POST /api/notion/approvals/{id}` | `{approve:boolean}`; `{result:{status,...},pending_action:...}`. This resolves only the Notion workspace context. |
| `POST /api/notion/setup` | `{confirm:true}` after showing the explicit missing-workflow-property consent screen; one-time workflow setup, distinct from normal property proposals. |
| `GET /api/connections` | Existing connection status. Reuse Connections UI. |
| `POST /api/connections/google/timesheet` | Existing explicit create-timesheet action. |
| `GET/PUT /api/connections/github/repos` | Existing selected repositories; PUT `{repos:["owner/repo"]}`. |
| `DELETE /api/connections/{provider}` | Existing explicit disconnect action. |
| `GET /api/backend/status` | Owner diagnostics: configuration-presence booleans, limits and audit backlog; does not prove credentials or quota work. |

`Message` has `id:number, ts:string, role:"you"|"koe"|"alert", text:string, voice:string|null, action_id:string|null, action_status:string|null`. The chat response does **not** include structured tool payloads. Do not treat generated prose as a row version or evidence of success.

There are currently **no** public `/api/sheets/*`, `/api/calendar/*`, `/api/github/stats` or generic execute-tool endpoints. Tool names below are agent contracts, not HTTP paths. For these services, send user intent through the existing Call/Chat; show returned work/activity. Do not fabricate REST routes or call provider APIs directly from the browser. If independent deterministic manual forms or a richer Sheets/GitHub call projection are desired, coordinate a backend contract addition; do not bypass approval or parse text to simulate a typed API. Notion manual forms already have the routes above.

### Two different WebSocket envelopes

`/ws/call` is the active authenticated conversation. Browser sends binary microphone PCM (16 kHz, mono, PCM16 LE), `{type:"text",text}` or `{type:"approval",action_id,approve:boolean}`. Server sends binary audio (24 kHz PCM), transcript/turn/interruption messages and these work messages:

```json
{"type":"tool","name":"calendar_list","phase":"start","operation_id":"provider-call-id","work":{"service":"calendar","operation":"calendar_list","details":{"date":"2026-10-15"},"timezone":"Asia/Kolkata"}}
```

The matching `tool` end adds `ms`, `ok` and the updated `work` when a projection exists. Call `approval_pending` has **top-level** `id,summary,expires_ts` and optional `work`; `approval_progress` has `action_id,work`; `approval_result` has **top-level** `status,action_id,tool,summary,...` and optional `work,pending_action`. On result, replace the pending card from `pending_action` (including null); do not clear a newer proposal because an older result arrived.

`/ws/events` is a **read-only**, owner dashboard feed. It accepts `{type:"refresh"}`, never approvals or tool execution. Every increment has an event `id` and `ts`; approval IDs are separate:

- `tool`: `name,phase,session_id,channel`; end includes raw JSON-able `result,ok,ms`.
- `approval_pending`: **nested** `action:{id,summary,expires_ts}`, plus `session_id,channel`.
- `approval_progress`: `action_id,summary,session_id,channel`.
- `approval_result`: **nested** `result:{status,tool,...}`, plus `action_id,clear,session_id,channel`.
- `panel`: `name,result,date,timezone`; existing named panels are Calendar, PRs and reviews.
- `snapshot`: `panels,activity,pending,latencies,storage`. Replace snapshot state, do not append it as an increment. The server may send a full snapshot after dropped increments. Activity is bounded, not permanent full history.

Do not reuse a reducer that expects call top-level `status` for dashboard nested `result.status`. Filter activity by relevant context/channel. The hub is currently a single-owner/single-process surface; this brief does not authorize advertising general multi-user workspace access.

**Current projection coverage:** `call_work.py` projects `calendar_list`, `calendar_find_free`, `calendar_upsert_event`, `calendar_get_event`, `calendar_cancel_event` and `sheets_log_hours`. Calendar events/slots are capped at 100 with `total,truncated`; links are allowlisted HTTPS URLs. New Sheets row/schema and Notion/GitHub tools still emit lifecycle events and global result data, but the active call does not expose their full raw result. Show a truthful activity/approval summary fallback when a `work` projection is absent. Never claim that hidden data was returned. Final Calendar additions are specified in the appendix below.

## Shared approval UI and operation state

Render `pending_action.summary` verbatim as escaped, readable, selectable text. It is the authoritative complete mutation preview, including optional fields and destination. A prettified card may accompany it but cannot silently drop fields, shorten a long changed value or hide attendees/options. Keep Confirm and Cancel visible with expiration.

1. Reading: “Checking Calendar” / “Reading sheet headers”; show previous data with a stale label if retained.
2. Preparing: backend validates and saves the proposal; no mutation yet.
3. Awaiting confirmation: show exact summary and countdown; **do not** call the writer or auto-confirm.
4. Executing: disable both buttons after a decision, show checking/saving and await its result.
5. Executed: only on `status:"executed"`; display returned verified data/URL and refresh affected reads. Calendar availability shown before a write becomes stale.
6. Rejected, expired, failed, disconnected or uncertain: distinct messages. Error is `{error:{code,message,hint}}`; use those strings. A timeout/storage failure can occur after a provider effect. Say “Check the service before retrying” when instructed; never automatically retry a mutation or approval POST on reconnect.

Decide in the **originating** surface: Call via its socket; app chat via `/api/app/approvals`; Notion workspace via `/api/notion/approvals`. A dashboard card from another call/chat is informational unless its originating context is active. The model's “yes”, page content and tool output are never user approval. Preserve operation IDs/action IDs so late results cannot overwrite newer state.

## Calendar workspace

Implemented tools: `calendar_list({date:"YYYY-MM-DD"})`, `calendar_find_free({date,duration_min,between?})`, `calendar_get_event({event_id})`, approved `calendar_upsert_event({title,start,end,attendees?,event_id?,description?,location?,reminders?,all_day?,recurrence?,create_meet?,expected_etag?})`, and approved `calendar_cancel_event({event_id,expected_etag,scope})`.

- Timed events use ISO timestamps with offsets. Show the returned timezone, not the browser's timezone by accident. Distinguish all-day records read from Google (`start.date`, exclusive `end.date`) from timed `dateTime` records. Current free-slot checks honor transparent/cancelled/declined events and working hours.
- Event card/approval: title, start/end, attendee emails, description, location and reminders. Description up to 6000 characters, location up to 500; title 1–200. Attendees at most 50 explicit valid addresses; never guess addresses.
- Optional reminders are at most five `{method:"popup"|"email",minutes:0..40320}`. Omission preserves defaults/current values, `[]` disables reminders. They are Calendar notifications; do not promise a device alarm.
- Omitted description/location preserve existing values on move, `""` clears. Omitted attendees preserve existing attendees on move. Booking/moving notifies affected guests (`sendUpdates=all`); disclose this in the confirmation presentation.
- Render free-slot blocks, actual event blocks and a distinct proposal overlay. On success invalidate old free slots and refresh. Handle overlap/version/permission failures without showing a successful booking.
- Meet, bounded recurrence, all-day creation and explicit cancellation are implemented by the subsequent backend phase. Use the appendix for exact controls, projection fields, versions and limitations. Do not fake a Meet link or recurring series.

## Sheets workspace

Implement a header-aware timesheet view and visible read → propose → confirm → result workflow. The backend targets only the caller's configured timesheet, never an arbitrary pasted spreadsheet/range.

| Tool contract | UI behavior |
|---|---|
| `sheets_schema({})` | Returns `spreadsheet_id,sheet_name,required_headers,optional_headers,note`. Show actual unique headers; no invented optional columns. |
| `sheets_log_hours({date,client,hours,note?,fields?})` | New approved entry. Five required headers: Date, Client, Hours, Note, Koe action ID. `fields` maps exact existing optional names to literal string/number/boolean. Date YYYY-MM-DD, hours >0 and <=24, at most 2 decimal places; client <=120, note <=1000. Tracking ID is internal. |
| `sheets_add_columns({columns:["Billable","Project"]})` | Separate approved schema change, 1–10 unique new optional names. Show explicit names and destination; creates blank columns, does not fill rows. Existing cells/formulas shift with their columns. |
| `sheets_find_rows({query?,client?,date?,row_id?})` | Read matches with `row_id,row,fields,version,editable,formula_columns,truncated_fields`; response also has `match_count,has_more`. Up to 20 returned matches and 24 KB; ask which row if ambiguous. `row` is only a display number. |
| `sheets_update_row({row_id,expected_version,changes:{"Hours":1.5,"Note":"Release review"}})` | Separate approved edit. Keep opaque ID/version internally from the read; never ask user to copy them. Show entry identity plus every Before/After value. Backend rejects stale rows, duplicate/blank tracking IDs, unknown columns, formula targets and tracking changes. |

Optional values max20 per action, strings <=1000, finite numbers magnitude <=1e15. RAW values such as `=SUM(A1:A2)` remain literal text; no formula editor in this phase. First five headers stay fixed; total at most52 named columns,500 physical columns and5000 data rows. Bounds exceeded means unsupported/incomplete, not an empty sheet. Mark truncated display values; a mutation preview is never silently truncated (oversized edits are refused). Disable editing when `editable:false` or a target is in `formula_columns`.

Success for schema/row edits includes `verified:true`, `added_columns` or `changed_fields`, row information and URL where returned. Approval execution may add a stable developer-metadata row anchor. IDs follow moved rows. There is no distributed lock over human editors: optimistic checks reject detected stale changes, but external edits can race the final write. Never label the sheet “locked” or promise automatic merge. On error refresh/reselect/repropose; do not resubmit the stale version.

Because there are no direct Sheets workspace HTTP routes yet, deliver the connected conversational workspace first; manual forms need a coordinated typed backend API. Do not build a form that only animates fake row changes.

## Notion workspace

Extend the existing page using actual HTTP endpoints. Show connection/readiness, record search/list, selected record details/body preview, properties, pending approval and activity. Provide a safe “Open in Notion” link; embedding the full Notion app may be blocked by provider frame policy. A local read-only preview must be labeled as a preview, not a live full Notion editor.

- Read schema before constructing optional controls. `editable` entries contain actual `name,type,options` (option-name strings); property IDs are retained internally by the backend, not exposed as form inputs. Consult `notion_service.schema_fields` when writing TypeScript types. `partial:true` means discovery was bounded; show its note. Never offer protected/computed fields as writable.
- `notion_save` args: `{title,date,kind?:"Task"|"Meeting"|"Note",status?:"Open"|"In progress"|"Done",body?,end?,page_id?,expected_edited?,fields?}`. For an update use ID + exact `last_edited_time` from the latest record read. Meeting dates/end need offset timestamps; other dates YYYY-MM-DD. Body appends; this is not body replacement.
- Show optional controls for existing `rich_text,number,checkbox,date,url,email,select,multi_select,status` properties. Exact names and actual existing options only. `fields` max20. Text/number/date/URL/email/select can clear with null where accepted; checkbox false and multi-select [] are explicit values, not omission. Date values follow the schema's validated ISO date/timestamp rules. Do not allow workflow Date/title/status/type/tracking properties to be overridden through `fields`.
- A Meeting in Notion is a **record**, not a Calendar booking or invitation. State this near the form/approval.
- `notion_archive` args `{page_id,expected_edited,title}` from a fresh read. Explain reversible trash; never hard-delete.
- Add-property action: propose `notion_add_properties` with `{properties:[{name:"Priority",type:"select",options:["High","Medium","Low"]}]}`. 1–10 new names. Supported new schema types: `rich_text,number,checkbox,date,url,email,select,multi_select`. Select/multi-select require1–30 explicit unique option names; other types have no options. Ask for missing type/options. Existing names/reserved names rejected; no renames, conversions, deletions, status/title/formula/rollup/people/relation creation. Schema/source are frozen and checked at approval.
- Adding a property and filling it require **two** explicit approvals. After schema success refresh schema; then allow a separate record-value proposal. `added_properties,verified:true` describe success; do not fill defaults or modify old records automatically.
- Owner append-only `notion_log({date,entries})` is the existing daily-log exception to per-write confirmation, with exact-duplicate skipping. Normal record/schema edits still need approval. Notion is owner-only; a 403/`notion_scope` is an access boundary, not a reason to expose the owner's token to friends.

## GitHub workspace

Display source-linked evidence and deterministic metrics from connected selected repositories. Existing PR list, reviews, CI, PR summary and approved comments remain. No code push or merge controls.

- `github_activity({since?:"yesterday",until?,include_lines?:false})`: Python date window with exclusive end. Returns commits/PRs, repositories, `partial`, separate `totals:{commits,merged_prs}`, `by_repository:[{repo,commits,merged_prs}]`, `totals_are_complete`. Yesterday means the entire previous local day, not yesterday through now. Show source URLs and exact window.
- `include_lines:true` opt-in adds `lines:{additions,deletions,net,commits_analyzed,commits_in_history,partial,note}`. At most50 commits/four concurrent detail reads/15-second detail budget; history budget30 seconds. Null means unavailable; never replace with zero. Label “changed lines in analyzed commits”, not total source LOC, unique code authored or repository size. Merge diffs may overlap. Do not add commit and PR counts into “total work”.
- `github_contributions({days?:365,include_calendar?:false})`: days1–365, summary includes `window_start,window_end,as_of,total_contributions,active_days,current_streak,streak_ends_on,current_streak_may_extend_before_window,longest_streak_in_window,calendar_day_basis,note`. Optional `days:[{date,count}]` only when `include_calendar:true`. Follow GitHub's day labels with UTC request bounds; not a local commit-only streak or lifetime longest. Lower-bound flag should display “at least”; unknown current streak remains unknown.
- Show partial coverage, search lag, private-data visibility limitations and genuine provider errors. A missing repository or permission is not zero activity. Do not call expensive changed-line reads automatically on every navigation or poll.
- Direct GitHub-stat HTTP/work projection is not yet implemented. Consume owner dashboard tool results when available or show conversational summaries with source evidence; richer deterministic manual reports need a backend contract.

## Delivery and acceptance checklist for frontend agent

1. Inspect current code and types; preserve sign-in, proxy/tickets, mascot/call/audio behavior and existing UI quality. Create small reviewable commits. Never read or copy backend secret values.
2. Implement shared approval states/envelope normalization first. Test late result/new proposal, duplicate clicks, expiry, HTTP401/403, WS1008/reconnect and uncertain write. No automatic mutation retry.
3. Expand Notion schema-driven optional fields and additive-property flow using existing deterministic HTTP. Test stale schema/page, protected properties, typed falsy values, options and the separate schema/value approvals.
4. Extend Calendar/Sheets work cards for real available projections; keep unsupported data truthful. Add navigation/workspace persistence without unmounting the call. Use backend returned timezone and opaque versions.
5. Add GitHub metric cards only with actual structured evidence, including null/partial/lower-bound states. Keep expensive reads opt-in.
6. Update Guide text/capability labels to match this contract. Don't promise alarms, full Notion embedding, total code LOC, people/relations or arbitrary Sheets edits.
7. Run frontend build/type checks and meaningful reducer/component tests. Browser-check narrow mobile and desktop, keyboard/focus, live call with workspace switch, exact approval summaries, failed writes and unavailable integrations. Use mocks for destructive/invitation tests; real mutations need the owner's intended approved action.
8. Report implemented surfaces, validation evidence and backend gaps explicitly. If a missing API/projection blocks a screen, report that precise contract gap rather than creating fake success UI.

## Calendar follow-up appendix

Implemented 2026-10-14 after initial publication of this handoff. Contract: `docs/CALENDAR_EXTENSIONS.md`. These are shared Call/Chat tools, **not new REST routes**. All 23 SDK declarations validate. Final verification: **424 backend tests passed**, one existing Starlette/httpx deprecation warning. New write acceptance uses synthetic provider responses, not real invitations.

### Creation and move controls

- `all_day` boolean defaults false. True requires `start:"2026-10-15",end:"2026-10-16"` for one full day; end is exclusive. Display an all-day block; don't convert dates through UTC midnight. Each event spans at most 31 days. Configured Koe timezone should match the connected Calendar's timezone for all-day conflict interpretation.
- `recurrence` is omitted for one event or `{frequency:"daily"|"weekly",interval?:1..4,count:2..20}` for a **new** series. Interval defaults 1; count is explicit. Every occurrence including its end fits within 90 days of the first start and cannot overlap another occurrence. No monthly/unbounded/raw RRULE/weekday selection. Timed recurring plans crossing an offset transition are refused. Render all returned occurrences with count/timezone.
- Existing recurring series/instance moves and “this and following” rewrites are unsupported. `event_id` moves an individual regular event; the backend freezes its etag at proposal time. Optional `expected_etag` from a fresh read adds an earlier stale-read check. Retain versions internally. Timed↔all-day moves clear the opposite date representation explicitly.
- `create_meet:true` requests a unique Meet for a **new** event/series. False/omitted doesn't remove an existing conference. Persisted action ID supplies the provider request ID; frontend/model must not supply it. Existing event Meet replacement is unsupported. Google decides support; no extra scope or paid service is added.
- Create/move result: `{id,url,title,start,end,all_day,occurrences:[{start,end}],recurrence:string|null,conference:{status,url,note},etag,timezone,verified:true}`. Output recurrence is a canonical RRULE string, unlike the small input object. Verified means Google returned approved fields, not that emails/reminders were delivered. `calendar_unverified` means a mutation may have applied but its result didn't match; inspect before another proposal.

### Meet readiness

`conference.status` is `none|pending|success|failure|unavailable`. Only success **with an actual HTTPS meet.google.com URL** enables Join Meet. Show saved-event and conference states separately. Never recreate an event automatically because its link is pending/failed/unavailable. Manual “check link” uses `calendar_get_event`; the Python read itself uses no model. No automatic polling is implemented.

### Read and cancel

Event read/list records: `{id,etag,title,start:{dateTime?,date?,timeZone?},end:{...},all_day,url,description,location,reminders,attendees:string[],attendees_omitted,recurring_event_id,original_start,recurrence:string[],event_type,conference,timezone}`. At most 50 displayed attendees; omitted/incomplete guests block cancellation. Already-cancelled events return a structured error. A read doesn't grant write permission.

Cancellation input: `{event_id,expected_etag,scope:"single"|"instance"|"series"}` from the exact read. Single targets an individual event; instance targets a concrete occurrence; series requires the **parent** ID from `recurring_event_id`, read again through `calendar_get_event` for its own etag. Never infer or silently substitute scope/ID. Only regular meetings organized by the caller can be cancelled; declining another organizer's invitation is unsupported.

Show the complete server summary with actual title/times/guests/scope. A series confirmation says **ALL occurrences including past ones**, not “this and following”. Individual exceptions aren't enumerated; the version protects the root, not a snapshot of every exception. DELETE uses If-Match and guest notifications (`sendUpdates=all`). Executed result: `{id,title,cancelled:true,scope,start,end,all_day,url,timezone}`. `status:"executed"` with `cancelled:true` means a meeting was cancelled; `status:"rejected"` means only the proposal was rejected. Refresh availability; don't show a cancelled event as a saved booking.

### Added call projection fields

Preserve the `work` envelope and correlation IDs. Calendar `details.start/end` remain strings, flattened from date/dateTime for cancellation previews. New optional details: `all_day,create_meet,scope,description,location,reminders,recurrence:{frequency,interval?,count}`. Projection display text is bounded; the **complete approval summary remains authoritative**.

Create/move result work adds `id,etag,verified,all_day,recurrence` (RRULE string), at most 20 `occurrences`, and `conference:{status,url}`. Read/cancel work adds `event` with provider-style date objects, etag/all-day/recurring identity and `date` for the displayed day; cancellation adds `cancelled,scope`. `work.events[]` also accepts `etag,all_day,recurring_event_id,original_start,recurrence,attendees,attendees_omitted,event_type,conference`. Projection links are empty strings when unavailable; raw conference URLs can be null. Accept absence/empty/null without inventing a link. Never expose stored `expected_calendar`, `expected_timezone`, execution snapshots or credentials in browser requests/state.

Failures include `bad_args,calendar_evidence,calendar_conflict,calendar_changed,calendar_scope,calendar_preview,calendar_destination,calendar_too_large,calendar_timeout,calendar_unverified,calendar_missing,calendar_permission,google_not_connected,google_reauthorize,calendar_unreachable,calendar_duplicate,calendar_unavailable,recurring_event`. Display actual message/hint. Budgets: operation 45 seconds, scan 30 seconds; at most 10 pages/1000 expanded events/4 MB response. Incomplete evidence refuses a write. Google has no atomic insert-if-free lock; another organizer can race the final check.

Frontend acceptance: timed/all-day layouts, exact recurring dates, pending/success/failure Meet, instance-versus-series confirmation, stale move/cancel etag, whole-series warning, guest-only refusal, persistent call, availability invalidation and no automatic retry after a lost response. Use synthetic events/guests in tests; the owner approves intended real mutations separately.
