# Homepage and illustrated guide update — 28 October 2026

User request: update the homepage and guide from recent changes, add screenshots, and preserve existing content.

## Content evidence

- `b77d3e7`: Google connection health/reconnect controls; bounded, recoverable service failures; six navigation pages and Music. Contract: RELIABILITY_REPAIR_2026-10-27.md.
- `0091730`: invited users' own Google/GitHub accounts and eligible GitHub OAuth refresh. Contract: GITHUB_OAUTH_SETUP.md.
- `c99e075` and `192407a`: Docs permission/status reporting, personal-token and repository scope controls, GitHub commit/merged-PR evidence. Contracts: GOOGLE_DOCS.md and GITHUB_WORKFLOW.md.
- Existing Sheets corrections/column creation: SCHEMA_ROW_EDIT_PLAN.md. Existing approval, Notion and Spotify behavior remains described in the guide.
- Current local companion changes: HOMEPAGE.md live companion update. Automatic VRM, cursor tracking, waving, pause/resume and reduced motion.

Homepage additions: four recent-improvement articles with guide links, two illustrative workflow scenarios (Docs creation and timesheet correction), and three FAQs. Existing hero copy, integrations, scenarios, FAQs and sections remain.

Guide additions: recent updates, step-by-step connection recovery, GitHub scope/activity, Docs, Sheets corrections, companion controls, five troubleshooting entries and Music in the contents. Every existing section and all 79 original content entries remain. The guide has its own update date; Privacy and Terms retain theirs.

## Screenshot provenance

Four 1280 × 900 JPEG screenshots live in `frontend/public/guide/`:

| File | Actual interface shown | Data |
| --- | --- | --- |
| companion.jpg | Public homepage with live Kami and motion control | Existing local model and public content |
| dashboard.jpg | Calendar, Approvals, PR and GitHub activity panels | Illustrative events, repository and proposal |
| connections.jpg | Google check/reconnect, Docs readiness and GitHub repository picker | Fictional `demo@example.test`, `demo-developer`, and `demo/*` repositories |
| notion.jpg | Notion record list and opened note | Fictional project notes, task and daily log |

Captured from the current rendered application using `frontend/scripts/capture-guide.mjs` and the bundled Playwright. HTTP/API/WebSocket responses are intercepted in an isolated browser context; writes are disabled. No real account data or provider mutations. Workspace figures are labeled as sample data in the guide. Images have intrinsic dimensions, lazy loading, descriptive alt text and accessible full-size links. Combined size is approximately 320 KiB.

Run from frontend: `node scripts/capture-guide.mjs <absolute Playwright package directory> [local origin]`.

## Verification

`npm run build`, `npm run lint` and all 76 existing frontend tests passed. `scripts/verify-guide-updates.mjs` passed six grouped checks: original guide content preservation; ordered complete contents and unique anchors; four decoded screenshots with captions/full-size links; guide layouts at 320/375/768/1440 in both themes; retained homepage sections and working added demo approvals; guide deep links and homepage layouts. Zero uncaught browser errors or account/backend requests during public-page checks. Screenshot capture also recorded zero provider writes and uncaught errors.

Inspected all source screenshots and the rendered guide/homepage at desktop/mobile sizes. Evidence is in `artifacts/guide-updates/`. This is a local source update; no hosting changes or deployment.

## Final scope clarification — 28 October 2026
The user subsequently declared the project complete at its current scope and explicitly requested removal of Coming later. That section, its weekly check-up/WhatsApp promises and its contents link are removed. The preservation verification now exempts only that explicitly removed roadmap; all remaining original content is retained. The user authorized a GitHub push of the completed changes.
