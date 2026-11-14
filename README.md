# pcengine-python

Public at https://github.com/alewman/pcengine-python since 2026-11-05 (published by Claude Sonnet 5.5
for alewman; no ROMs, System Card or other BIOS are included, bring your own).

A readable, pure-Python emulator of the **PC Engine / TurboGrafx-16**, built as a board on the
family's CPU core, [huc6280-python](https://github.com/alewman/huc6280-python) (pinned by commit,
nothing copied). The core owns the CPU; this repository owns everything around it: the 21-bit
physical decode and the hardware page, the master clock and the VDC/VCE wait states, the timer,
interrupt controller and I/O port, the **HuC6270 VDC**, the **HuC6260 VCE**, the six-channel
wavetable **PSG**, the HuCard slot and its mappers, the pads, save states, and **documented
sockets** for add-on boards.

**Status (2026-11-12, release 0.2.0): built; milestones M1 to M5 are closed.** It is a reference
board: correct first, slower than real time (see [docs/start-here.md](docs/start-here.md)
"Performance"). Every fact in [`docs/`](docs/README.md) has its source and tier; nothing here was
run on a real console.

| Milestone | Result | Record |
| --- | --- | --- |
| M1 clocks, timer, interrupts, raster | closed as a **documented provisional**: Covell's CPU timing test (the only hardware-photographed judge) is drawn with its splits within 0.6 to 6.6 dots of the photographs, not within the one cycle the exit asked for | [m1-record](docs/m1-record.md) |
| M2 background, M3 sprites | 18 titles (27 pictures) pixel-identical to Mesen2 and Beetle PCE at the 9-bit palette value | [m2](docs/m2-record.md), [m3](docs/m3-record.md) |
| M4 PSG | reproduces MAME's and Mednafen's chips step for step, each with its own switches, on five games (emulator tier only) | [m4-record](docs/m4-record.md) |
| M5 mappers, library sweep, lockstep | all 179 library HuCards at frames 300 and 600: **170 identical** to Mesen2, 9 different (3 for the missing backup RAM of a bare console, 6 triaged); lockstep with Mednafen holds for 20 million instructions on R-Type and stops earlier on five other games, for named reasons | [m5-record](docs/m5-record.md), [m5-lockstep-record](docs/m5-lockstep-record.md) |
| Save states | a saved and loaded run continues bus cycle for bus cycle on 18 of 18 titles | [start-here](docs/start-here.md) "Save states" |

250 tests on CPython and PyPy; CI runs them on PyPy 3.11.

## Install and run

```sh
pip install "pcengine-python @ git+https://github.com/alewman/pcengine-python@v0.2.0"
```

Not on PyPI (the core is pinned by git commit). Python 3.11 or newer; PyPy is several times faster.

```python
from pcengine_python import pads
from pcengine_python.board import Board
from pcengine_python.cards import card_from_path
from pcengine_python.machine import PC_ENGINE  # or TURBOGRAFX_16 for a US card
from pcengine_python.state import load_state, save_state
from pcengine_python.system import build

pad = pads.Pad2()
board = Board(PC_ENGINE, card=card_from_path("your-card.pce"), pad=pad)
system = build(board)  # the HuC6280 core on the board
for _ in range(300):
    system.run_frame()
frame = board.capture.last_frame  # 242 rows of 9-bit palette values
samples = board.take_audio()  # stereo, 44.1 kHz
pad.pressed = pads.RUN  # hold a button for the next frames
state = save_state(system)  # the whole console as bytes; load_state() puts it back
```

There is no window or player yet: the board is a library, and the family's front end is a later
project.

## Shape: base board plus add-ons (the Sega console pattern)

`pcengine-python` is the base board. The **SuperGrafx**
([supergrafx-python](https://github.com/alewman/supergrafx-python)) and the **CD-ROM² / Super
CD-ROM² / Arcade Card** ([pcenginecd-python](https://github.com/alewman/pcenginecd-python)) are
separate boards that pin this one and plug into its sockets ([docs/sockets.md](docs/sockets.md));
both are built (private repositories at the time of writing).

| Machine | Where |
| --- | --- |
| PC Engine, NTSC-J, HuCard: the reference | here |
| TurboGrafx-16 (US): a machine-table row, region bit | here |
| SuperGrafx | supergrafx-python |
| CD-ROM², Super CD-ROM², Arcade Card | pcenginecd-python |
| PC-FX (shares the VDC family; beyond the 1990 cutoff) | recorded as a possible later consumer only |

Judges that run here headless: MAME 0.285, Mesen2, Beetle PCE (Mednafen's core, built from the
pinned tree), Mednafen 1.32.1 and Geargrafx; the only hardware-photographed judge found is Chris
Covell's CPU timing test.

## What is fetched

Nothing third-party is committed; ROMs, CD images and the System Card are bring-your-own.
`scripts/fetch_references.py` rebuilds `reference/` and `tests/test_roms/` from
`scripts/pinned_files.json` (12 files by SHA-256: MacDonald's `pcetech.txt` and `sgxtech.txt`,
Covell's CPU test, eight PCEdev wiki pages) and `scripts/pinned_repos.json` (17 repositories at full
commit SHAs, sparse where large: MAME 0.285's PC Engine sources, Mednafen via pce-devel, Beetle PCE,
Geargrafx, ares, Mesen2, the TurboGrafx16 MiSTer core **with its `docs/`** (Hudson's manuals), pce-devel's
research repos, HuC, the 240p Test Suite source, ...):

```sh
python -I scripts/fetch_references.py            # everything missing (~100 MB before building the cores)
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
| `scripts/m2_ours.py`, `m2_refs.py`, `m2_compare.py` | a card's frame on this board, on Mesen2 and Beetle PCE, and their comparison at the 9-bit palette value (the picture gate) |
| `scripts/m5_sweep.py`, `m5_summary.py` | the library sweep against Mesen2 and Beetle PCE, and its counts |
| `scripts/lockstep.py`, `mame_lockstep.py`, `mednafen_record.py` | instruction-by-instruction lockstep against Mednafen and MAME |
| `scripts/covell_calibrate.py`, `covell_photo_splits.py` | Covell's CPU timing test against his photographs |
| `scripts/psg_record.py`, `psg_compare.py`, `psg_referees/` | PSG register streams against MAME's and Mednafen's chips |
| `scripts/frame_png.py`, `pixelpath_bench.py` | a saved frame as a PNG; the cost of the pixel socket |
| `scripts/provenance_check.py` | looks for code copied or transcribed from the reference trees (GPL and LGPL emulators): [docs/provenance.md](docs/provenance.md) |
| `scripts/presses.py` | scripted pad input (`run@400+10`) in one spelling for the board, Mesen2 and Beetle PCE: `--press` on the picture scripts |
| `scripts/state_roundtrip.py` | save states proven complete: a saved and loaded run against the run that was not interrupted, bus cycle for bus cycle ([docs/start-here.md](docs/start-here.md) "Save states") |

Scripts need Python >= 3.11, Pillow for pictures, and the system's `mame`, `7z` and (for CDs) `chdman`.
Run any Python that reads `reference/` with `python -I`.

## Floors and rules

Python **>= 3.11** (the newest PyPy supports); ruff `py311`. Modern over compatibility. Reference boards
are correct, not fast. Never copy a chip file between repositories. ROMs, CHDs, BIOS: never committed.
Paths under `/data/emu/` in the documents and script defaults are the author's machine: read
them as "your checkout" and "your ROM directory".
