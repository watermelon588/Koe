# Koe — beyond the screen

Five experimental visual mockups, created 18 October 2026. A second series exploring brand art and product presentation with more expressive poses, materials, cameras and typography. The original ten application screen concepts remain in the sibling folder.

| File | Direction | Format | Native resolution |
| --- | --- | --- | --- |
| `11-open-window-laptop.png` | Kami, architectural daylight, silver laptop and celadon plinths | ≈16:9 | 1672 × 941 |
| `12-say-less-poster.png` | Mei, oversized typography, halftone echo and chrome voice ribbon | 1:2 | 887 × 1774 |
| `13-your-little-world.png` | Kobashi, collectible keycap, satin and an acrylic voice interface | 1:1 | 1254 × 1254 |
| `14-a-voice-a-feeling.png` | Kami close-up, ribbed optical glass and editorial serif typography | 3:4 | 1086 × 1448 |
| `15-signal-garden.png` | Three-companion ensemble, reflective water and a luminous crescent installation | ≈21:9 | 1916 × 821 |

Open `index.html` to review the gallery. Click a composition to open its original PNG; the ratio link downloads it. Final images are in `mockups/`. `contact-sheet.png` provides a browser-rendered overview. Images retain native generated dimensions, with no stretching, cropping, upscaling or post-processing. Landscape ratios are approximate within one output pixel.

## Creative approach

Used the frontend taste and imagegen skills. Increased visual variance while retaining a small palette: paper, charcoal, mint, teal and peach. Each direction changes the camera, physical materials, scale, crop, typography and overall composition. The works intentionally prioritize visual impact over information architecture. They are exploratory brand artwork, not implemented application features or proposed hardware products.

Final raster artwork was created with the built-in `image_gen` tool, one separate prompt per composition. The supplied mascot poses guided identity, costumes and gesture; the results are generative reinterpretations rather than unmodified sprite composites. Original source assets are unchanged. Full prompts are saved in `source/prompts.json`.

## Supplied references

All paths below are relative to the repository root.

- Laptop / Kami: `frontend/assets/mascot/4-kami(2).png`.
- Poster / Mei: `frontend/assets/mascot/26-Oct-16-01-01-23-00.png`; luminous type-texture inspiration from `frontend/assets/35169f77d14878a39f31ec1ffac3e115.jpg`.
- Collectible / Kobashi: `frontend/assets/mascot/26-Oct-16-01-01-21-06.png`.
- Editorial / Kami: `frontend/assets/mascot/3-kami.png`; optical softness inspiration from `frontend/assets/6c9b71381b0f16a1383961d0d5ec42e0.jpg`.
- Panorama / ensemble: `frontend/assets/mascot/4-kami(2).png`, `26-Oct-16-01-01-22-01.png` and `26-Oct-16-01-01-19-32.png` in that same mascot folder.

The six supplied design reference images and the complete local mascot pose folder were visually catalogued before choosing these references. Their existing third-party text and branding were not copied into the deliverables. The inspection atlas in `source/` is supporting research only.

## Files and reproduction

- `manifest.json`: titles, dimensions, formats, mascot names and pose filenames.
- `source/prompts.json`: complete prompt archive; use the listed references with the built-in image generator to explore further. Generative reruns will vary.
- `source/build-gallery.mjs`: generates the gallery. Run with the existing Node runtime from the repository root.
- `source/verify-gallery.mjs`: verifies all five images load, the gallery has no horizontal overflow at desktop/mobile widths, and saves the overview.
- The gallery uses the existing Geist font in the first-series sibling directory. It falls back to the system sans if the folder is moved alone.

No production application, service account, provider integration or hosting configuration was changed for these designs.
