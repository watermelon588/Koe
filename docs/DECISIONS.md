# Decision log: Koe (声)

Add a row for every decision that changes scope, stack or behavior. Newest at the bottom.

| Date | Decision | Why | Alternatives rejected |
|---|---|---|---|
| 2026-10-12 | Build a **dev-day agent** for a developer founder (GitHub-centric) | The user lives this problem daily, so the demo is honest | On-call incident agent; client bug hotline |
| 2026-10-12 | Name: **Koe (声)**, meaning "voice" | Short, anime-flavored, says what it is. `koe-agent` free on PyPI and npm (2026-10-12) | Kotodama, Shikigami, Kuchiyose |
| 2026-10-12 | Budget **₹0, no card** | User constraint | — |
| 2026-10-12 | **No phone-network calls** | Twilio trial expires after 30 days; paid plans need a card | Twilio, LiveKit US number (inbound only) |
| 2026-10-12 | Channels: **web call with mascot** (desk) + **WhatsApp** (on the move) | Free, two-way, matches the user's day | Phone, Telegram, Linphone SIP |
| 2026-10-12 | **Gemini Live speech-to-speech** for web voice | Lowest latency, free tier, built-in tool calling | STT→LLM→TTS chain (slower) |
| 2026-10-12 | **FastAPI only** (WebSockets included) | One server, no extra hop | Node/Express for WebSockets |
| 2026-10-12 | **No LangGraph** | ≤10 tools, one agent; a plain loop is enough | LangGraph, LangChain |
| 2026-10-12 | **Drop site uptime monitoring** | User decision: polling wastes free resources; GitHub webhooks are event-driven | 60 s uptime checker |
| 2026-10-12 | **GitHub is the core feature** + webhook alerts to WhatsApp | User priority | — |
| 2026-10-12 | **No merge-by-voice** | Misheard command = shipped bug | Merge with approval |
| 2026-10-12 | Prod backend on **Azure for Students VM**, frontend on **Vercel** | Always on, persistent disk, no card for students | Render free (sleeps, wipes disk), Koyeb/Railway/AWS/GCP (card) |
| 2026-10-12 | SQLite for state and memory | Single user; stdlib | Postgres, vector DB |
| 2026-10-12 | Output style: **Explanatory** | User choice in the first build session: Claude writes the code, explains each step in chat and BUILD_LOG | Learning (`TODO(human)` pieces) |
| 2026-10-12 | **Python 3.13** (not 3.12) | Already installed; all deps resolve on it; `requires-python >=3.12` | Download a uv-managed 3.12 |
| 2026-10-12 | Models: **`gemini-3.8-live`** (call), **`gemini-3.8-flash`** (WhatsApp, PR summaries) | Current stable + free tier per official docs; 2.5 is closed to new users | `gemini-3.8-live-extended-thinking` (adds reasoning delay), 2.5 native-audio |
| 2026-10-12 | Phase 0 smoke tests are **one script** (`backend/scripts/smoke.py`) with a function per service, skipping services with no keys | One command to re-check everything; fewer files | Five separate scripts |
| 2026-10-12 | **Start Phase 1 before Google OAuth is set up** | Phase 1 only needs Gemini Live (verified); Calendar isn't used until Phase 2 | Block Phase 1 on every smoke test passing |
| 2026-10-12 | Keep **WhatsApp**; Rohit adds funds to Meta (exception to "no card" for this one service) | User choice over Telegram / web-only | Telegram bot, web app only |
| 2026-10-12 | ⚠️ Funds added (₹100), but WhatsApp still blocked: Meta requires **business verification** | Evidence in SERVICES_AND_COSTS.md. Next step pending a user decision; doesn't block Phases 1–4 | — |
| 2026-10-12 | **WhatsApp parked**; continue Phase 1 | User will sort out Meta business verification (or switch to Telegram) later. Phases 1–4 don't need it | Block on WhatsApp now |
| 2026-10-12 | **UI exploration:** 5 static variants in `frontend/design/`; Hibiki and Kotoba dropped by the user, Kasumi, Ma and Utsuwa kept until the mascot is in; fonts **Geist, Geist Mono, Noto Serif JP** (light weights) via Google Fonts | User wants a light, minimal UI with lightweight fonts; mockups first, then port the chosen one to React. Fonts are free | Building directly in React; Inter (ElevenLabs' font) |
| 2026-10-12 | Mascot tech: **3D VRM** (three.js + `@pixiv/three-vrm`, model from VRoid Studio); pixiv sample model as a placeholder | Measured no latency cost (1.2 ms/frame, task-queue delay unchanged); VRM ships mouth/blink/expressions, so lip sync is ~10 lines | 2D AI-generated pose sprites (characters drift between images, flipbook look), Live2D (manual rigging, license caveat for avatar apps), Rive (`.riv` export is paid), Spline (no face rig, heavy runtime), image-to-3D (no face blendshapes, paid credits) |
| 2026-10-12 | Phase 5 webhooks built **in parallel with Phase 2** (separate agent session, separate files) | Webhook verify + GitHub alert rules need no agent core; WhatsApp sends are blocked anyway, so built and tested against fakes | Waiting for Phase 2 to finish |
| 2026-10-12 | CI alerts from **`workflow_run` only**; "my PR" = I triggered the run; delivery dedupe **in memory** until `store.py` exists | Actions sends both `check_suite` and `workflow_run` for one failure (double alert); `workflow_run.pull_requests` has no author field | Both events; one extra API call per run to fetch the PR author |
| 2026-10-12 | GitHub PR-list tools use **GraphQL search** with one reused `httpx` client | One request instead of ~3 per PR; reusing the TLS connection cut a tool call from 3.1–4.3 s to 0.8–1.7 s (measured) | REST per-PR calls; new client per call |
| 2026-10-12 | Mascot moods are **code-driven** (expressions + head/eye pose from `/ws/call` events), not animation files | Small and subtle as asked; no license or file-size cost; works with any VRM | pixiv's free `.vrma` pack (forbids extractable redistribution, i.e. a public site), Mixamo (Adobe account, FBX retargeting) |
| 2026-10-12 | Ship **two** mascot models, user-selectable: **miku** (default) and **kami**; retire akane + pixiv sample | Rohit's pick; miku is also the cheapest per frame (2.5 ms p50, 15 hair chains) | akane (4.5 ms p50), one fixed model |
| 2026-10-12 | **7 UI directions** (Kasumi, Ma, Utsuwa + Mizu and Monogatari for Miku, Kagura and Gin for Kami), each a static page with the real mascot in a **three-quarter shot** and the **real call**; listed on the home route | Rohit wants to see each UI with the actual mascots before choosing one; static pages keep the React app untouched until then | Port all 7 to React now; head-and-shoulders framing |
| 2026-10-12 | Mascot interaction in code: pointer gaze, tap reactions, drag to turn | Rohit wants her to feel real; uses the existing three.js + three-vrm, raycast only on tap so per-frame cost is unchanged | VRMA animation files, physics drag |
| 2026-10-12 | **UI reset:** the 7 static variants are deleted; the home route has **two layouts** (Shoji, Engawa) × dark (default) / light, **kami default**, flat backgrounds, light type, mascot to one side | Rohit: gradients distracted from the mascot; wants a dark, minimal UI with her as the focus | Keep refining the 7 variants |
| 2026-10-12 | Mascot on **one full-window transparent canvas**, placed by the camera (view offset + dolly between half and full figure) | Panels animate with transform only and the WebGL canvas never resizes during a transition | A canvas inside each panel (two renderers, or resizing during the animation) |
| 2026-10-12 | **Chat** = Gemini Live audio transcription (both directions) + typed text into the same Live session | No second model or endpoint; transcripts come free with the session | A separate text model for chat; a transcript-only panel with no typing |
| _pending_ | Mascot name | Decide at the start of Phase 3 | — |
| 2026-10-12 | Phase 2 storage uses **Supabase PostgreSQL**, replacing SQLite; existing async `httpx` calls the REST API and restricted SQL functions | User wants managed storage that survives hosting and a future Supabase Auth option; relational approvals plus JSONB payloads fit | MongoDB Atlas; server-local SQLite |
| 2026-10-12 | Confirmation is bound to one pending action in one conversation; only explicit user yes/no or a UI action resolves it, never a model-supplied approval argument | Prevent model/tool output from authorizing a write; atomic database claims prevent concurrent executions | An approval tool callable by the model |
| 2026-10-12 | Add CPython-maintained `tzdata` for `zoneinfo` on Windows; bring `/ws/call` app-token authentication forward into Phase 2 | Windows has no IANA timezone database; the new Calendar writer needs access protection immediately | Fixed UTC offsets; leaving a write-capable call unauthenticated |
| 2026-10-12 | Continue with Phase 3 dashboard while Phase 2 live setup waits for the user; use authenticated, bounded in-process events and existing read tools | User explicitly asked to keep building without credentials. One server process needs no extra dependency; missing services must remain visible rather than showing fictional data. Approval controls stay on the original call socket | Block all progress on secrets; add Redis; approve writes on a read-only dashboard socket |

## Frontend decision — 2026-10-12: profile mascot selection

Use a dedicated hash route (`#settings`) and a shared four-mascot catalog without adding a router dependency. Keep the applied mascot in App state and `koe-mascot` localStorage; keep the preview choice local to Settings. Ignore old `?model=` selectors so only Settings changes the preference. Mount one WebGL renderer at a time, shared through a small lifecycle component, and release it when leaving a page or switching models. Keep themes and layouts on Home. Existing voice, token and approval behavior stays intact.

## Frontend decision — 2026-10-13: visual inspection studio

Follow-up: vertical panning is removed. Pointer dragging changes rotation only, and Up/Down no longer shifts the camera. Keep the measured vertical center fixed to prevent users from dragging the figure out of the pane, including when zoomed. Left/right keyboard rotation, Home reset, turntable and zoom remain.

Replace the first text/card-heavy Settings layout with one adaptive studio, real VRM screenshot thumbnails, and an overlay toolbar. Full-body view expands the same canvas rather than opening a second renderer. Add explicit inspection mode to the renderer for actual mesh-bound framing, persistent rotation, vertical pan and zoom; Home keeps its existing framing and drag spring-back. Use CSS expansion with accessible focus containment, inert background navigation and Escape restoration. Keep direct touch interactions and one wave button; remove separate expression and call-mood control rows. No dependency or backend changes.

## Phase 4 decision — 2026-10-13
User confirmed Sheets with approval before every entry. Implement the five tools already listed in the plan using existing httpx/Google libraries. Extend the shared atomic approval gate for PR comments and timesheets; show complete text and bind the destination. Use current Notion data sources, append-only daily bullets and exact-entry deduplication, with one worker. Bound PR source JSON to 30,000 UTF-8 bytes, disclose incomplete evidence and keep the summarizer tool-free. Credentials can remain deferred: all development verification uses fake API boundaries; no real writes are authorized by this implementation task.

## Mascot framing and poses — 2026-10-13
| Date | Decision | Why | Rejected |
|---|---|---|---|
| 2026-10-13 | Home half figure = hair to waist, standing behind a **desk card** (bottom 24% of the stage) | Rohit: the screen edge cutting her body looked like a misplacement; a deliberate object hides the cut | Screen edge crop; a fade-out mask |
| 2026-10-13 | Import **VRoid Studio `.vroidpose`** files as idle poses (bundled from `src/mascot/poses/`) | VRoid exports poses as JSON quaternions; no new dependency, works on every VRoid model | `.vrma` + `@pixiv/three-vrm-animation` (new dependency; pixiv's free pack forbids extractable redistribution), Mixamo (Adobe account, retargeting) |
| 2026-10-13 | Kami runtime model replaced by the 22:22 re-export; the previous one kept as `frontend/assets/mascot/kami-2044.vrm` | Rohit updated Kami in VRoid | — |
