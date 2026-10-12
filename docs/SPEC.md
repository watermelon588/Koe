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
| **Web call** | User ⇄ Koe, live audio | Browser ⇄ FastAPI over WebSocket (`/ws/call`), PCM16 audio | Gemini Live native-audio model (speech-to-speech, tool calling) |
| **Dashboard events** | Koe → browser | WebSocket (`/ws/events`), JSON | — |
| **WhatsApp in** | User → Koe | Meta webhook `POST /webhooks/whatsapp` (text, audio, button replies) | Gemini (standard) with audio input |
| **WhatsApp out** | Koe → User | Meta Send API (text, interactive buttons, templates for alerts) | — |
| **GitHub events** | GitHub → Koe | Webhook `POST /webhooks/github` (HMAC-SHA256 verified) | none (rules decide what to alert) |

**Allowed WhatsApp senders:** only numbers in `ALLOWED_WHATSAPP_NUMBERS` (env). Everything else is ignored and logged.

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
| `check_suite` / `workflow_run` completed | conclusion = failure, on a PR authored by me | 🔴 CI failed on #N (repo): failing check name |
| `pull_request` review_requested | requested reviewer = me | 👀 X requested your review on #N |
| `pull_request` closed + merged | author = me | ✅ #N merged |
| `pull_request_review` submitted | on my PR, state = changes_requested | ✏️ Changes requested on #N by X |

Alerts outside the 24-hour WhatsApp window use one approved **template** (`koe_alert`). Duplicate deliveries (same `X-GitHub-Delivery` ID) are ignored.

## 5. Approval gate (human in the loop)
- Tools marked **write: approval** never execute directly. The agent core creates a **pending action** (stored in SQLite) and asks:
  - **Web call:** Koe asks out loud ("Book 7:00–7:30 with Rahul. Shall I?"). A spoken yes or no resolves it, and the dashboard shows Approve/Reject buttons too.
  - **WhatsApp:** an interactive message with **Confirm / Cancel** buttons.
- Pending actions expire after 10 minutes.
- Every action (proposed, approved, rejected, executed, failed) goes to the activity log and the dashboard.

## 6. Mascot
- An anime-styled character drawn in **SVG + CSS** (no paid assets, no 3D). Built with the `blobatar` skill as a starting point, or a custom SVG if blobatar can't reach the anime look.
- **States:** `idle`, `listening` (reacts to mic volume), `thinking` (a tool is running), `speaking` (mouth/scale driven by the agent's output volume via the Web Audio `AnalyserNode`), `happy` (action succeeded), `error`.
- **Design direction:** to be decided with the user at the start of Phase 3 (examples: a small kitsune spirit, or a chibi character with headphones). Name the mascot then.

## 7. Memory
- **SQLite** (`koe.db`): `activity` (every action and message, with channel and latency), `pending_actions`, `daily_notes`.
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
3. Exact Gemini Live model ID and free-tier limits: verify on Day 1 (they change often).
4. Will Meta approve the `koe_alert` template quickly? If not, alerts only arrive inside the 24-hour window. Check in Phase 5.
5. Is a Google Sheets timesheet useful to the user, or is Notion enough? Confirm before Phase 4.
