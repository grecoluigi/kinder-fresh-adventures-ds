# Emulator playtests

Requirements: macOS, melonDS at `/Applications/melonDS.app`, a built ROM with matching ELF/map, the asset Python environment, and decoded map data. The current automated controller reads map data at `generated/maps/`; in a clean checkout, link that path to the `maps/` directory produced by `prepare_assets.py`.

From the project root:

```sh
.venv/bin/python tools/playtest.py --world all --stage both --include-arenas --ticks 600 --check-hud --continuous-smoke 1
```

The runner builds the ROM unless `--no-build` is given, drives the four main levels, tutorials and arenas, writes JSON/CSV logs, and closes each owned emulator session. It refuses to interrupt an existing emulator or continue if ROM/ELF hashes change during a run. Emulator output is drained into a bounded 64 KiB tail. Preferences are updated atomically; GDB is disabled after the run and the original DLDI setting is restored. New sessions are deferred below 1 GiB free disk space.

For the Makefile target, select the Python environment explicitly:

```sh
make -C ds playtest KF_PYTHON="$(pwd)/.venv/bin/python"
```

Ordinary `make -C ds` never starts an emulator. No background watcher is installed.

## Scope and controls

The controller uses original tile/object positions to jump near gaps and hazards, shoot, attempt character switching when stuck, and wait during dialogue. Scenario setup selects a route, initializes tutorial flags and fixes the RNG seed in emulator RAM. Arena setup requests the existing arena transition. The harness uses RAM input patches and disables DLDI to avoid updating real saves. It does not solve every puzzle or boss; damage and death remain possible and are reported.

Each scenario checks native tilemap/cache state and three START pause/resume cycles. `--check-hud` also compares actual bottom-screen VRAM with the current HUD state. `--continuous-smoke` adds four uninterrupted intervals (idle, right+jump, left+jump, idle), then checks that updates and renders advanced. It accepts 0–5 seconds per interval. Per-frame counter CSV data excludes these post-route intervals.

These are bounded regression probes, not complete playthroughs, original Windows raster parity, listening tests or physical-device FPS measurements. A zero exit status means the scripted session completed and produced logs. `issues` separately reports sampled FPS below 30 and audio underruns. Exceptions, stalls and host timeouts fail the run.

## Artifacts and logs

`--artifact-dir PATH --no-build` selects another build containing `Kinder Fresh Adventures.nds` (older private artifacts may use `kinder_fresh.nds`), `build/kinder_fresh.elf` and `build/kinder_fresh.map`. Telemetry uses that exact artifact directory. HUD comparisons use the project's matching assets.

Logs default to `research/playtests/<UTC timestamp>-<ROM SHA prefix>/`; use `--output-dir PATH` to choose a fresh directory.

| File | Contents |
|---|---|
| `run.json` | ROM/ELF hashes, outcomes, performance/audio flags, emulator shutdown status |
| `<world>-<stage>.json` | Samples, native render checks, HUD checks and uninterrupted intervals |
| `<world>-<stage>.csv` | Position, health, update/render counts, phase timings and audio underruns |
| `<world>-<stage>.jsonl` | Streamed inputs and samples, including partial failed runs |
| `<world>-<stage>.runner.log` | Controller progress and errors |
| `<world>-<stage>.emulator-tail.log` | Last 64 KiB of emulator output |

The on-screen Y diagnostic toggle requires `KF_DEBUG=1`. Automated debugger telemetry can inspect a release build without enabling the diagnostic UI. After emulator checks, hardware testing and complete playthroughs are still required.

## Save persistence across emulator restarts

```sh
.venv/bin/python tools/playtest_save.py --output-dir build/save-reboot-check
```

This creates a private256MiB FAT16 image, boots the current ROM, confirms a scripted qualifying name through the production UI, and reads the resulting8KiB save directly from the card image. It independently checks both record CRCs. A second emulator process must reload all1,692payload bytes, including the confirmed name. The image needs space for the emulator's padded copy of the ROM as well as the save; undersized cards can leave an empty file after an out-of-space error.

The runner logs both boots, restores emulator preferences with GDB disabled, and closes owned sessions. It deletes the private card after success and retains it on failure for diagnosis; it never opens a user card image or save. The result/name are supplied in debugger RAM. This verifies the production commit/reload path, rather than gameplay completion, touch typing or physical flashcart durability.

Add `--empty-save` to seed a zero-byte `kinder_fresh.sav` before the first boot and verify recovery from a loader placeholder or failed initial creation. The second boot still requires a complete byte-for-byte state reload.

## Native source-cache occupancy

Use a separate diagnostic run to log retained ranges, record limits and arena byte occupancy every 30 updates:

```sh
python tools/playtest.py --no-build --world ice --ticks 900 --cache-occupancy
```

This reads the ARM32 cache table through the debugger and checks its linked size and arena bounds. It adds debugger traffic; do not use this run for ordinary timing comparisons. The JSON/CSV samples include `native_cache_entries`, `native_cache_resident_bytes`, `native_cache_capacity_bytes` and `native_cache_record_limit_reached`. A full record table with free arena bytes is evidence of a record-capacity limit; it does not alone identify which resources should remain resident.

## Statistical CPU profile

```sh
.venv/bin/python tools/playtest.py --no-build --world all --stage main --ticks 600 --pc-samples --output-dir build/pc-profile
.venv/bin/python tools/report_pc_profile.py build/pc-profile/*.pc.jsonl
.venv/bin/python tools/compare_phase_timing.py BASELINE_DIR CANDIDATE_DIR
```

`--pc-samples` interrupts at random points after most frame boundaries and logs PC/LR/CPSR. Emulated time is frozen while halted, so shares estimate emulated ARM9 time; they are not hardware measurements. BIOS/`swiIntrWait` samples are idle VBlank waits. The comparison tool separates cold first renders from steady-state medians and p95.

## Headless gameplay routes

```sh
python3 tools/playtest_main_host.py --world 1 --route /path/to/route.json --finish-boss --output .local/playtests/ice-logic.json
```

This compiles current production gameplay on macOS, loads generated collision,
actor geometry, scene definitions and sound durations, then drives `world_tick`
with ordinary input bits. A route JSON contains a `world` index (0–3) and
`waypoints` with native `x`/`y` coordinates; the controller also supports
ingredient targets, character selection, climbing and moving-platform boarding.
The optional boss continuation currently supports Jungle and Ice.

The host backend validates scene definitions and aborts if rendering is called.
It provides no software renderer, screenshots, GPU checks or audible output.
JSON/CSV logs record navigation, damage, inventory, transitions and results;
controller/route snapshots and production source hashes accompany each run.
The Jungle route retains its earlier same-layer threat and shooting policy;
Ice and Factory use the later cross-layer threat policy. These affect the bot,
not game collision or enemy logic. Failed routes alone do not prove port defects.
Full DS playthroughs, visuals, sound listening and hardware timings require
separate verification.


To check the SDK name-entry keyboard over each level's backdrop, run the UI
probe with `--world 0`, `1`, `2` or `3` (Jungle, Ice, Factory, Fantasy):

```sh
.venv/bin/python tools/playtest_ui.py --artifact-dir ds --world 0 --output .local/playtests/keyboard-jungle.json
```

The probe checks the level crop and palette byte-for-byte in the upper64KiB of
sub-screen bank C, separately from the keyboard tiles/map in the lower64KiB.
It also checks keyboard/background layer priority and return-to-menu ownership.
Input is supplied in debugger RAM; this does not verify physical touch typing.
