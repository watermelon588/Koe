# Koe sign-in before hosting

Status: **superseded 2026-10-13 by [ACCOUNTS_SPEC.md](ACCOUNTS_SPEC.md)** (invite-only multi-user). The session, PKCE and CSRF requirements below still apply. Originally: proposed final flow, not implemented. The current access-token UI remains available for local testing. The user requested an explanation of its replacement on 2026-10-13.

## Current behavior

`KOE_ACCESS_TOKEN` is a shared application password, separate from `DATABASE_URL`, Google OAuth tokens, and API keys. It protects the dashboard, calls and app chat. The home screen keeps it in component memory; the app chat remembers it on the device. It is a development access mechanism, not the intended final onboarding experience. Removing the input without replacing server authentication would expose private data and write-capable tools.

## Recommended finished user journey

1. Open Koe and choose Continue with Google (recommended because Calendar/Sheets already use Google), or GitHub if that provider is selected for implementation.
2. The provider verifies the account. FastAPI completes the authorization-code flow and checks the stable provider user ID against the configured owner's allowlist. Signing in as any arbitrary Google/GitHub account must not grant access to Rohit's data.
3. FastAPI issues a random, revocable session, stored server-side, and an HttpOnly cookie. Production cookies use Secure and appropriate SameSite settings. The browser does not store provider or database secrets in JavaScript storage.
4. The dashboard opens automatically. Chat, voice calls and dashboard WebSockets use the session; the user never copies a token from `.env`. Refreshing or returning to the installed app keeps the session until expiry or logout. A new device signs in normally.
5. A Connections screen shows Calendar/Sheets, GitHub and Notion setup. App sign-in proves identity; accessing Calendar or repositories requires separate consent/scopes. Existing developer credentials remain server-side until web connection flows are implemented. Google sign-in alone does not grant Calendar access.
6. The user can read their day, chat or call. Calendar changes, PR comments and every timesheet entry still show a preview and require explicit approval. Login is not approval to execute an action.
7. Logout revokes the server session and clears its cookie. Expired sessions return to sign-in.

No additional Koe password is necessary when using a provider. This remains a personal single-owner app. Public multi-user signup would require per-user credentials, storage isolation, ownership checks and a separate product scope.

## Implementation and deployment requirements

- Add web OAuth/OIDC client credentials and register exact localhost and production callback URLs. The current Desktop OAuth client for Calendar is a separate setup.
- Validate state; use PKCE and provider-appropriate identity validation (including OIDC nonce/issuer/audience where relevant). Reject an account outside the owner allowlist.
- Store sessions in Neon with expiry/revocation; rotate session IDs on login. Add login rate limits, CSRF protection for mutations and Origin checks on WebSocket handshakes.
- Serve the frontend and backend through one public origin (`/api` and `/ws` reverse proxy), including Vite's proxy locally. This makes cookie behavior reliable on browsers and the installed app. A frontend and unrelated backend domain need an explicit cross-site cookie/CORS design.
- Replace token handling consistently across Home, app chat, HTTP APIs, voice files and both WebSockets, and test rejection before any data/API work.
- Complete this slice and account/logout tests before hosting publicly. Do not silently treat the Neon database connection as user login or enable every provider by default.

Sources: [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
