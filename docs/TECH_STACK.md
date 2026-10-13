# Tech stack: Koe (声)

Everything here is free and needs no credit card. Adding anything not on this page needs the user's approval (CLAUDE.md).

## Frontend
| Tech | Use | Why |
|---|---|---|
| **React + TypeScript** | Dashboard + call UI | User's preference; good for live-updating panels |
| **Vite** | Dev server + build | Fast, simple, deploys to Vercel as-is |
| **Plain CSS** (CSS variables) | Styling | No UI framework needed for one screen |
| **Web Audio API**: `AudioWorklet` | Mic capture → 16 kHz PCM16 chunks | Low-latency audio processing off the main thread; built into browsers |
| **Web Audio API**: `AnalyserNode` | Mascot mouth/scale from voice volume | Built in, no library |
| **Native `WebSocket`** | `/ws/call` (audio) + `/ws/events` (JSON) | Built into browsers |
| **three.js** + **`@pixiv/three-vrm`** (MIT) | 3D anime mascot (VRM model: mouth shapes, blink, gaze, expressions built in) | Standard for anime avatars; ~1.2 ms per frame measured; lazy-loaded chunk (186 kB gzip) |
| **Web app manifest + service worker** (built into browsers) | Install Koe on the phone like an app; receive push notifications | No app store, no card, one codebase |
| **`@phosphor-icons/react`** (MIT) | UI icons (header, call controls, dashboard tabs) | Light weight matches the light type; tree-shaken, only used icons ship. Added 2026-10-13 with Rohit's OK |
| **VRoid Studio** (desktop app, free) | Making the mascot's VRM model | Free, commercial use allowed, exports VRM |

## Backend
| Tech | Use | Why |
|---|---|---|
| **Python 3.13 + `uv`** | Language + package manager | Best AI/Google/Notion libraries; `uv` is already installed (3.13 was already on the laptop; `requires-python >=3.12`) |
| **FastAPI + `uvicorn`** | HTTP routes, webhooks, **WebSockets** | Async, native WebSocket support, so no second server is needed |
| **`google-genai`** (official Google Gen AI SDK) | Gemini Live (web call) + Gemini (WhatsApp, PR summaries) | Official SDK for both the Live API and regular calls |
| **`httpx`** | Calls to GitHub, Notion, WhatsApp APIs | Async HTTP client; one client for all REST APIs |
| **`pywebpush`** (MPL-2.0) | Web Push to the installed Koe app (VAPID, encrypted payloads) | The standard Python implementation; free push services (FCM, Mozilla, Apple) need no account. Added 2026-10-13 with Rohit's OK |
| **`google-api-python-client` + `google-auth-oauthlib`** | Google Calendar + Sheets | Official Google clients; OAuth installed-app flow |
| **`pydantic-settings`** | Config from `.env` | Typed config, fails fast if a key is missing |
| **Neon PostgreSQL + `psycopg[binary]` 3** | Activity, pending actions, memory | Managed storage in Singapore; parameterized SQL and atomic approval functions. Blocking connections run in worker threads so voice stays responsive; works with Windows' default event loop. |
| **`tzdata`** | IANA timezones on Windows | Python's `zoneinfo` needs timezone data; Windows does not ship the IANA database |
| **`pytest` + `respx`** | Tests; fake HTTP APIs | Test logic without hitting real services |

Notion is called with existing `httpx` against the current data sources, pages and blocks REST endpoints (API version 2026-03-11). This keeps Phase 4 free of new dependencies. Sheets uses existing Google OAuth credentials with `httpx` REST calls and RAW append values; Calendar consent remains the default when requesting credentials.

## AI models (IDs verified 2026-10-12; see SERVICES_AND_COSTS.md)
| Need | Model | Why |
|---|---|---|
| Live web voice | **`gemini-3.8-live`** | Speech-to-speech in one model (no separate STT/TTS), streaming, server-side voice activity detection, barge-in, tool calling. Free tier available |
| WhatsApp voice notes + text | **`gemini-3.8-flash`** (standard API) with audio input | Understands audio directly (no separate transcription step), tool calling, free tier |
| PR summaries | `gemini-3.8-flash` | Long context for diffs |
| **Fallback** if Gemini free-tier limits block us | Groq free tier (Whisper STT + gpt-oss LLM) + browser `speechSynthesis` or Gemini TTS | Keeps the project at ₹0 if one provider says no |

### Why speech-to-speech instead of an STT → LLM → TTS chain
A chain waits at each step: speech-to-text, then the LLM, then text-to-speech. Done naively that's 3–5 s. A speech-to-speech model streams audio in and out continuously and starts speaking about 1 s after you stop. That's the core latency decision of this project.

## Integrations
| Service | API | Auth |
|---|---|---|
| GitHub | **GraphQL** search for PR lists (CI, reviews, conflicts, size in one request) + REST API v3 (diffs, commits, comments) + **webhooks** | Fine-grained personal access token; webhook secret (HMAC) |
| Google Calendar | Calendar API v3 (freeBusy, events) | OAuth 2.0 (Desktop app, Testing mode, your account only) |
| Google Sheets | Sheets API v4 (append values) | Same OAuth |
| Notion | Notion API (pages/blocks in one database) | Internal integration token, shared with the target database |
| WhatsApp | **Meta WhatsApp Cloud API** (Graph API): messages, media, interactive buttons, templates + webhooks | System-user/temporary access token, app secret, verify token; **free test number** |

## Dev and ops tools
| Tool | Use |
|---|---|
| `cloudflared` | Free public HTTPS URL to the laptop during development (webhooks) |
| Git + GitHub | Version control (also the test repo for evals) |
| Azure for Students VM + **Caddy** + `systemd` | Production backend (always on, auto-HTTPS) |
| Vercel | Production frontend |

## Rejected (and why)
| Rejected | Why |
|---|---|
| **Node/Express for WebSockets** | FastAPI does WebSockets natively. A second server in a second language means two codebases, shared state across processes, and an extra network hop that *adds* latency |
| **LangGraph / LangChain** | One agent with ≤10 tools; the tool loop is about 30 lines. LangGraph helps long multi-step workflows with checkpoints, which we don't have. It also fits poorly inside a streaming audio session |
| **WebRTC / Pipecat (for now)** | A WebSocket to our backend is simpler and good enough. **Plan B** if measured latency or audio quality is bad: Pipecat with SmallWebRTC |
| **Twilio / phone numbers** | Costs money; no card |
| **Render free (prod backend)** | Sleeps, wipes disk, loses webhooks (see SERVICES_AND_COSTS). Used **temporarily** since 2026-10-13 until the Azure VM (DECISIONS) |
| **Vector DB / RAG** | Not needed; memory is a daily summary in Neon PostgreSQL |
| **Redux / heavy state libs** | One screen; React state + one event stream is enough |
