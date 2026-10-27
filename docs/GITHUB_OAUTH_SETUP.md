# GitHub connection recovery — 2026-10-27

Koe supports two separate connection methods. A personal access token is a credential for one GitHub account. An OAuth App supplies the Client ID and Client Secret used by Koe's **Connect GitHub** button so each invited person can authorize their own account.

The token shown during this repair had no selected repositories or repository permissions. A successful public-repository read does not prove that token has access to private repositories. If using a personal token, select the intended repositories and grant Contents and Pull requests read access. Grant Pull requests write only when approved comments are wanted. Do not distribute the owner's token to invited users.

## OAuth App

The registered app is [Koe](https://github.com/settings/applications/3966020), owned by `watermelon588`.

| Setting | Value |
| --- | --- |
| Homepage | `https://koe-pi.vercel.app` |
| Callback | `https://koe-pi.vercel.app/auth/github/callback` |
| Wildcard matching | Off |
| Device flow | Off |
| Expiring user tokens | On |

Store `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` only in Render's existing `koe-backend` environment. The values are not part of this document, Git, frontend variables, or chat. Keep the existing `KOE_SECRET_KEY` stable: it encrypts the saved connections. Saving Render variables without deploying does not activate them in the running process.

New OAuth Apps use expiring access tokens by default. Koe now stores the refresh token and both expiry times encrypted. A server-side refresh rotates the pair under a per-user lock, validates the GitHub login, and saves the new pair. Failed or uncertain refreshes require reconnecting instead of replaying a token or falling back to the owner's credentials. Legacy non-expiring OAuth and personal tokens remain supported.

Sources: [GitHub OAuth app creation](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app), [expiring tokens and refresh](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps), [new-app defaults](https://github.blog/changelog/2026-08-14-multiple-redirect-uris-and-token-refresh-for-oauth-apps/), [fine-grained token permissions](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens).

## Verify the live connection

1. Deploy the reviewed backend repair. Check owner-authenticated `/api/backend/status` for its exact revision.
2. Check `/api/connections`: `github_ready=true` means OAuth's client credentials and connection encryption are configured. It does not prove a user's consent or provider availability.
3. In Koe Settings → Connections, connect GitHub and review GitHub's consent page. The existing OAuth request asks for `repo read:user`; private repository access is included. Writes in Koe still need the separate approval gate.
4. Choose and save repositories after connecting. A new account connection resets selection; reconnecting the same saved account preserves it. For the owner's example, select `watermelon588/Koe` and `watermelon588/Walkthru`.
5. Ask “What did I commit on October 25, 2026?” and compare the Koe source link with commit `3355795`, timestamped 21:37:32 IST. Using the explicit date avoids changing the question's meaning after midnight.

Invited users can now start Google and GitHub consent without admin status. Their credentials, selected repositories, conversations and approvals stay separate. Notion and Spotify retain their documented owner-only limits. Real consent and voice/microphone acceptance are separate from synthetic regression tests.

## Verified recovery evidence

On October 26, the hosted backend was behind GitHub and selected only Walkthru. The owner-authorized selection was saved as `["watermelon588/Walkthru", "watermelon588/Koe"]`, read back from PostgreSQL, and then verified through the live repository endpoint after Render updated to `3355795`. The OAuth App and its backend credentials were created with explicit user confirmation. The live connection endpoint subsequently reported `github_ready=true` and both selected repositories. Render now uses `main` with **On Commit** deployment. The expiring-token and invited-user repair is published separately from unrelated concurrent work; verify its exact deployment revision before claiming those code paths are live.
