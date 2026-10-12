# Services and costs: Koe (声)

**Budget: ₹0. No credit card.** Every service below is free *and* needs no card. Figures were researched 2026-10-03 to 2026-10-12 and many come from third-party sources, so **re-verify on the official page when you first set each one up** and update this file.

## Summary
| Service | What we use it for | Free? | Card? | The catch |
|---|---|---|---|---|
| Gemini API (Live + Flash) | Voice brain, WhatsApp brain, PR summaries | ✅ Free tier | No | Rate limits (not published; see AI Studio → Rate limit page); only a few concurrent Live sessions; Live audio sessions 15 min, connections about 10 min (use session resumption; tokens valid 2 h); **Google may use free-tier data to improve its products**, so don't say secrets on calls |
| GitHub API + webhooks | Core feature | ✅ | No | API rate limit 5,000 req/h with a token, which is plenty |
| Google Calendar + Sheets API | Scheduling, timesheet | ✅ | No | OAuth app in **Testing** mode: refresh tokens may expire after **7 days**, so re-login weekly (or publish the app later) |
| Notion API | Daily dev log | ✅ | No | Share the database with the integration, or it can't see it |
| Meta WhatsApp Cloud API | Mobile channel + alerts | ✅ with the **test number** | No | Only up to **5 registered recipients**. Custom templates need Meta approval. From **Oct 1, 2026** service replies are reportedly billable beyond about 1,000 free/month/number (sources disagree), so we're far below that. **Business-initiated *calls* are paid**, so we don't use them |
| Groq (fallback only) | Whisper STT + LLM if Gemini blocks us | ✅ | No | Daily request and audio caps |
| cloudflared quick tunnel | Dev webhooks | ✅ | No account | URL changes every run, so update the webhook URLs |
| Vercel | Frontend hosting | ✅ Hobby | No | Fine for a static React app; no WebSockets server, which we don't need there |
| **Azure for Students** | Backend hosting (prod) | ✅ **$100 credit + 12 months of free services**, renewable yearly while a student | **No** | Must be a full-time university student; verify with college email or the GitHub Student Pack |

**Expected spend: ₹0.**

## Why voice can be free here
Voice agents are usually expensive because they chain three paid services: speech-to-text, an LLM and text-to-speech, together about $0.07–0.25/min at market rates. We use **one speech-to-speech model (Gemini Live) on its free tier** instead. It's lower latency *and* free, within rate limits, for a single user.

## Hosting: why Azure and not Render
The backend must be **always on**: GitHub webhooks time out after about 10 s and aren't retried automatically, WhatsApp messages would be delayed, and the live call needs a persistent WebSocket.

| Option | Card? | Verdict |
|---|---|---|
| Render free | No | ❌ Sleeps after 15 min idle (about 1 min to wake) · 512 MB · filesystem wiped on restart (SQLite lost) · WebSocket support on free is disputed |
| Vercel | No | ✅ Frontend only (no persistent processes or WebSockets) |
| Koyeb, Railway | Yes | ❌ Card verification |
| AWS / GCP / Oracle free tiers | Yes | ❌ Card or billing account |
| Heroku / DigitalOcean (Student Pack) | Yes | ❌ Card on file |
| **Azure for Students** | **No** | ✅ Small Linux VM, always on, persistent disk, free DNS name `*.cloudapp.azure.com`, Caddy for free HTTPS. Covered by the free 12-month services and/or the $100 credit. **Confirm the VM size and cost in Azure's pricing calculator at signup** |

Development (Phases 1–6) runs on the laptop + cloudflared at ₹0. Azure is needed only for Phase 7.

## Verified Gemini facts (2026-10-12, official pages)
| Fact | Value | Source |
|---|---|---|
| Text/audio model (WhatsApp, PR summaries) | `gemini-3.8-flash` (stable, free tier) | ai.google.dev/gemini-api/docs/models · /pricing |
| Live voice model (web call) | `gemini-3.8-live` (stable, free tier). Also `gemini-3.8-live-extended-thinking` (slower, more reasoning) | same |
| Cheaper fallback | `gemini-3.5-flash-lite` (free tier) | same |
| Live audio formats | in: PCM16 16 kHz mono LE · out: PCM16 24 kHz mono LE | /docs/live |
| Live session limits | audio-only session 15 min · connection about 10 min · GoAway sent before close · resumption token valid 2 h · context window compression → unlimited | /docs/live-api/session-management |
| Free-tier RPM/TPM/RPD | **Not published in docs**; shown per account in AI Studio's rate-limit page | /docs/rate-limits |
| Free-tier data use | "Used to improve our products: Yes" | /pricing |
| 2.5 models | Access limited to past users; use 3.5/3.8 for new projects | /docs/models |

## Rate-limit plan
- Single user, so concurrency is 1–2 sessions.
- Log every `429`/quota error to the activity feed. Back off and retry once, then tell the user in voice or text: "Gemini's free quota is busy, try again in a minute."
- If limits block real use, switch the WhatsApp brain to Groq (fallback), and keep Gemini Live for calls.

## Accounts the user creates in Phase 0 (all free, no card)
1. Google AI Studio → Gemini API key.
2. Google Cloud project → enable Calendar + Sheets APIs → OAuth consent (External, Testing, add yourself as a test user) → Desktop OAuth client → `credentials.json`.
3. Notion → internal integration → token → create the "Koe Daily Log" database → share it with the integration.
4. GitHub → fine-grained token (selected repos: Pull requests R, Contents R, Checks R, Issues/PR comments R/W, Metadata R) + a test repo for evals.
5. Meta for Developers → app → WhatsApp → test number, add your phone as a recipient, temporary token, app secret, set verify token.
6. (Phase 7) Azure for Students, verified with college email or the GitHub Student Pack.
