# Changelog

## 0.9.1 — 2026-10-23

- Smoother graphics: all artwork downscaled for the DS (HUD, bottom-screen backdrops, players, enemies, pickups, level scenery, scrolling backgrounds, credits and highscore screens) now uses premultiplied Lanczos resampling instead of nearest-pixel sampling. Outlines no longer drop or double pixels, and shading has fewer stray pixels.
- Sprite GPU page formats, scenery tile counts and ROM size stay essentially unchanged; emulator frame timings are unchanged.
- Fixed the source build: asset assembly expected 28 conversion steps but the pipeline runs 29, so a fresh build stopped before producing a ROM.

## 0.9.0 — 2026-10-23

- Nintendo DS port of all four worlds, with tutorials, enemies, bosses and character switching.
- Native scenery and GPU actor rendering, DS graphics conversion and compressed audio.
- Bottom-screen HUD, touch menus and character switching, credits and highscores.
- DS keyboard name entry with the current level backdrop; raw 8 KiB save files.
- Source distribution with a bundled ROM icon and a hash-checked ISO extraction and asset conversion pipeline.
- Output renamed to `Kinder Fresh Adventures.nds`.

Hardware validation currently covers the Jungle tutorial and first level. Complete playthroughs, other worlds and flashcart save durability remain open.
