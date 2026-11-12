# Start here: the machine, the clocks, the module shape

Read [README.md](../README.md) first, then this, then [memory-map.md](memory-map.md),
[sockets.md](sockets.md), [vdc.md](vdc.md), [vce.md](vce.md), [psg.md](psg.md),
[cartridge.md](cartridge.md), [cd.md](cd.md), [validation.md](validation.md),
[mame-oracle.md](mame-oracle.md), and last [handoff-brief.md](handoff-brief.md) (milestones, the
U and C lists, the decisions taken; a historical brief). The board is built: these documents
describe it and say where each fact comes from.

## The machines as data

One board, a machine table. Facts are the pins and clocks of [memory-map.md](memory-map.md); the
differences are rows, not forks.

| | PC Engine (NEC, 1987, Japan) | TurboGrafx-16 (NEC, 1989, US) | SuperGrafx (1989, Japan) | with CD-ROM² / Super / Arcade Card |
| --- | --- | --- | --- | --- |
| Master clock | 21.477272 MHz (6 x NTSC burst) | same | same | same; the CD unit has its own clocks (U8) |
| CPU | HuC6280 (HuC6280A on later units: U6) | same | HuC6280A | same |
| I/O port D6 (country) | 1 | **0** (US games check it) | 1 (switch for compat mode) | unchanged |
| Work RAM | 8 KiB (mirrored in `$F8-$FB`) | 8 KiB | **32 KiB** | + 64 KiB CD RAM (+192 KiB Super System Card) |
| VDC | 1 x 64 KiB VRAM | 1 | **2 x 64 KiB + HuC6202 VPC** | unchanged |
| Card data pins | ascending | descending (converter in the dump) | PC Engine order | |
| Lines per frame | 263 / 262 (VCE bit 2: C3) | same | same | same |

**Scope**: PC Engine (NTSC-J) first, TurboGrafx-16 as a row from day
one (a region flag on the I/O port: cheap and 93 of the 179 library cards are US), SuperGrafx and the
CD family as add-on boards ([sockets.md](sockets.md)). There is no PAL machine.

## Clocks and time

Everything is counted in **master clocks** (21.477272 MHz). A line is **1365** of them; a frame 263
lines (358,995; 59.826 Hz) or 262. The CPU takes a cycle every 12 (low) or 3 (high) master clocks;
`CSL`/`CSH` switch, power-up is **low**. The VCE divides by 4/3/2 for the dot. The PSG runs at
master/6, the timer at master/3072 whatever the CPU does. The board owns the clock: the core calls once
per CPU cycle with a 21-bit physical address and the board advances time, adds the VDC/VCE
one-cycle penalty ([memory-map.md](memory-map.md), C4) and VDC `/BUSY` waits (RDY), and raises
IRQ1/IRQ2/timer. **One timeline in master clocks, no second domain in the base board**; the CD adds
domains ([sockets.md](sockets.md)).

## The module shape

```
pcengine_python/
  machine.py     the machine table (clocks, RAM size, region bit, VDC count)
  board.py       the one timeline in master clocks, the bus callbacks, hold(), IRQ lines
  pagetable.py   8192 x 256-byte pages: who answers which physical address; work RAM
  hardware_page.py  the decode of bank $FF (VDC, VCE, PSG, timer, I/O port, interrupt registers)
  cpu_io/        timer, $1402/$1403 interrupt registers, $1000 I/O port, the I/O buffer   (board-owned, pin-shaped)
  vdc/           HuC6270 (instances): regs, chip, sequencer (timing), background, sprites, dma   (import boundary)
  vce.py         palette, dot clock, 262/263 lines
  video.py       the frame timeline and the line capture (what a frame is)
  psg/           C6280 six channels (import boundary)
  mixer.py       the `audio_sources` list mixed to 44.1 kHz stereo
  cards.py       standard ROM + mirroring, SF2, Populous, Tennokoe
  sockets.py     the Protocols add-ons plug into (the test-only fakes are tests/fake_devices.py)
  pads.py        2-button, 6-button, multitap
  system.py      the CPU on the board, run_frame
  state.py       save states: the whole console as bytes, and back
```

with `huc6280-python` (the CPU core) pinned by git revision and nothing copied. Module state is
forbidden (a second VDC is a second instance). The VDC and the PSG sit behind import-boundary tests so
a later extraction (PC-FX for the VDC family; nothing for the PSG) is a move, not a rewrite.

## Save states

`pcengine_python.state` (the family's standard, first built for famicom-python): `save_state(system)`
gives the whole console between two instructions as bytes, `load_state(system, data)` puts a system
built the same way (machine row, card, add-on) into that state.

```python
from pcengine_python.state import load_state, save_state

data = save_state(system)  # zlib-compressed JSON, 20-110 KiB for a HuCard
load_state(another_system, data)  # the same card on the same machine; continues identically
```

- **What it is.** A walk of the object graph from the board: every attribute of every object of this
  package (and of an add-on that has registered itself), as plain data. The CPU is saved as
  huc6280-python's `CPUState`. Callables (the wiring) are not saved; loading writes into the
  existing objects, so the wiring of the system loaded into stays as it was built.
- **No ROM in a state.** An immutable `bytes` of 8 KiB or more is saved as its SHA-1 and length, and
  loading refuses a system that holds other bytes there: that is how a state of another card is
  recognised. A disc is named by its table of contents only (the add-on's `Disc.state_identity`).
- **Refused, with a `StateError`:** another machine row, another card, another disc, an add-on that
  is not imported, and a machine built another way (a state made with an Arcade Card loaded into a
  machine without one). A state holds no code and can name only classes of the registered packages.
- **The proof is equivalence** (`scripts/state_roundtrip.py`, `tests/test_state.py`): a run saved in
  the middle of a frame and loaded into a fresh system, and into one that had run something else,
  continues exactly as the run that was never interrupted: every CPU bus cycle (address, value,
  direction, master clock), the picture, the mixed audio and the CPU's state of every frame after;
  and the loaded system, saved at once, gives the same bytes back.
- **Measured (2026-11-12, PyPy):** the 18 picture-gate titles, saved 148-2,477 instructions into
  frame 300 with pad input before and after, 60 frames compared: 18 of 18 equal, on a fresh system
  and on one that had run (states of 23-110 KiB). The add-ons' own runs are in their start-here.
  Mapper cards (Street Fighter II', Populous, Tennokoe) are covered by unit tests of their registers
  and RAM, not by a run of the real cards.
- **For an add-on:** call `register_package("your_package")` in its `__init__`; give media classes
  `STATE_FIXED = True` and a `state_identity()`; keep state in attributes that are data (numbers,
  bytes, lists, dicts, deques, enums, dataclasses, objects of the package), not in closures. An
  object that can appear while the machine runs must be a dataclass (the loader builds nothing else).
- **Not promised:** a state is for the same revision of the code. The version number in the header
  changes when the format does, not when a chip gains an attribute; a state from an older revision
  may load and continue differently. Nothing here is a format other emulators read.

## Performance: correct, not fast

The reference board is **correct, not fast**; speed is a later `pcengine-rust` / `-fast` project's job.
For scale (an extrapolation, **nothing here was measured on a PC Engine board**): famicom-python,
built on the same 6502-python frame, runs a NES at 0.89x real time on PyPy and 0.15x on CPython with
the full PPU/APU, and does 5.4 M CPU cycles/s on PyPy (`famicom-python/docs/validation.md`). A PC Engine
CPU in high speed makes 7.16 M cycles/s, so the **CPU alone is ~0.75x real time on PyPy and
~0.33x on CPython**, before the VDC (a line is 42-85 character cycles) and the PSG; expect the
whole board around 0.2-0.5x on PyPy and 0.05-0.1x on CPython until the VDC runs on line events
(a few per line) and not by dot. That is acceptable for a reference; the milestones are judged by traces, not by
frames per second.

## Floors and rules (from Aubrey)

Python floor **3.11** (newest PyPy supports): `requires-python = ">=3.11"`, ruff `target-version =
"py311"`. Modern forms over compatibility shims. Reference boards are correct, not fast. Never copy a
chip file between repositories: extract on the second consumer. **ROMs, CHDs, the System Card and any
BIOS are bring-your-own, read in place by path, never committed** (the `.gitignore` refuses their
extensions). No dangerous-looking shell
one-liners in scripts or docs.
