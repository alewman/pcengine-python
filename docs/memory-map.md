# The CPU-side map and bus: what the board decodes, and who owns what

Every fact is labelled with its source tier ([validation.md](validation.md)): **[mfr]**
Hudson manual or schematic, **[hw]** MacDonald's notes ("tested and verified on a
TurboGrafx-16 console", his words, no captures published), **[doc]** community document,
**[emu]** read from an emulator's source. Nothing here was measured on a console by us (we
have none).

## The HuC6280 as the board sees it

A 65C02 core with a memory management unit in front of it: eight 8-bit mapping registers
MPR0-MPR7 translate the 16-bit logical address (page = A15-A13) into a **21-bit physical
address** (bank = 8 bits, offset = 13 bits). So the physical space is 256 banks of 8 KiB =
2 MiB. [mfr: HuC6280 hardware manual; doc: pce.nesdev.org "CPU addresses"] (The wiki page
`CPU addresses` carries a spam paragraph: ignore it.)

- Zero page and stack are **fixed at logical `$2000-$21FF`** (so they live in whatever bank
  MPR1 selects), and the vectors are at `$FFF6-$FFFF`: IRQ2/BRK `$FFF6`, IRQ1 `$FFF8`,
  timer `$FFFA`, NMI `$FFFC`, reset `$FFFE`. [doc: wiki "CPU addresses"]
- On power-up MPR7 = 0 and the other MPRs are random; A, X, Y, S random; P has T and D clear,
  I and B set. [hw: pcetech §2]
- `ST0/ST1/ST2` write straight to physical `$1FE000/2/3` (the VDC), **not translated** through
  the MMU. [hw: pcetech §2] The core therefore emits physical addresses; nothing board-side
  has to special-case them.
- Block transfers (`TII TDD TIN TIA TAI`) cannot be interrupted, push Y/A/X first and pop them
  after; reads of `$0800-$1400` in the hardware page **by a block transfer** return 0 and do not
  touch the I/O buffer; writes work. [hw: pcetech §2]
- Speed: `CSL` = low (master/12 = 1.79 MHz, the **power-up** state), `CSH` = high (master/3 =
  7.16 MHz). The timer does not follow it (master/3072). [hw: pcetech §2.4; doc: wiki "Timing"]

## Physical map (bank = physical >> 13)

| Banks | Contents | Source |
| --- | --- | --- |
| `$00-$7F` | HuCard ROM (1 MiB window; ROMs under 1 MiB are mirrored, layout depends on the card: [cartridge.md](cartridge.md)). PA20 is the card's chip enable | [hw], [doc: wiki "HuCard pinout"] |
| `$80-$87` | unmapped on a stock PC Engine; **64 KiB CD RAM** with a CD unit (Arcade Card Duo also decodes here) | [doc: wiki "CPU memory map"], [emu: MAME `pce.cpp` `0x100000-0x10ffff`] |
| `$68-$7F` | **192 KiB RAM on a Super System Card** (overrides ROM mirror space) | [hw: pcetech §8.1] |
| `$F7` | `$1EE000-$1EE7FF`: 2 KiB backup RAM (CD unit; locked at power-up) | [hw: pcetech §8] |
| `$F8` | work RAM 8 KiB; `$F9-$FB` mirror it (PC Engine, TG-16, CD); **SuperGrafx: 32 KiB real** | [hw: pcetech §3, sgxtech], [doc: wiki] |
| `$FF` | hardware page | below |
| others | unmapped: read `$FF` | [hw] |

Unmapped reads return `$FF` [hw: pcetech §3], with one caveat (the I/O buffer below).
Pin-level: `/CER` is the **RAM** chip enable for banks `$F8-$FB`, `/CE7` the VDC
(`$FF:0000-03FF`), `/CEK` the VCE (`$FF:0400-07FF`); on the HuCard edge connector PA20 is /CE
and `/CD` is grounded by a card so the CD unit can tell one is inserted. [doc: wiki pinouts]

## The hardware page (`$FF:0000-1FFF`)

| Offset | Device | Mirroring | Notes |
| --- | --- | --- | --- |
| `$0000-$03FF` | VDC | 4 bytes (`$00` register select / status, `$02` data LSB, `$03` data MSB; `$01` reads 0) | an extra CPU cycle on every access [hw]; SuperGrafx re-decodes this block ([sockets.md](sockets.md)) |
| `$0400-$07FF` | VCE | 8 bytes | extra cycle too [hw] |
| `$0800-$0BFF` | PSG (in the CPU) | | [psg.md](psg.md) |
| `$0C00-$0FFF` | timer | 2 bytes | |
| `$1000-$13FF` | I/O port | one register | |
| `$1400-$17FF` | interrupt controller | 4 bytes | |
| `$1800-$1FFF` | unmapped, `$FF`; the CD interface is `$1800-$18FF`, Arcade Card ports `$1A00-$1AFF`, Super System Card id registers `$18C1-$18C6` | | [cd.md](cd.md) |

**The I/O buffer** [hw: pcetech §3 note 1]: the last value read from or written to
`$0800-$17FF` is held in an 8-bit buffer. `$0800-$080F` read as the buffer (all 8 bits),
`$0C00/$0C01` return it in bit 7, `$1400/$1401` return it entirely, `$1402/$1403` in the upper five
bits; `$1000` never does. Games that read these locations get buffer bits where the manual says
"unused". Pcetech §3 gives a worked example; it is the first unit test.

**Extra VDC/VCE cycle**: "When accessing the VDC or VCE, an additional cycle is taken ... for
reads and writes (regardless of addressing mode) and instruction execution (e.g. `jsr $0002`)"
[hw: pcetech §3 note 3; MAME's h6280 has `check_vdc_vce_penalty`, `ST0/1/2` cost 4+1 [emu]].
ares charges the penalty only when the VDC is not in burst mode [emu: `ares/pce/vdp/vdc.cpp`
l.116, 154]: a conflict, C4 in the [handoff brief](handoff-brief.md).

## I/O port (`$FF:1000`) [hw: pcetech §4; sgxtech]

Reads: D7 CD-unit sense (1 = **not** attached; the SuperGrafx text says the opposite polarity in
one sentence: C6), D6 country (1 = PC Engine, 0 = TurboGrafx-16), D5-D4 always 1, D3-D0 pad
pins. Writes: D1 = CLR, D0 = SEL (and, on the SuperGrafx's S-EXP port, D7-D2 are outputs too).
The **US console's country bit makes US games refuse to run on a PC Engine**: measured here
(2026-10-23, MAME 0.285): every `(USA)` HuCard of the library shows a black screen under the
`pce` driver and runs under `tg16`; the image bytes are the same. [emu, inference: a region
check; not disassembled]

Pads: a 2-button pad answers SEL=1: Up/Right/Down/Left, SEL=0: I/II/Select/Run (active low), with
CLR high forcing D3-D0 to 0; the **multitap** (5 pads) advances a counter on each SEL 0 to 1 while
CLR is low and resets on CLR 0 to 1 with SEL high; the first `$01` write returns zeros even
though CLR is low (a quirk, pcetech §4). The 6-button Avenue Pad, mouse and the rest of the
signalling: `reference/src/pce-controller-info` (pce-devel, community-measured) and MAME's
`pce_avenue_pad_6`/`pce_arcade_pad_6`/`pce_multitap` devices. A game's `PHA PLA NOP NOP` after
changing SEL is the settle delay a board must not assume away (the pad mux is slow).

## Interrupts [hw: pcetech §2.1; doc: wiki pinouts]

| Line | Source | Vector |
| --- | --- | --- |
| IRQ1 | VDC (`/IRQ`) | `$FFF8` |
| IRQ2 | HuCard and expansion port (CD unit: ADPCM and CD interface), and `BRK` | `$FFF6` |
| TIQ | the CPU's own timer | `$FFFA` |
| NMI | **not connected** [hw] / "from the expansion port" [doc: wiki CPU pinout, EXT BUS pinout]: C2 | `$FFFC` |

`$1402`: bit 2 timer, bit 1 IRQ1, bit 0 IRQ2: **1 = disabled**. `$1403`: reads pending state
(bits 2-0; the *line*, even when masked), **any write acknowledges the timer**. A level is held
until its source is acknowledged (VDC: by reading the status port); an unacknowledged IRQ
re-enters after every instruction. Interrupts push P with B clear and then the CPU clears D and T
and sets I. [hw: pcetech §2]

## Timer [hw: pcetech §2.2]

7-bit down counter, one tick per **1024 CPU-high-clock cycles** (master/3072, 6.99 kHz) whatever the
speed. `$0C00` = reload value (0 counts as 1, `$7F` as 128; bit 7 reads the I/O buffer),
`$0C01` bit 0 = enable. The interrupt fires when the counter goes from 0 to `$7F`, and it is
reloaded at that moment and keeps counting inside the handler. Reading returns the live count.
Disabled: it freezes; re-enabled: reloaded from the last written latch. Power-up: count 0,
disabled.

## Clocks [doc: wiki "Timing"; hw: pcetech §2.4]

Master 21.477272 MHz (6 x NTSC colour burst, 315/88 MHz x 6). CPU master/3 or master/12; PSG
master/6 (pcetech says 3.58 MHz; Hudson's patent text says 7.16: the formulas
agree with 3.58); VCE dot clock master/4, /3, /2 (5.37, 7.16, 10.7 MHz). A line is **1365
master clocks**, a frame 263 lines = 358,995 clocks (59.826 Hz) or 262 = 357,630 [emu:
Mednafen `vce.cpp` l.621; Beetle PCE reports 59.8261 fps, measured here]. The PAL-form 313-line
machine does not exist; the PC Engine is NTSC-J, the TurboGrafx-16 NTSC-U, both 263/262
(region/system scope: open decision 2).

## Who owns what (the core / board split; recommendation)

The sibling core, `huc6280-python`, exposes one callback per CPU cycle with the 21-bit physical
address; **the board owns the clock, the VDC wait states and the IRQ lines** (the brief for
this phase). The question is what lives *inside the HuC6280 die* but outside the instruction
set. Aubrey's rule: CPUs always own a core; non-CPU chips used by one machine family stay in
the board and are broken out only when another emulator could use them.

| Piece | In the die? | Recommendation | Why |
| --- | --- | --- | --- |
| Instruction set, T flag, block moves, CSL/CSH state, flags, vectors | yes | **core** | it is the CPU |
| **MMU** (MPR0-7, TAM/TMA, 21-bit translate, ST0-2 bypass) | yes | **core** | TAM/TMA are instructions; the logical-to-physical step is part of every access; every user of the chip needs it |
| Interrupt **sampling** (3 lines + NMI, vector choice, `I`) | yes | **core** (levels in, taken between instructions) | instruction-boundary semantics |
| Timer (`$0C00`), interrupt mask/status (`$1400`), I/O port (`$1000`), I/O buffer | yes | **board**, as one `cpu_io` module behind a pin-shaped interface | memory-mapped, driven by the board's clock; the core has no use for them. MAME puts them inside `h6280`, so a later Data East arcade board (HuC6280 sound CPU, 1990 Dark Seal) is a plausible second consumer: **extract on the second consumer, never copy** |
| PSG (`$0800`) | yes | **board** (`psg` package, import-boundary test, like gameboy-python's APU) | no other machine uses the C6280 PSG (the arcade boards use it unused) |

If huc6280-python's Phase 0 decided otherwise, the board adapts: the bus decode is the same and
only the module that answers `$0C00-$17FF` changes.
