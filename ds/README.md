# Nintendo DS runtime

Runtime C and ARM assembly live in `source/`; host-side loader tests live in `tests/`.
See [build instructions](../docs/BUILDING.md) and [development checks](../tools/PLAYTEST.md).

With generated assets assembled, run `make -C ds -j4` from the repository root.
Output: `Kinder Fresh Adventures.nds` in this directory, with a SHA-256 sidecar.
`build/` contains the SDK ROM, ELF, map and object intermediates; all are ignored.

`KF_DEBUG=0` is the default release build. `KF_DEBUG=1` opts into diagnostics;
changing the flag rebuilds source objects. START remains the ordinary game menu.
