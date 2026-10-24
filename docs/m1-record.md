# Milestone 1 record: what is built, what judges it, what is provisional

Status (2026-10-24): **the board is built, pinned to the core and green; M1's two core-dependent
judges were run and the exit does NOT hold, so M1 stays open.** The core is huc6280-python
`143eb29` (rungs 0-5, pinned in `pyproject.toml` by git commit); 149 tests pass on CPython 3.14 and
PyPy 3.11 (`tests/test_core_wiring.py` uses the real core; `tests/test_covell.py` is `slow`).
Details: "The two judges" below.

## Layout as built

```
src/pcengine_python/
  machine.py       the machine table and the clock constants (each with its source tier)
  sockets.py       the Protocols: Card/CardSlot, PortDevice, PageHandler, BoardPins (hold, IRQ2),
                   Clocked, IrqLine, PixelPath/DirectPath, VideoTiming, AudioSource, ResetKind,
                   ControllerPort
  pagetable.py     8192 x 256-byte pages; base map + claim/release; Ram, Unmapped
  hardware_page.py bank $FF as 32 page handlers (VDC, VCE, cpu_io; $1800-$1FFF left to claims)
  cpu_io/          timer, $1400 interrupt controller, $1000 I/O port, I/O buffer (boundary-tested)
  pads.py          2-button, 6-button, 5-port multitap
  vce.py           colour table, control, dot clock; replaceable RGB table
  vdc/             regs, VRAM port + status/IRQ1 (chip.py), vertical state machine and line events
                   (sequencer.py) (boundary-tested)
  psg/             register file only (the voices are M4) (boundary-tested)
  video.py         Timeline (line/frame clock, 262/263) and Capture (rows of 9-bit values)
  cards.py         the standard ROM card with mirroring
  board.py         one master-clock timeline; the CPU callbacks; IRQ delivery
  system.py        board + CPU, run_frame
tests/             138+ tests, CPython 3.14 and PyPy 3.11 both green
```

## Judges and results

| Item | Judge (tier) | Result |
| --- | --- | --- |
| I/O buffer, the worked example of pcetech 3 note 1 | MacDonald, tested on a console (2) | exact, test `test_pcetech_io_buffer_worked_example` |
| timer: period `latch + 1` ticks of 3072 clocks, 0 counts as 1, $7F as 128, underflow rather than 1 -> 0, reload at the underflow, freeze on disable, reload from the latch on enable, latch write leaves the count alone | pcetech 2.2 (2); HuC6280 manual 2.7 (3) | exact |
| `$1402`/`$1403` layout, the line state visible while masked, any write acknowledges the timer | pcetech 2.1 (2); manual 2.4 (3) | exact |
| I/O port bits, country by machine row, CD sense follows the *port*, not the slot | pcetech 4 (2) | exact; C6 polarity unresolved (follows pcetech) |
| output port powers up high | HuC6280 manual 2.5 (3) | SEL and CLR power up set |
| pads: 2-button groups, CLR high zeros, Turbo Tap counter, reset sequence, `$0F` empty port, 6-button scans | pcetech 4 (2); pce-devel notes (4) | tested; mouse not modelled (U12) |
| VCE colour table, address advance after the MSB, `$0405` bits 7-1 set, unused registers `$FF`, 8-byte mirror, dot clock bits | pcetech 6 (2); VCE manual (3) | exact |
| VDC bus: select/status/data, MAWR/MARR/VWR/VRR with the CR increment, write latch, buffer, invalid registers, status clears except BSY, BSY raises no IRQ, mirrored half | pcetech 5 (2); VDC manual (3) | exact; the mirrored-half read (0) is U23 |
| frame layout: vsync is the last 3 lines; first display line = VDS + VSW; vblank flag on the first line after VDW; RCR counts from `$40` at the first active line; `$146` at the next frame's line 24; out-of-range values never match | pcetech 5, 5.1, 7 (2) | line-exact; the sub-line position is U19/U22 (tier 5) |
| pricing: 12/3 master clocks, VDC and VCE access one cycle longer, `hold` | pcetech 2.4, 3 (2) | exact; where in the cycle the device sees the access is U21 |
| a mid-line palette write changes the row from the dot it was made on | the mechanism of Covell's test | exact (dot = first dot at or after the write) |
| **Covell's CPU test photographs** (tier 1): vertical split for every 2-8 cycle group | the photographs | vertical: **yes**; at the photographed position: **no** (see below) |
| **MAME instruction-stream lockstep on the test ROM**, 0 unexplained | MAME 0.285 (tier 5) | **not met**: first difference at instruction 2 (see below) |

## The two judges

### Covell's CPU test (tier 1)

`tests/test_roms/CPU_Test/CPU_Test_10.pce` runs on the board and the real core and draws, without any
background layer, the stripes of the photographs: grey left, magenta right, alternate lines
swapped, one split per scanline (`scripts/frame_png.py`). Measured against the seven ROM-mode
hardware photographs (`images/8MROM_2..8.png`, measured by `scripts/covell_photo_splits.py`
into `tests/covell_hardware_splits.json`; the photograph is registered to Mednafen's screenshot on
the text, so the numbers carry about 1.2 dots of photographic error):

- **Verticality holds.** Over 115 scanlines the split's interquartile range is at most 2 dots in
  every group, as in the photographs (2-3 px). The core's instruction timing therefore does not
  walk the split down the screen in any 2-8 cycle group.
- **Absolute position does not.** With the Mednafen-derived VDC events (vblank test at the start of
  the display width) our splits sit **24-28 dots right** of the photographs in every group:
  the photographs agree with Covell's remark that Mednafen's VSync "triggers too late", and our
  VDC model is Mednafen's (it reproduces Mednafen's own screenshots to within 1-2 dots). Moving the
  vblank test to the start of the line (MAME's position; now the default, `vblank_dots=0`)
  recovers about 18 of the dots and **leaves 6.2-10.0 dots (8.3 on average) right of the photographs**.
  Earlier vblank times change nothing: the ROM's wait loop quantises the interrupt to about 6 dots, so
  the photographs cannot place the event more finely, nor decide a whole line either way.
- **"Within one cycle" is not shown.** Relative to the 2-cycle group the groups sit within 1.8
  dots of the hardware's (6-cycle group worst); one high-speed cycle is 0.75 dot and the photographs
  carry 1.2 dots of error, so the data neither prove nor refute one-cycle agreement.
- Block-transfer and VRAM X-cycle rows were not measured (provisional, U1/U20).

### MAME instruction-stream lockstep (tier 5), `scripts/mame_lockstep.py`

MAME's 2.1 M-instruction trace of the same ROM (`tests/mame_traces/`, not copied) against the board,
started as MAME starts (beam line 260, 263-line frames: `lines_follow_vce_bit2=False` for this
comparison only). Nothing is masked except the B bit (not a stored flag of the core; MAME shows it
clear inside an interrupt handler, pcetech says it reads set). Each experiment flag below makes the
core or the VDC behave as MAME does where they differ, **to look behind a difference, never as a
default**:

| Flags | First difference | Cause and tier |
| --- | --- | --- |
| none | instruction 2 (`CSH`), clock: 9 ticks, MAME 12 | C7: the core applies the new speed for the instruction's last cycle (Mesen, Mednafen), MAME after it. pcetech knows only the non-switching 3 cycles; Covell's photographs contain `CSH` rows but a real switch is not isolated: **undecidable here** |
| `--mame-csh` | instruction 11, registers: A, X after a block transfer | C14: the core pushes and pops Y, A, X (Hudson HB-6, Mesen, Mednafen), MAME keeps them in the CPU; the ROM's block fill overwrites the stack. Cycle counts agree (49,208 ticks). **Manual (tier 3) against MAME (5); the core follows the manual** |
| `--mame-csh --mame-blocks` | instruction 136,975, the first vblank interrupt: MAME enters after the instruction in progress, the board one instruction later | 136,975 instructions equal in every register and every clock first. U19: where the vblank flag rises, and C-level difference in when the vertical phase counters step (MAME at line start, Mednafen and this board at the end of the previous line, 0.8 line apart) |
| `+ --mame-vertical --mame-entry7` | instruction 216,735, the second interrupt: MAME enters one instruction later than the board | MAME's own IRQ visibility is not repeatable at sub-instruction level (the same assertion time is seen after one instruction in one frame and not in the next); with a 7-cycle entry (C3: MAME 7, the core 8) the first entry matches to the tick. **A MAME artefact or U19; undecidable here** |

So the criterion "0 unexplained" is **not** met: three named causes are overridden to get 216,735
instructions, and the fourth stop is not explained. The honest results are the 136,975
instructions that agree exactly once C7 and C14 are overridden, and the three disagreements above.

### The brief's handoff checks

- **Block-transfer reads of `$0800-$13FF`**: the core calls `idle(address)`, not `read_byte`, so the
  device is not asked and the I/O buffer is not loaded (test). **Finding for the core**: its range
  ends at `$13FF`, so a block read of the interrupt registers (`$1400-$1403`) reaches them although
  pcetech 2 lists them among the unreadable; tier 2 and the core's U7 disagree by that block.
- **`irq_disable`**: the core's property uses the `$1402` layout; the board forwards every `$1402`
  write and gives raw line levels; a masked IRQ2 is not taken and an unmasked one enters through
  `$FFF6` (test).
- **Interrupt entry 8 vs 7 cycles** (C3) and **CSL/CSH**: see the table; both are cases where a
  tier-5 source (MAME) alone differs, and are undecidable here.

## Provisional items, with their tier (the milestone's "undecidable" list)

U1, U19, U20 (VDC CPU slot schedule, vblank position now fitted loosely to tier 1, block-transfer rows): tier 1-5; U4: not
modelled yet (palette-access conflict is M2/M3); U21-U24 and C9-C10 below. No item here needed a
console and none was guessed silently: each has a named default in code with a `# U..` comment.

## What the data contradicted in the Phase 0 documents

- **The VDC does not step by 8-dot character cycle.** Mednafen's line counter steps 4 dots before
  the end of the display width and its display-start events sit at `(HDS + 1) * 8` dots plus 8 after
  the sync: not on the 8-dot grid. The sequencer is event-driven at dot granularity. (start-here.md,
  vdc.md and the brief's "decided" list said character cycle; corrected there.)
- **A 256-wide line's events run past the line.** With HDS 2 and HDW `$1F` the display width ends
  at 365 + 1024 = 1389 master clocks after the sync starts, 24 clocks into the next line; so the
  next sync must not discard the pending events, and a picture row is measured from the *end* of the
  sync (Mednafen's scanline), not from its start. A first version cut six dots off every 256-wide row.
- **The block-transfer zero-read rule is the core's, not the board's** (huc6280-python brief,
  "The core boundary"). The brief here said the board could not tell; whether the core still calls
  `read_byte` for those reads (and so would load the I/O buffer) is to be checked at the first pin.
- **RCR `$146` needs 263 line-counter steps per frame.** Mednafen drops the step pending at the
  vertical sync, which would make `$146` unreachable although pcetech 5.1 documents it; the board
  takes the step instead (C9).

## New unknowns and conflicts

| # | Entry | Default and tier |
| --- | --- | --- |
| U21 | Where inside a CPU cycle a device sees the access, and where the VDC/VCE stretch cycle goes | the base cycle elapses, then the access, then the stretch (tier 5 convention); Covell's photographs place it |
| U22 | The dot positions of the VDC's line events (display start, line-counter step; the vblank test is U19) | Mednafen's, restated in master clocks (tier 5) |
| U23 | Reads of the mirrored VRAM half | return 0 (Mednafen's zero-filled array; pcetech says "sometimes corrupted") |
| U24 | Delay from the timer's enabling write to its first tick | one full period, 3072 master clocks (MAME, Mednafen); the prescaler reset itself is tier 3 |
| C9 | Mednafen drops the line-counter step pending at the vertical sync; pcetech 5.1's RCR range needs it | take the step (tier 2 over tier 5) |
| C10 | Multitap read with CLR high right after the reset write: pcetech says pad 1's directions, the pce-devel port table implies 0 | pcetech's (`MultiTap(clr_high_reads_pad=True)`) |
