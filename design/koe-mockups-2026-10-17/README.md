# Koe — visual mockups · 17 October 2026

Ten minimal, mascot-led screen concepts for the existing Koe application. Design exploration only; the running product is unchanged. All account, calendar, chat and music content shown is illustrative.

## Direction

Preserve Koe's charcoal, paper and mint identity; give the companions space; prefer a visual schedule, waveform, progress indicator or provider mark to explanatory paragraphs. Use the supplied Kami, Mei and Kobashi PNGs, original local provider artwork, Geist and Phosphor icons. Apply frontend UI engineering, Emil Kowalski design engineering and design-taste principles. Static mockups do not need decorative animation.

The ten screens cover Home, Dashboard, live Call, Chat, a proposed Calendar view, Notion, Music, Companion settings, Connections and mobile. The Calendar view is a concept, not a claim that Koe already has a separate Calendar page.

## Files

- `index.html`: visual gallery; open locally in a browser.
- `contact-sheet.png`: overview of all ten designs.
- `mockups/`: ten full-resolution PNG mockups.
- `source/`: editable, self-contained HTML/CSS plus repeatable build/capture scripts.
- `assets/`: copies of the supplied transparent mascots, existing fonts and original provider logos used in this exploration.
- `screenshots/current/`: full-page references of the current application in an isolated browser with synthetic API/socket responses. No real sign-in, messages, streaming or provider mutations.

## Palette

| Role | Color |
| --- | --- |
| Charcoal | `#0e0f11` |
| Raised charcoal | `#16171a` |
| Paper | `#e2e2df` |
| Ink | `#1c1d1f` |
| Kami mint | `#a6d6d1` |
| Mei teal | `#5cc4b8` |
| Kobashi peach | `#e2ba9b` |

The mockups are built directly in HTML/CSS with existing artwork, then rendered in Edge. The original asset images are not regenerated or retouched. Screenshots of the original app and redesigned concepts are stored separately.

## Screen index

1. Veranda — Home, Kami
2. Daylight — Dashboard, Kami
3. Quiet conversation — live Call, Kami
4. Just say it — Chat, Kami
5. Make room — Calendar concept, Kobashi
6. Thoughts, kept close — Notion, Kobashi
7. Quiet hours — Music, Mei
8. Your kind of company — Companion selection, all three
9. Good company — Connections, Kobashi
10. Pocket companion — mobile Home and Call, Kami

All ten PNGs are 2880 × 2000. `verification.json` records successful asset loading, artboard bounds, no horizontal overflow and no browser page errors. The 15 current-app screenshots use illustrative account data; they are visual references, not live integration acceptance tests.

## Reproduce

From the repository root, run `node design/koe-mockups-2026-10-17/source/build-mockups.mjs` after installing the existing frontend dependencies. For captures, set `KOE_MOCKUP_MODULES` to a local `node_modules` directory containing Playwright, then run `node design/koe-mockups-2026-10-17/source/capture-mockups.mjs`. Microsoft Edge must be installed. The capture script serves only this folder on a temporary loopback port and closes it after rendering.

The mockup pages and gallery also open directly from disk with no server. Source pages use a fixed 1440 × 1000 artboard; the gallery adapts to the browser width. Fonts retain their supplied OFL notices; Phosphor's license and provider asset notes are included in `assets/`.
