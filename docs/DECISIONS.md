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
| _pending_ | Mascot design + name | Decide at the start of Phase 3 | — |
