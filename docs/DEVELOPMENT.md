# Repository layout

| Path | Purpose | Included in Git |
|---|---|---|
| `ds/source/` | Nintendo DS runtime C and ARM assembly | Yes |
| `ds/tests/` | Host-side runtime tests | Yes |
| `tools/` | Asset conversion, validators and current emulator tools | Yes |
| `docs/` | Build documentation and a framed gameplay screenshot | Yes |
| `VERSION`, `CHANGELOG.md` | Release version and notes | Yes |
| `ds/icon.png` | Optimized ROM banner icon | Yes |
| `ds/assets/`, `ds/nitrofs/` | Generated runtime assets | No |
| `ds/build/`, `ds/*.nds`, `ds/*.sav` | Build output and saves | No |
| `build/`, `.venv/`, `generated/` | Local conversion output and Python environment | No |
| `.local/` | Original inputs, extracted files, studies, dumps, archived experiments and local reports | No |

The public tool directory remains flat because converters and validators import shared modules from it. Historical experiments live privately under `.local/research/archive/retired_tools/` rather than becoming part of the public development API.

The root ignore rules use an allowlist. New top-level files and generated data are ignored by default. Before committing, run:

```sh
python3 tools/verify_source_tree.py
```

The checker inspects tracked and untracked Git candidates for unexpected paths, symlinks and binary payloads. It allows only the approved framed gameplay WebP and the bundled 32×32 ROM icon as image files. It cannot establish ownership or licensing of source text; review the initial Git inventory before publication.

Builds keep the SDK's space-free intermediate ROM in `ds/build/kinder_fresh.nds`, deduplicate identical NitroFS payloads, then publish the human-readable filename atomically. The ROM checksum sidecar is generated locally and ignored. Diagnostics remain opt-in.
