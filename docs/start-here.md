# Start here: the machine, the clocks, the module shape

Read [README.md](../README.md) first, then this, then [memory-map.md](memory-map.md),
[sockets.md](sockets.md), [vdc.md](vdc.md), [vce.md](vce.md), [psg.md](psg.md),
[cartridge.md](cartridge.md), [cd.md](cd.md), [validation.md](validation.md),
[mame-oracle.md](mame-oracle.md), and last [handoff-brief.md](handoff-brief.md) (milestones, the
U and C lists, the open decisions). Nothing here is code: this is Phase 0.

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

**Scope proposal (open decision 2)**: PC Engine (NTSC-J) first, TurboGrafx-16 as a row from day
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

## The module shape (proposed)

```
pcengine_python/
  machine.py     the machine table (clocks, RAM size, region bit, VDC count)
  board.py       the page table (8192 x 256-byte pages), clock, hold(), IRQ lines
  cpu_io.py      timer, $1400 IRQ mask/status, $1000 I/O port, the I/O buffer   (board-owned, pin-shaped)
  vdc/           HuC6270 (instances): regs, vram, bat/cg render, sprites, dma, timing   (import boundary)
  vce.py         palette, dot clock, 262/263, output
  psg/           C6280 six channels (import boundary)
  cards/         standard ROM + mirroring, SF2, Populous, Tennokoe, system card
  sockets.py     the Protocols and the test-only fakes
  pads.py        2-button, multitap, 6-button, mouse
  system.py      run_frame, the scheduler
```

with `huc6280-python` (the CPU core) pinned by git revision and nothing copied. Module state is
forbidden (a second VDC is a second instance). The VDC and the PSG sit behind import-boundary tests so
a later extraction (PC-FX for the VDC family; nothing for the PSG) is a move, not a rewrite.

## Performance: correct, not fast

The reference board is **correct, not fast**; speed is a later `pcengine-rust` / `-fast` project's job.
For scale (an extrapolation, **nothing here was measured on a PC Engine board**): famicom-python,
built on the same 6502-python frame, runs a NES at 0.89x real time on PyPy and 0.15x on CPython with
the full PPU/APU, and does 5.4 M CPU cycles/s on PyPy (`famicom-python/docs/validation.md`). A PC Engine
CPU in high speed makes 7.16 M cycles/s, so the **CPU alone is ~0.75x real time on PyPy and
~0.33x on CPython**, before the VDC (a line is 42-85 character cycles) and the PSG; expect the
whole board around 0.2-0.5x on PyPy and 0.05-0.1x on CPython until the VDC steps by character cycle
and not by dot. That is acceptable for a reference; the milestones are judged by traces, not by
frames per second.

## Floors and rules (from Aubrey)

Python floor **3.11** (newest PyPy supports): `requires-python = ">=3.11"`, ruff `target-version =
"py311"`. Modern forms over compatibility shims. Reference boards are correct, not fast. Never copy a
chip file between repositories: extract on the second consumer. **ROMs, CHDs, the System Card and any
BIOS are bring-your-own, read in place by path, never committed** (the `.gitignore` refuses their
extensions). Local git only until a rung says otherwise (open decision 8). No dangerous-looking shell
one-liners in scripts or docs.
