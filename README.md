# pcengine-python

A readable, pure-Python emulator of the **PC Engine / TurboGrafx-16**, to be built as a board on the
family's cores: [huc6280-python](../huc6280-python) for the HuC6280's instruction set (built in
parallel; not read by this phase). The core owns the CPU; this repository will own everything around
it: the 21-bit physical decode and the hardware page, the master clock and the VDC/VCE wait states,
the timer, interrupt controller and I/O port, the **HuC6270 VDC**, the **HuC6260 VCE**, the
six-channel wavetable **PSG**, the HuCard slot and its mappers, the pads, and **documented sockets**
for add-on boards.

**Status (2026-10-23): Phase 0, groundwork only, no emulator code.** The documents in
[`docs/`](docs/README.md) hold what the build needs, every fact with its source and tier;
[docs/handoff-brief.md](docs/handoff-brief.md) is the plan (8 milestones, 20 unknowns, 8 conflicts,
14 open decisions). Measured while gathering: MAME 0.285, Mesen2 (famicom-python's headless build,
after setting the config the DLL lacks), Beetle PCE (Mednafen's core, built from the pinned tree) and
Geargrafx all run here headless; 35 library cards start on all three of the first; the CD boots the
Super System Card screen on four emulators; the only tier-1 (hardware-photographed) judge found is
Chris Covell's CPU timing test.

## Shape: base board plus add-ons (the Sega console pattern)

`pcengine-python` is the base board; **CD-ROM² / Super CD-ROM² / Arcade Card** (`pcenginecd-python`)
and probably the **SuperGrafx** (`supergrafx-python`) are separate boards that pin it through sockets
([docs/sockets.md](docs/sockets.md)). Neither add-on repository exists yet.

| Machine | Phase |
| --- | --- |
| PC Engine, NTSC-J, HuCard: the reference | 1 (milestones M1-M5) |
| TurboGrafx-16 (US): a machine-table row, region bit | 1 |
| SuperGrafx: add-on (or a mode, open decision 6) | M6 |
| CD-ROM², Super CD-ROM², Arcade Card: add-on | M7-M8 |
| PC-FX (shares the VDC family; beyond the 1990 cutoff) | recorded as a possible later consumer only |

## What is fetched

Nothing third-party is committed; ROMs, CD images and the System Card are bring-your-own.
`scripts/fetch_references.py` rebuilds `reference/` and `tests/test_roms/` from
`scripts/pinned_files.json` (12 files by SHA-256: MacDonald's `pcetech.txt` and `sgxtech.txt`,
Covell's CPU test, eight PCEdev wiki pages) and `scripts/pinned_repos.json` (17 repositories at full
commit SHAs, sparse where large: MAME 0.285's PC Engine sources, Mednafen via pce-devel, Beetle PCE,
Geargrafx, ares, Mesen2, the TurboGrafx16 MiSTer core **with its `docs/`** (Hudson's manuals), pce-devel's
research repos, HuC, the 240p Test Suite source, ...):

```sh
python -I scripts/fetch_references.py            # everything missing (~130 MB)
python -I scripts/fetch_references.py --verify   # check what is present
```

It needs `git` and `curl`. The wiki pages are live: a changed page is reported and kept.

## Scripts

| Script | What |
| --- | --- |
| `scripts/fetch_references.py` | the pinned references |
| `scripts/count_carts.py` | the census: HuCards by MAME software list (CRC), CDs by hash then title |
| `scripts/mame_trace.py` | MAME 0.285 per-instruction HuC6280 trace for `pce`, `tg16`, `sgx` ([docs/mame-oracle.md](docs/mame-oracle.md)) |
| `scripts/mesen_run.py` | a card on Mesen2's `MesenCore.so` headless, frame to PNG (sets the PC Engine config the DLL lacks) |
| `scripts/libretro_run.py` | a card or CD on a libretro core (Beetle PCE, Geargrafx) through a ctypes host |
| `scripts/detectors_compare.py` | MAME, Mesen2 and Beetle PCE against each other on a card list |

Scripts need Python >= 3.11, Pillow for pictures, and the system's `mame`, `7z` and (for CDs) `chdman`.
Run any Python that reads `reference/` with `python -I`.

## Floors and rules

Python **>= 3.11** (the newest PyPy supports); ruff `py311`. Modern over compatibility. Reference boards
are correct, not fast. Never copy a chip file between repositories. ROMs, CHDs, BIOS: never committed.
Local git only until a rung says otherwise.
