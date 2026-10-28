# GitHub in Koe

OAuth setup, token permissions and the October 26–27 recovery checklist are documented in [GitHub connection recovery](GITHUB_OAUTH_SETUP.md). Invited users can connect their own GitHub account; admin rights are not required.

## Connect and use

Invited, signed-in users can connect their own GitHub account; admin rights are not required. GitHub OAuth must be configured on the deployed backend, or use the personal-token option on a current backend. Always check the saved repository selection: connecting an account does not automatically track every repository. An answer about Koe requires selecting `watermelon588/Koe` (or all accessible repositories), even if a different repository was already tracked.
1. In Settings → Connections, connect GitHub with your own account using OAuth or **Use a token**. A fine-grained token can restrict access at GitHub itself; grant Contents and Pull requests read access, and Pull requests write only if you want approved PR comments. The token is verified and encrypted on the backend; it is never kept in browser storage. **Change account** replaces the connection and resets repository selection.
2. Choose up to 20 repositories or **All accessible repositories**, then save. Load more to browse past the first page. An empty selected list stops tracking and produces a selection prompt, not a zero-commit report. All-access mode remains limited by your credential's GitHub permissions; activity scans the 100 most recently pushed accessible repositories and reports truncated coverage explicitly.
3. Open Dashboard. Yesterday's commit/merged-PR counts and source-linked commits load automatically. Refresh uses the existing shared dashboard refresh; provider failures show errors or partial coverage.
4. Ask in chat or a live call: “What did I commit yesterday?”, “Summarize my work this week”, “What changed in commit [SHA] in owner/repo?”, “Which PRs need my review?”, or “What is my contribution streak?”

## What answers mean
- Activity covers each repository's default branch and up to 20 named branches, matched to the authenticated GitHub author login, plus your merged PRs. Commit SHAs are deduplicated per repository. Branch/repository limits or failed reads are marked partial; this is not unlimited all-branch coverage. Counts overlap; commits and PRs must not be added as unique work.
- Yesterday is midnight-to-midnight in Koe's configured timezone, Asia/Kolkata by default; the end is exclusive. GitHub search indexing may lag.
- Commit detail reports message, author, file names and additions/deletions with a GitHub link. It does not analyze patches or certify code. Source text is untrusted.
- Changed-line totals are opt-in, bounded and labeled; they are not repository LOC. Contribution streaks use GitHub's contribution calendar, not a commit-only calendar.
- Missing access is unknown, never zero. Partial repository failures retain accessible results and identify missing repositories.
- PR comments still require separate explicit approval. The agent cannot merge.

## Architecture and checks
OAuth/account and selected repositories → github_work/github_stats → shared agent registry → chat/voice tool events and dashboard. The read-only dashboard also requests yesterday's activity on refresh. Credentials remain server-side. No new database migration or dependency.

Focused backend tests: test_github_connect, test_github_tools, test_phase4_github, test_github_stats, test_github_hooks, test_events, test_voice_call. Frontend tests include dashboard state. Build before running backend/tests/github_ui_browser.mjs with KOE_E2E_NODE_MODULES pointing to an existing Playwright installation. The browser runner starts/stops only its own preview server on 5187 and uses synthetic provider data.

## Later work
Music latency is deferred. Google Docs creation/editing is implemented; standalone Drive file management remains outside the planned scope. Docs requires Drive APIs for file discovery/permissions.

## Sources
- https://docs.github.com/en/rest/commits/commits
- https://docs.github.com/en/rest/repos/repos#list-repositories-for-the-authenticated-user
- https://developers.google.com/workspace/docs/api/how-tos/overview
- https://developers.google.com/workspace/drive/api/guides/about-files
