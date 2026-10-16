> **Superseded for the core app by the 2026-10-16 rollback.** The user requested the original application design. This document is historical; SPEC 17.2 is authoritative. Only the Studio landing page remains.

# Studio throughout Koe — 2026-10-16

The user selected Studio for the homepage, then requested its design principles throughout the app, original service logos everywhere a service is represented, Mei instead of Miku/Mint, removal of Aoi from the main application, the existing palette, and slightly larger text.

## Shared design

- Existing Geist and Geist Mono typography. Body text is now 16px; smaller existing labels, captions and controls increase by roughly 1px. Large page headings use regular weight, close tracking and a clear hierarchy.
- Constrained 1200px layouts, more generous section spacing, understated borders, consistent panel corners and pill actions. Both themes keep their original colors.
- A consistent top navigation, with horizontally scrollable labeled navigation on phones. Original Spotify and Notion marks identify their pages. Existing Home, Dashboard, Chat, Settings, Guide and theme controls remain reachable.
- Scoped GSAP transitions introduce page headings; reduced motion disables them. Live call and workspace animations retain their existing behavior.
- The homepage remains Studio only. It uses the supplied PNGs and the names Kami, Mei and Kobashi.

## Pages

| Surface | Final treatment |
| --- | --- |
| Home | The original open, transparent companion stage beside the greeting, call action, live Today summary and original-logo tool links. No surrounding scene card or redundant home composition wrappers. The original desk and full-figure call framing remain. |
| Dashboard | Larger page heading, clear section rhythm and readable data panels. Calendar and GitHub panels use their original service artwork. |
| Chat | A focused bordered conversation workspace, larger messages and composer, companion heading, and preserved voice-note/live-workspace controls. A mini player reserves additional vertical space. |
| Notion | Original Notion heading/empty-state artwork, a spacious record list and preview/editor, preserved schema fields and approval controls. |
| Music | Original Spotify artwork in navigation, heading, placeholders, playlist attribution, external-player area and mini player. Existing playback, playlist actions and privacy/audio coordination remain authoritative. |
| Settings | A companion list and an open transparent interactive viewer followed by consistent account, connection, key and device sections. Google account and service rows use original artwork. |
| Install | The same app navigation, larger setup heading and more readable numbered steps. |
| Sign-in and public docs | Slightly larger text and a clearer sign-in hierarchy. Google sign-in uses its original mark at the intended size. |
| Approval previews | Original provider marks accompany verified provider links; the existing URL allowlist and approval contents are unchanged. |

## Palette lock

These values are existing application tokens, not a new Studio palette:

| Token | Dark | Light |
| --- | --- | --- |
| Background | `#0e0f11` | `#e2e2df` |
| Surface | `#16171a` | `#eaeae7` |
| Secondary surface | `#1e2024` | `#f2f2f0` |
| Text | `#e6e6e3` | `#1c1d1f` |
| Muted text | `#8b8d92` | `#5f6166` |
| Kami accent | `#a6d6d1` | `#3d7671` |
| Mei accent | `#5cc4b8` | `#1d7a72` |
| Kobashi accent | `#e2ba9b` | `#8b5a36` |

`frontend/src/studio.css` changes layout and hierarchy through existing variables, rather than redefining these colors. Provider artwork retains the providers' own colors.

## Companion compatibility

The catalog now contains Kami, Mei and Kobashi. Mei retains the internal `miku` identifier and asset paths so existing saved choices and runtime files continue working. An old Aoi selection falls back to Kami. Original user source files and unused runtime files are retained; Aoi is not rendered or offered by the application. The homepage reads the same display names instead of maintaining an independent Mint alias.

## Verification

The build and existing frontend tests cover compilation, existing behavior and companion compatibility. `frontend/scripts/verify-studio-app.mjs` uses an isolated Edge profile, synthetic auth/API/socket data and fake microphone input. It checks every major page at desktop and phone widths, original logo loading, exact palette tokens for all three companions, Notion editor controls, chat controls, simulated call cancellation/mute/end, and tablet breakpoints. It prevents provider writes. `verify-homepage.mjs` verifies the matching homepage and names.

Browser screenshots and JSON reports are saved in this chat's visualization directory under `koe-studio-app` and `koe-homepage`. These fixtures prove frontend behavior; they do not claim live Spotify streaming or account/provider acceptance. No deployment or account changes are part of this work.

Completed verification: production build and 55 frontend tests passed. Final lint has four existing warnings and no new warnings. Twenty-two app and ten homepage browser checks passed with no uncaught page errors or provider writes. Exact dark/light palette tokens and all companion accents matched the existing values.


## Interaction consistency correction

The 2026-10-16 follow-up restores the open companion composition. Shared `interactions.css` owns control typography, hover, press, disabled and keyboard-focus feedback for app, homepage, sign-in and docs. Action controls use 15px Geist; compact tabs/chips use 13px. All use 160ms state feedback and 0.97 press scale; filled controls dim slightly, neutral controls change surface/text colors. No hover lift or added button elevation. Selected rows and approval outlines retain their state indicators. Mini player and active-call utility use one elevation token. Existing headings and body hierarchy remain, with 16px body text and Geist Mono reserved for numbers/metadata.


Correction verified: production build and 55 tests passed; lint retains four existing warnings. Thirty-two app and seventeen homepage/sign-in/public-page browser checks passed. The control audit verifies computed fonts/timing and actual pointer/keyboard feedback, including both themes, disabled controls and reduced motion. Exact palette assertions and original logos remain valid. No uncaught errors or provider writes. Current reports are under `koe-ui-consistency` and `koe-homepage-consistency`.
