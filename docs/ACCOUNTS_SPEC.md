# Spec: accounts, connections and guides (Phase 5c)

Status: approved direction 2026-10-13; built slice by slice (PLAN.md Phase 5c). This supersedes the owner-only design in [AUTH_FLOW.md](AUTH_FLOW.md). If this file and SPEC.md disagree, SPEC.md wins, so SPEC.md links here.

## Objective
Today Koe works for one person who edits `backend/.env`. A friend can't use it: they would need your access token, your Google/GitHub/Notion tokens, and a code change. The goal is for **an invited friend to go from link to working assistant without touching code**:

> open the site → read the Guide → Continue with Google → install the app → connect Calendar, Sheets, GitHub, Notion from Settings with consent screens → talk to Koe about *their* day.

Decisions (Rohit, 2026-10-13):

| Question | Decision |
|---|---|
| Who can use it | **Invite-only.** An allow-list of emails; anyone else sees "not invited". |
| Gemini key | **Rohit's key by default with a per-person daily cap**; a person may add their own key in Settings to remove the cap. |
| Sign-in | **Continue with Google.** Signing in proves identity only. Calendar/Sheets access is a separate Connect step with its own consent. |

## Capability map

| Module id | Responsibility | Depends on |
|---|---|---|
| `pages` | Public Guide, Privacy, Terms (path URLs, no login) | — |
| `identity` | Google sign-in, invite allow-list, sessions, logout; replaces `KOE_ACCESS_TOKEN` everywhere | — |
| `user-data` | Every stored row and conversation belongs to one user; app chat moves from SQLite to Neon | identity |
| `connections` | Per-user OAuth for Google Calendar/Sheets, GitHub, Notion; tokens encrypted at rest; Settings → Connections | identity, user-data |
| `quota` | Per-user daily turn cap on the shared Gemini key; optional own key | identity, user-data |
| `admin` | The owner invites and removes people in Settings | identity |

Build order: `pages` → `identity` → `user-data` → `connections` (Google, then GitHub, then Notion) → `quota` → `admin`.

## Architecture
- **One origin for HTTP.** Vercel rewrites `/api/*` and `/auth/*` to the Render backend (reverse proxy, [Vercel rewrites](https://vercel.com/docs/routing/rewrites)). The session cookie then belongs to `koe-pi.vercel.app`, so it works on phones without third-party cookies. API and auth responses send `Cache-Control: no-store` (Vercel honors upstream cache headers on external rewrites). Locally the Vite proxy does the same.
- **WebSockets go straight to Render** (rewrites don't carry them). The page gets a **one-time ticket** with `POST /api/ws-ticket` (cookie-authenticated, valid 60 s, single use) and opens `wss://…onrender.com/ws/call?ticket=…`. Handshakes also check `Origin`.
- **Sessions:** a random 256-bit id in an `HttpOnly; Secure; SameSite=Lax` cookie. Only its SHA-256 is stored, in Neon `koe_sessions` (user, created, expires, revoked). 30-day expiry, rotated on sign-in, revoked on logout. State-changing requests must carry `Origin` = the site (CSRF).
- **Google sign-in:** authorization-code flow with PKCE, `state` and `nonce`, scopes `openid email profile`. The ID token's `iss`, `aud`, `exp` and `nonce` are checked. Access requires a verified email on the allow-list. Uses a new Google OAuth client of type **Web application**; the existing Desktop client stays for local scripts.
- **Users:** Neon `koe_users` (id, google_sub unique, email, name, is_admin, created). The owner is `KOE_ADMIN_EMAIL`; invites live in `koe_invites` (email, invited_by, created).
- **Connections:** Neon `koe_connections` (user, provider, account label, scopes, encrypted token JSON, created, updated). Tokens are encrypted with Fernet (`cryptography`, already in the lock file via pywebpush) under `KOE_SECRET_KEY`. Tools load the *calling user's* connection; there is no global token in multi-user mode.
  - **Google Calendar + Sheets:** incremental consent (`calendar.events`, `spreadsheets`), `access_type=offline`. Settings can **create the Hours sheet** with the right headers, so nobody copies an ID.
  - **GitHub:** OAuth App, scopes `repo read:user`. Settings lists the user's repos to tick.
  - **Notion:** public integration OAuth. The user picks pages in Notion's own consent; Settings can create the "Koe Daily Log" database.
- **Quota:** `koe_usage` (user, day, turns). Default cap `KOE_DAILY_TURNS=60` on the shared key, no cap with the person's own key (stored encrypted like a connection).
- **Single-owner mode keeps working.** If the multi-user settings (Google web client, `KOE_SECRET_KEY`) are absent, Koe behaves as today. The `.env` tokens still apply to the owner, so local development never breaks mid-migration.

## Commands
```bash
uv run pytest -q                      # backend (from backend/)
uv run python -m scripts.migrate_store  # applies migrations/*.sql to Neon
npm test && npm run lint && npx tsc -b  # frontend (from frontend/)
```

## Project structure (new)
```
backend/koe/auth.py          sign-in, sessions, current_user dependency, ws tickets
backend/koe/connections.py   OAuth connect/callback per provider, encrypted token store
backend/migrations/002_accounts.sql
frontend/src/pages/          Guide, Privacy, Terms (public, path-routed)
frontend/src/settings/Connections.tsx
```

## Testing strategy
pytest with fakes for Google, GitHub and Notion token endpoints (respx). Every new endpoint gets a "rejected without a session" test, plus "user A can't read user B" tests for each table. Frontend: node tests for pure helpers. A browser check of the Guide, sign-in and Connections pages at 375 and 1280 px.

## Boundaries
- **Always:** keep write approvals (SPEC §5) per user. Keep tokens server-side and encrypted. Log no tokens or message bodies. Keep the docs first.
- **Ask first:** new dependencies (`cryptography` as a direct dependency is the only one expected); creating OAuth apps or clients (Rohit does it in each console, guided step by step); any change to who is admin.
- **Never:** open sign-up; share one user's data or tokens with another; store tokens in browser storage; ask for a password.

## Success criteria
1. `/guide`, `/privacy` and `/terms` load without signing in, link to each other from the footer, and describe what Koe actually does with data.
2. An invited Gmail account signs in with Google and reaches Home with no token typed. An uninvited account sees "You're not invited yet" and gets no session.
3. Calls, chat, voice notes, dashboard and push work with the session alone. Logout ends them.
4. A second invited user sees none of the first user's chat, activity, approvals or connections (tested).
5. From Settings → Connections, a user connects Google Calendar and Sheets, then GitHub, then Notion, and Koe answers "what's on my calendar today?" from *their* calendar.
6. A user on the shared key hits the daily cap with a friendly message. Adding their own key removes it.

## Known limits (said plainly in the Guide)
- **Google:** Calendar and Sheets are "sensitive" scopes, and an unverified app shows a warning screen. While the Google app is in *Testing*, each friend's Gmail must be added as a test user, and refresh tokens expire after 7 days. Switching the app to *In production* without verification removes the 7-day expiry, keeps the warning, and caps the app at 100 users.
- Render free sleeps when idle, so the first request takes up to a minute.
- WhatsApp stays owner-only, and blocked until Meta verifies a business.
- GitHub push alerts stay owner-only for now (per-user repo webhooks need extra permissions).
- A weekly check-up is a v2 idea; the Guide lists it under "coming later".
