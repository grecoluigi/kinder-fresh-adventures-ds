# Building from the original disc

## Original game data

The source release must not contain the ISO, Windows executable, extracted graphics/audio, generated game assets or commercial reference ROMs. Supply your own copy of the supported disc:

| Disc identity | Value |
|---|---|
| Size | 214,038,528 bytes |
| MD5 | `186e1d22c3cf1d490542399a570e93bb` |
| SHA-256 | `9c6d7b33665ce10d0d2e38277d07ff51b2887c1b348012fd91210abc308458a7` |

Install Python 3 and `unshield`, then validate and extract the disc:

```sh
python3 tools/extract_source.py --iso "/path/to/Kinder Fresh Adventures - Collection.iso" --verify-only
python3 tools/extract_source.py --iso "/path/to/Kinder Fresh Adventures - Collection.iso" --output build/assets
```

The extractor reads the disc directly, validates its identity before creating output, and invokes `unshield` on the cabinet volumes. It does not mount the disc or run the Windows installer. Its output directory must not already exist. Cabinet intermediates are removed after successful extraction; the source files and manifest remain.

Asset conversion dependencies used in development:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-assets.txt
```


The asset conversion stages run together, using a separate, initially absent output directory:

```sh
.venv/bin/python tools/prepare_assets.py --iso "/path/to/Kinder Fresh Adventures - Collection.iso" --output build/asset-regeneration --through scenery
```

This extracts the source, decodes graphics, exports maps/scripts, generates collision masks, compiles native scene dispatch, builds music/effects/voices, and generates the menu, credits, ending banners, highscore/font assets, indexed HUD/backdrops, floating score graphics, player animations, projectile images, enemy/pickup sprites, object geometry, scene headers, scrolling backgrounds the native GPU actor pack, native scenery tile banks and ordered depth packets. It reads the supplied ISO and generated intermediate data; no research files or legacy renderer atlases/indexes are needed. Use `--through collision`, `--through scene-definitions`, `--through audio`, `--through ui`, `--through hud`, `--through characters`, `--through entities` `--through scenes` or `--through actors` for an earlier stopping point. Assemble the output into the source project before building, as described below.

Music and sounds are adapted to 22,050 Hz mono. The audio stage then encodes music as independently decodable IMA-ADPCM blocks (`audio/*.kfm`, decoded on the ARM9 into the PCM stream) and every effect/voice as one hardware sample in `sounds/samples.hw` (search-encoded IMA-ADPCM; short sounds whose ADPCM quality would fall below 20 dB stay PCM16). Effects play on ARM7 hardware channels from a RAM cache. Sound bindings are recovered by bounded execution of the original initialization routine in Unicorn. The generated `sounds/sound_assets.inc` must accompany its matching `samples.hw`.

Check the hardware audio assets and slot logic on the host (`--reference-*` point at the stage's intermediate `samples.pcm` and WAV directory):

```sh
.venv/bin/python tools/verify_hw_audio.py --nitrofs build/asset-regeneration/hardware_audio --reference-sounds build/asset-regeneration/sounds --reference-audio build/asset-regeneration/audio --output build/asset-regeneration/hw-audio-verification.json
```

Verify regenerated dispatch data against the current local playable assets with:

```sh
.venv/bin/python tools/verify_native_scene_definitions.py --assets build/asset-regeneration/native_scenery
```

This also exercises the C loader with malformed files under AddressSanitizer and UndefinedBehaviorSanitizer. It does not prove gameplay or performance.

UI output directories are `menu/`, `credits/`, `end_titles/` and `highscores/`. Generated `menu/menu_hitboxes.h` and `highscores/highscore_assets.h` accompany their matching assets. The menu stage emits only the compressed base and six focus patches; menu music is handled by the audio stage. Menu, credits and highscore screens are Lanczos-resampled from 800×600 to 256×192.

Verify decoded menu states and native highscore text/layout behavior without opening an emulator:

```sh
.venv/bin/python tools/verify_menu_cache.py --assets build/asset-regeneration/menu --decoded-assets build/asset-regeneration/decoded --output build/asset-regeneration/menu-verification.json
.venv/bin/python tools/verify_highscore_ui.py --assets build/asset-regeneration/decoded --source build/asset-regeneration/source/ausf_hrende_Dateien --runtime-assets build/asset-regeneration/highscores --output build/asset-regeneration/highscore-verification
```

The highscore verifier's output directory must not already exist. It uses the supplied original executable for bounded native glyph/layout checks and does not overwrite playable assets.

The HUD stage generates `native_bottom/` (four shared-palette backdrops and indexed HUD patches) plus `score_popups/points.bin`. `hud_intermediate/` holds offline RGB555 conversion inputs and is not a runtime dependency. Downscaled HUD art and backdrops use premultiplied Lanczos resampling with 1-bit transparency restored at half coverage; the score font keeps exact colors and nearest-neighbour scaling.

Verify the regenerated HUD loader, draw states and touch bounds with sanitizers:

```sh
.venv/bin/python tools/verify_native_bottom.py --assets-dir build/asset-regeneration/native_bottom --output build/asset-regeneration/native-hud-verification.json
```

Player output is `players/` (both characters with both facings baked at the original body origin). `projectiles/` and `enemy_shots/` contain player and enemy projectile images. Physics coordinates and native frame dimensions/offsets remain in original units; sprite rasters use premultiplied Lanczos resampling on the same 8/25 lattice, with 1-bit transparency at half coverage. Frames whose centered-sample rasters fit 15 or 255 colors are reduced back to that palette class, so GPU page formats do not grow.

Check every character frame/facing and projectile image against decoded original artwork:

```sh
.venv/bin/python tools/verify_character_assets.py --decoded-assets build/asset-regeneration/decoded --players build/asset-regeneration/players --projectiles build/asset-regeneration/projectiles --enemy-shots build/asset-regeneration/enemy_shots --output build/asset-regeneration/character-verification.json
```

This verifies runtime packet decoding, alignment, transparency and buffer guards without maintaining a software scene renderer.

The entity stage creates `enemies/enemies.frames`, `entities/pickups.frames`, `entities/*.entities` and `geometry/objects.geometry`. These derive animation ranges and frame alignment directly from original scripts and artwork; they do not require a previous packed copy. The record order, initial per-map object bytes and collision-related frame geometry remain exact.

Verify all enemy/pickup raster variants, animation ranges and geometry:

```sh
.venv/bin/python tools/verify_entity_assets.py --decoded-assets build/asset-regeneration/decoded --maps build/asset-regeneration/maps --enemies build/asset-regeneration/enemies --entities build/asset-regeneration/entities --geometry build/asset-regeneration/geometry --output build/asset-regeneration/entity-verification.json
```

`scenes/` contains scene headers, static object metadata, original tile layers, fixed background images and collision files. `backgrounds/` contains the compressed row packs used by scrolling backgrounds. Sprite metadata IDs and spawn coordinates are preserved without emitting obsolete software tile banks or static sprite images.

Check scene/source records, collision alpha and background rows expanded by the runtime C decoder:

```sh
.venv/bin/python tools/verify_scene_assets.py --decoded-assets build/asset-regeneration/decoded --maps build/asset-regeneration/maps --scenes build/asset-regeneration/scenes --backgrounds build/asset-regeneration/backgrounds --output build/asset-regeneration/scene-verification.json
```

The actor stage builds `native_actors/pages.gpu` from the complete regenerated player, enemy and pickup banks. It uses lossless 4/8-bit palettes or direct RGB555 pages, a dense frame lookup and the current palette-bank layout. Exact mirrored facing rasters share texture pages and use reversed GPU texture coordinates; distinct facings remain separate. Every output frame is reconstructed and checked against its source during conversion. No recorded gameplay routes or research manifests are read.

Verify every page through the runtime storage reader and reconstruct all source actor rasters through the runtime frame catalog:

```sh
.venv/bin/python tools/verify_gpu_actor_pack.py --pack build/asset-regeneration/native_actors/pages.gpu --players build/asset-regeneration/players --enemies build/asset-regeneration/enemies/enemies.frames --pickups build/asset-regeneration/entities/pickups.frames --output build/asset-regeneration/gpu-actor-verification.json
```

The scenery stage builds all 12 native tile banks and ordered depth-packet files from original artwork and maps, then joins them with the native callback definitions in `native_scenery/`. Intermediate static passes exist only during offline conversion. Each pass is Lanczos-resampled across the whole map at 8/25 scale before it is cut into tiles, so tile borders stay seamless; scrolling and fixed backgrounds use the same filter. The runtime uses native tilemaps and GPU depth geometry.

Check the runtime tile/depth loaders on the host:

```sh
.venv/bin/python tools/verify_native_bg_assets.py --study-dir build/asset-regeneration/native_scenery --output build/asset-regeneration/tile-verification.json
.venv/bin/python tools/verify_offline_depth_packets.py --assets-dir build/asset-regeneration/scenery_intermediate/depth --output build/asset-regeneration/depth-verification.json
```

These checks cover packet decoding, caching and malformed inputs under sanitizers; they do not measure DS rendering performance. The optimized ROM icon is included as `ds/icon.png`. To replace it locally with a custom image, optionally run:

```sh
.venv/bin/python tools/icon_build.py --source /path/to/icon.jpg --output ds/icon.png
```

The conversion fits the full image into 32×32 pixels and a 15-color RGB555 palette, reserving palette index zero for transparency.

Assemble converted runtime assets into the source project:

```sh
.venv/bin/python tools/assemble_assets.py --generated build/asset-regeneration --project ds
```

Run this in a checkout without `ds/assets/` or `ds/nitrofs/`; the assembler refuses to overwrite those folders. It copies the runtime files and matching generated headers, and writes `ds/asset-assembly.json` with file sizes and hashes. Player, enemy and pickup banks become compact KFP4/KFE4/KFU4 geometry records during assembly; their pixels are already in the GPU actor pack. Every frame and all resource/animation records are retained. Complete KFP3/KFES/KFSP banks remain in the generation directory for conversion and verification. The runtime has no software decoder for these actors, and the native source-cache arenas have exclusive ownership. Conversion manifests, previews and original files stay outside the ROM. The ISO is the only external game-data input; the optimized banner icon is bundled; no old generated asset folder or research files are required.

Verify the assembled player metadata and native draw submission against the complete generated banks (requires a host C compiler with AddressSanitizer and UndefinedBehaviorSanitizer):

```sh
.venv/bin/python tools/verify_player_metadata.py --players build/asset-regeneration/players --runtime ds/nitrofs/players --output build/player-metadata-verification.json
.venv/bin/python tools/verify_scene_actor_metadata.py --enemies build/asset-regeneration/enemies/enemies.frames --pickups build/asset-regeneration/entities/pickups.frames --runtime ds/nitrofs/scenes --output build/scene-actor-metadata-verification.json
```


## Build

The project uses BlocksDS 1.24.0 and its Wonderful ARM toolchain. Set the toolchain root to your installation. With the generated assets present:

```sh
make -C ds -j4 WONDERFUL_TOOLCHAIN=/path/to/wonderful
```

Output: `ds/Kinder Fresh Adventures.nds`. Copy it to a DLDI-compatible flashcart. Saving uses a raw 8 KiB `.sav` alongside the ROM; the loader must allow filesystem writes. Empty `.sav` placeholders initialize automatically; unrecognized nonempty saves are preserved. Release builds store everything in that one file; no other save folder or files are created or read. Without a valid ROM path from the loader, it uses `kinder_fresh.sav` at the writable drive root. A repeatable two-boot emulator test is documented in [tools/PLAYTEST.md](tools/PLAYTEST.md); physical flashcart persistence still needs verification.

`KF_DEBUG=0` is the default release configuration. The diagnostic overlay and Y toggle compile only with:

```sh
make -C ds -j4 WONDERFUL_TOOLCHAIN=/path/to/wonderful KF_DEBUG=1
```

Changing `KF_DEBUG` rebuilds source objects automatically. The original START menu remains part of normal gameplay in both configurations.


## Development checks

See [the playtest guide](../tools/PLAYTEST.md) for repeatable emulator checks. Emulator timing is not proof of physical DS performance.
