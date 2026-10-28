# Public homepage — 2026-10-16

## Live companion update — 2026-10-28

The homepage hero loads the selected VRoid VRM automatically. Reuse the existing renderer for breathing, blinking, idle gestures, eyes/head following the cursor, touch reactions and drag rotation. The greeting triggers a real wave. Replace the artwork toggle with Pause/Resume movement; respect the system reduced-motion preference and suspend rendering while the companion is outside the viewport. Supplied PNGs remain loading/error fallbacks and gallery thumbnails. Kami, Mei and Kobashi selections load their corresponding VRMs. No new assets or dependencies are needed. This supersedes the optional-3D behavior below.

## Additive content and illustrated guide — 2026-10-28

Preserve all current homepage and guide content. Add user-facing details supported by recent commits: invited users' own Google/GitHub connections, Google Check connection/Reconnect and separate Docs consent, saved GitHub repository scope and automatic eligible OAuth refresh, Docs read/create/edit with approval and stale-edit protection, Sheets row corrections/columns, optional approved Spotify voice controls, and the live 3D companion. Add homepage workflow examples, recent improvements and FAQs; extend the guide with practical setup/recovery steps and screenshots of the current UI. Capture screenshots locally using sample API/socket data and label illustrative account/workspace data clearly. Public guide access must require no account or backend requests. Update the guide's date independently of legal pages. No deployment or provider writes.

User request: three premium, minimal homepage variations sharing existing Geist typography and design principles, original provider logos throughout the frontend, the existing mascot, detailed user benefits, and smooth GSAP motion.

## Scope

- Public homepage at `/`, with `?look=studio`, `?look=after-hours`, and `?look=field-notes` as shareable variations. A visible switcher changes composition as well as palette.
- Existing authenticated application at `/app`; existing root hash links such as `/#settings` remain supported. Public documentation and authentication remain available.
- Shared content: voice-first product introduction, interactive illustrative workflow, current and planned integrations, existing 3D mascot, concrete usage examples, approval/privacy explanation, FAQ, and links into the app.
- Five implemented service integrations: GitHub, Google Calendar, Notion, Google Sheets, and Spotify. Google Docs and Google Drive are planned, with no implied functionality or account connection. WhatsApp remains setup-dependent; web call, typed chat, and app voice notes are the three described input modes.
- No invented customers, adoption statistics, latency measurements, prices, or time-saving claims. Demo records are labeled and never call provider APIs.
- Original locally stored provider artwork is shared by the homepage and application connection rows. Standard action icons remain Phosphor.
- GSAP entry, section reveal, and workflow transitions use scoped cleanup and honor reduced motion. Existing VRM artwork remains the source of the mascot, with portrait fallback.
- Responsive layouts, keyboard accessible selectors, native FAQ disclosures, and visible focus states.
- No backend, hosting, account, approval, or dependency changes are required.

## Design

Studio: airy ice-white and mint, split hero with a companion scene, understated rounded surfaces.
After Hours: graphite and pale mint, a wide product scene, compact editorial introduction and a technical atmosphere.
Field Notes: paper-white, ink and muted green, offset composition, section numbering and a notebook-like layout.

All three share Geist / Geist Mono, light display weights, generous negative space, restrained borders, consistent interactive shapes, and original connection colors.

## Verification

Run frontend TypeScript/production build, lint and existing frontend tests. Inspect all three variants in a browser at desktop and mobile widths; exercise variation selection, demo scenarios, mascot greeting/selection, integration filtering, FAQ and application routing. Report any unavailable browser verification honestly.

### Completed verification

2026-10-16: production build passed; 54 existing frontend tests passed; lint passed with four existing warnings and no warnings in new files. Thirteen isolated Edge checks verified desktop/mobile layouts, working original logos, live mascot, demo controls, filters/details/FAQ, URL history, reduced-motion entrance behavior and existing sign-in gates. No uncaught browser errors. The existing VRM bundle-size advisory remains. All changes are local; no hosting or account changes were made.

## Supplied mascot artwork follow-up — 2026-10-16

The user supplied mascot PNGs in `frontend/assets/mascot` for homepage use. Use the original transparent exports directly through Vite imports, without regenerating or editing their pixels. Each homepage design uses a distinct supplied Kami pose. Supplied Mint and Kobashi poses populate the companion previews and selected hero; Aoi retains her existing portrait because no Aoi PNG was supplied. Artwork is the initial hero, with an explicit optional 3D preview so homepage visits do not download the VRM model automatically. The greeting retains lightweight GSAP feedback and respects reduced motion. The real app's 3D mascot remains unchanged.

Follow-up verification: production build passed, no new lint warnings, and 15 isolated Edge checks passed with no uncaught errors. Browser evidence confirms three different supplied Kami PNGs, supplied Mint/Kobashi previews, and zero VRM downloads until the visitor requests 3D.

## Final homepage selection — 2026-10-16

The user selected Studio only and asked to remove Aoi's picture from the homepage. Remove the other homepage variations and the design switcher. The homepage companion gallery now contains Kami, Mint and Kobashi; its count and copy must say three. Legacy `?look=` links resolve to Studio. This is a homepage-only change; the existing app mascot catalog and runtime assets remain available to the app.

Final-selection verification: production build passed; ten isolated Edge checks passed with no uncaught errors. No new lint warnings. Studio is the only rendered design, its gallery contains three companions and no Aoi image, and former variation URLs resolve to Studio.

**App-wide follow-up (2026-10-16):** Studio's layout and type principles now apply throughout the app with its existing palette preserved. Homepage and app names are Kami, Mei and Kobashi; Mei replaces the former Miku/Mint display names. Smaller homepage text is slightly larger. See STUDIO_UI.md for the shared design and verification.
