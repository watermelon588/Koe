# Music UX implementation — acceptance verification pending

Recorded 2026-10-16. Implementation was subsequently authorized and added. The user's latest instruction is to push now without tests/live checks; the acceptance boxes below remain pending verification. [Requirements and boundaries](plan.md).

## M1 — Same-page assistant and audio contract

Define ownership, lifecycle and API/event boundaries for one Music page with a compact assistant and player.

- [ ] Opening Music and pressing its Call button is sufficient; no separate agent/music window prerequisite.
- [ ] Reuse the real conversational agent and one SDK player/controller.
- [ ] Define visible call/playback/handoff states, preserve exclusive audio and genuine uncertainty barriers.
- [ ] Review artist/title data flow and current approval/API scope before expanding the bounded tool.
- [ ] Document expected recovery on reconnect, tab visibility, session expiry and revocation.

Verification later: contract review and lifecycle scenarios. Dependencies: none. Likely files: SPEC, voice contract, music controller, call/audio adapters. Scope: medium design/contract slice.

## M2 — Compact assistant in Music

- [ ] Small assistant portrait/instance with Call, mute and end controls on Music; no full-body Home scene.
- [ ] Normal conversation works alongside playlist/player/search.
- [ ] Start/setup/progress are handled by the page, with no “open the music window first” instruction.
- [ ] Keyboard and phone controls fit; focus and accessible status are clear.

Verification later: focused component/browser checks and production build. Dependency: M1. Likely files: MusicPage, shared compact call presentation, useCall integration. Scope: medium.

## M3 — Reliable control connection and supported actions

- [ ] Enabled permission is distinct from an actually ready control/player session.
- [ ] Safely reconnect after temporary closure without “reopen Music” as the standard recovery.
- [ ] Explain SDK/device restriction errors with a useful action; do not mask them as generic connection failures.
- [ ] No uncertain command replay, stale grant execution, competing player or hidden duplicate socket.

Verification later: close/reconnect/expiry/revocation/device-restriction tests and browser call handoff. Dependency: M1; integrate with M2. Likely files: useMusicVoice, voice boundary, music_voice service, SDK/controller. Scope: medium, split transport and device cases if needed.

## Checkpoint — assistant and reliability

- [ ] Real Music page call works without a second window.
- [ ] Audio handoff/recovery tests and build pass; review the actual desktop/phone behavior.

## M4 — Play by artist or song within the allowed playlist

- [ ] “Play some Kesha” randomly selects an available matching artist track from that playlist.
- [ ] “Play [title]” selects the requested matching title; accept an artist qualifier.
- [ ] Handle ambiguity/versions, unavailable tracks and no matches honestly; no fabricated song names.
- [ ] Do not play from an unapproved playlist or send Spotify content to model context without an explicitly reviewed permitted contract.

Verification later: deterministic matching tests, bounded tool tests, real spoken artist/title requests and build. Dependencies: M1–M3. Likely files: music selection service/contract, voice adapter, playlist/controller tests. Scope: split matching and voice wiring into small slices.

## M5 — Missing song → useful add suggestion

- [ ] Clearly say the requested song is absent from the playlist.
- [ ] Offer an appropriate visible search/result/add path on Music.
- [ ] Suggestion alone does not add music; explicit user Add is required.
- [ ] Handle no catalog result, ambiguous results and unavailable content.

Verification later: present/absent/ambiguous cases and real search acceptance. Dependency: M4. Likely files: selection outcomes, Music search/controller and compact assistant feedback. Scope: medium.

## M6 — Direct Add and visible artwork

- [ ] Search results show real thumbnail, title, artist and clear versions/context, with a deliberate fallback if artwork is missing.
- [ ] One Add click executes once and changes in place to Adding/Added; no extra modal or large notification block for this action.
- [ ] Preserve request-ID deduplication, failures and unknown-outcome inspection; do not automatically resend a lost-response mutation.
- [ ] Keep other consequential-action approval gates intact.

Verification later: artwork response/render checks, double-click/lost-response/reload tests, actual Add acceptance and build. Dependency: M1; coordinate with M5. Likely files: Search, Music intents/controller, artwork/API mapping. Scope: split artwork and direct-add interaction into small slices.

## M7 — Music-only visual and scrolling refinement

- [ ] Professional music-player hierarchy inspired by Spotify, consistent with Koe's current fonts, colors and controls.
- [ ] Compact assistant, artwork, playlist/search/player read as one composition; remove redundant notice/card clutter.
- [ ] Predictable scrolling, no nested-scroll traps or controls hidden behind a mini-player; good desktop/mobile widths.
- [ ] Restrained GSAP motion/scroll polish, reduced motion, lifecycle cleanup and responsive keyboard/touch interaction.
- [ ] Use relevant frontend/GSAP skills when authorized to implement; no whole-app or homepage redesign.

Verification later: visual review, computed style/overflow/focus checks, reduced-motion checks and build. Dependencies: M2, M5, M6. Likely files: MusicPage/music CSS, compact assistant presentation and scoped animation hooks. Scope: split composition, scrolling and motion passes.

## Final checkpoint — real acceptance, not only mocks

- [ ] Artist/title/absent-song flows work with the user's actual permitted playlist and speech.
- [ ] Artwork and one-click Add work; no duplicates or false success after lost responses.
- [ ] Device/SDK restrictions, connection closure and real audio handoff behave honestly.
- [ ] Desktop/phone presentation is reviewed; focused suites and production build pass.
- [ ] User reviews the final Music page before any deployment.

The current implementation is being published at the user's request. Run the pending acceptance work only when requested; do not claim unchecked outcomes have passed.


## 2026-10-17 Music repair verification

This section updates the earlier pending implementation checklist. The user subsequently requested end-to-end repair and continuation; the previous no-test instruction no longer applies to this repair.

- [x] Separate unconfirmed shuffle/repeat from play/transfer uncertainty; verify recovery without replay.
- [x] Same-page Call and Home Call after reload verified through the simulated browser pipeline.
- [x] One functioning Change playlist chooser with cancel/refresh/select and labelled Create form; creation pauses previous playback.
- [x] Bounded debounced artist suggestions, keyboard selection, artwork fallback and direct Add feedback.
- [x] Compact mute, volume steps, slider and percentage; responsive Music layout uses the existing palette/fonts.
- [x] Canonical `/app/music` paths, legacy hash migration, browser back/reload and Vercel rewrite.
- [x] Focused backend tests (71), frontend tests (69), 28 browser checks and production build pass; desktop/mobile screenshots reviewed.
- [x] Real read-only playlist eligibility, artwork presence and artist-search checks pass; local backend/frontend HTTP 200.
- [ ] Owner verifies real speech recognition, audible Spotify playback and phone behavior.
- [ ] Verify hosted authenticated music and voice after the GitHub deployment completes.

The unchecked items require real provider/audio acceptance; automated fixture checks do not stand in for those outcomes.


## 2026-10-18 priorities
- [ ] Deferred: profile and reduce Music-page latency (load, SDK readiness, search, call preparation, voice-to-playback). Measure each stage first; preserve verified audio handoff. Do not implement in the GitHub task.
- [ ] Next Google integration: Google Docs creation/editing, selected by Rohit. Drop standalone Google Drive from the planned feature list; keep only any Drive API support needed by Docs. No removal of working Google Calendar/Sheets integration.
- [x] Implemented locally: GitHub connection/repository selection, yesterday's local-time authored commits and merged PRs, evidence-linked commit summaries, honest scoped statistics, dashboard visibility and agent read tools across chat/voice. Verify authorization, partial provider failures, pagination and UI/API integration. No automatic comments, merges or account changes.

- [ ] GitHub live acceptance after deployment: connect the real account, choose repositories, ask about yesterday and a specific commit in chat and voice; compare source links. Automated tests simulate provider responses and model tool selection.
