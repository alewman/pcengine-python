# Milestone 1 record: what is built, what judges it, what is provisional

Status (2026-10-24, updated after M2): **the board is built, pinned to the core and green; M1's
two core-dependent judges were run and the exit does NOT hold, so M1 stays open.** M2's first
background picture calibrated Covell's absolute positions ("Calibration with the background"
below): the offset did not close. The core is huc6280-python
`143eb29` (rungs 0-5, pinned in `pyproject.toml` by git commit); 149 tests pass on CPython 3.14 and
PyPy 3.11 (`tests/test_core_wiring.py` uses the real core; `tests/test_covell.py` is `slow`).
Details: "The two judges" below. Update 2026-10-24: the instruction-stream lockstep now closes
against Mednafen (not MAME); the photograph criterion does not ("The same lockstep against Mednafen").

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

### Calibration with the background (M2, 2026-10-24)

M1 could not place the photographs' columns on our raster (they were registered through Mednafen's
screenshot). With the background layer drawn, the heading's left edge and the HuCard icon's right
edge are the same two features in our picture and in each photograph, so a photograph column
converts to our dots with its own scale (1.252-1.254 photograph px per dot) and offset, no
emulator in between (`scripts/covell_calibrate.py`). Also corrected: the board starts in **RAM**
mode ("Running in RAM"), so M1's table paired our RAM-mode screens with the ROM-mode photographs;
the pairs below are like with like. Differences are ours minus the hardware, in dots (one
high-speed cycle is 0.75 dot, the photographs carry about 1.2 dots of error):

| Vblank test | RAM mode, groups 2-8 | ROM mode, groups 2-8 |
| --- | --- | --- |
| 0 dots after the sync (the accepted default) | +7.4, +7.0, +11.0, +11.4, +10.2, +8.0, +9.8 | +12.6, +11.0, +8.4, +12.2, +11.2, +11.6, +8.8 |
| -8 dots (before the sync ends) | +1.4, +1.0, +5.0, -0.6, +4.2, +2.0, +3.8 | +6.6, +5.0, +2.4, +6.2, +5.2, -0.4, +2.8 |

**Decision 2026-10-24 (Aubrey): the default is now -8 dots** (`vblank_dots=-8`, U19, provisional,
tier 1). Before (0): +7.0 to +11.4 dots in RAM mode, +8.4 to +12.6 in ROM mode. After (-8): -0.6 to
+5.0 and -0.4 to +6.6. The M2 pictures and the gate are unchanged by it (docs/m2-record.md).

So **the offset moves with the vblank position and does not close**: the test measures the
vblank flag's time to a few dots, and the photographs fit best with it about 8 dots *before* the
end of the horizontal sync (a negative `vblank_dots`, now supported); the default stays 0 (Aubrey's
acceptance) and **the -8 fit is an open decision**. Even at -8 the groups' positions differ from
the hardware's by -0.6 to +6.6 dots, and our groups spread over 4 dots where the photographs spread
over 2.4: that is not "within one cycle" (0.75 dot). Variants tried on the RAM screens (vblank -8): a
7-cycle interrupt entry (C3, MAME's) gives +0.4 to +4.8 (a smaller spread, a different mean); no
VCE access stretch gives -5.6 to -11.6. None isolates the cause: the groups differ by the length
of the ROM's wait loop, so the quantum of the interrupt's entry, and the entry's length (C3) and
poll point (U21) are the suspects. **M1's exit cannot close** on Covell's criterion; what holds
(vertical splits, instruction timing walking nowhere) is recorded above.

### The vblank fit, per photograph (2026-11-04)

`scripts/covell_calibrate.py` re-run per vblank position, both modes, against the photographs only
(ours minus hardware, dots, groups 2-8; the -8 rows reproduce the table above):

| `vblank_dots` | RAM mode | ROM mode |
| --- | --- | --- |
| -16 | -4.6 -5.0 -7.0 -6.6 -7.8 -4.0 -2.2 | -5.4 -7.0 -3.6 -5.8 -6.8 -6.4 -3.2 |
| -12 | -4.6 -5.0 -1.0 -0.6 -1.8 -4.0 -2.2 | +0.6 -1.0 -3.6 +0.2 -0.8 -0.4 -3.2 |
| -11 | +1.4 +1.0 -1.0 -0.6 -1.8 +2.0 -2.2 | +0.6 -1.0 -3.6 +0.2 -0.8 -0.4 -3.2 |
| -10, -9 | +1.4 +1.0 -1.0 -0.6 -1.8 +2.0 +3.8 | +0.6 -1.0 +2.4 +0.2 -0.8 -0.4 +2.8 |
| -8 (default) | +1.4 +1.0 +5.0 -0.6 +4.2 +2.0 +3.8 | +6.6 +5.0 +2.4 +6.2 +5.2 -0.4 +2.8 |
| -6 | +1.4 +1.0 +5.0 +5.4 +4.2 +2.0 +3.8 | +6.6 +5.0 +2.4 +6.2 +5.2 +5.6 +2.8 |
| -4 | +7.4 +7.0 +5.0 +5.4 +4.2 +8.0 +9.8 | +6.6 +5.0 +8.4 +6.2 +5.2 +5.6 +8.8 |

What the per-case pattern says. Each group's split sits on one of two levels about 4-6 dots apart and
**jumps a whole level (4-6 dots) at a threshold vblank position** (e.g. RAM group 4 between -10 and -8,
group 5 between -8 and -6; ROM group 4 and 8 between -11 and -10); between thresholds the vblank
position moves nothing. The 4 dots are the
quantum with which the ROM's wait loop takes the interrupt; the hardware's splits do not show it
(spread 2.4, no group on two levels). So the vblank position fixes the mean and cannot fix the
spread: the mean is best at -11 to -9 (mean -0.2 to +0.7 RAM, -1.2 to +0.5 ROM; largest single
residual 2.2-3.8 against 3.6 at -11 ROM), the spread stays 3.8-5.6 at every position that has a
good mean. No position puts both modes' seven groups within the photographs' 2.4-dot spread (the
best, -10 and -9 ROM, is 2.8 at worst; -10 RAM is 3.8). The earlier variants (C3's 7-cycle entry,
no VCE stretch) change the quantum's phase or shift the mean, as recorded above; none removes the
two-level jump. Line-start offset: the calibration anchors on the test's own text, which moves with
the line start, so it cancels; not a free parameter here.

**Decision (2026-11-04): the default stays -8.** No parameter closes the criterion, so no default
is changed, no 18-picture gate or lockstep re-run was needed (nothing moved). **-10 (or -9) is the
best fit** to the photographs (mean +0.6 against +3.2, worst +3.8 against +6.6) and is available as
`Board(vblank_dots=-10)` for a later decision; it is not adopted because it does not close the
criterion either, and a move that does not close it is a tuning, not a result. **M1 closes as a
documented provisional.** What remains: the two-level quantum of the interrupt's entry (the entry
length C3, the poll point U21; both in the core's interrupt sampling, a separate repository) and
Covell's own data cannot separate them; the hardware spread of 2.4 dots against the board's 4 stays.
A tier-1 observation that isolates the interrupt entry (a cycle-exact instruction at known
vblank phase) would close it; the photographs of the 2-8 cycle groups do not.

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

Re-run on 2026-10-24 with the core at a379416 and the vblank default at -8: the same two stops
(instruction 2, `CSH`; instruction 136,975 with C7 and C14 overridden); the default moved neither.

### The same lockstep against Mednafen 1.32.1 (tier 5), 2026-10-24

`scripts/lockstep.py mednafen` (the trace build of huc6280-python; method and the six-game runs in
[m5-lockstep-record.md](m5-lockstep-record.md)); 2,100,000 instructions of the same ROM, core a379416.
Mednafen takes the interrupt entry in 8 cycles (C3), applies `CSH` as the core does (C7) and pushes
Y, A, X for block transfers (C14): **the board agrees with it on all three with no override**, where
MAME needed three. What is left, in the order the run meets it:

| Flags | First difference | Cause and tier |
| --- | --- | --- |
| none | instruction 0, S (`$00` against `$FF`) | Mednafen powers up with S = 0; random on hardware (U2) |
| `--adopt-reset-s` | 136,994, the first vblank interrupt, 30 ticks (8 instructions) early | U19: the board's -8 dots (photograph fit, tier 1) against Mednafen's start of the display width, 24 dots later |
| + `--vblank-dots mednafen` | 201,927, clock +14 ticks on `ST2` to the VDC data port | VDC wait state (U18/U20): Mednafen 19 ticks, the board 5 |
| + `--adopt-io-waits` (36 waits, 14-32 ticks) | 290,925, the 7th interrupt, one instruction late | U21: the line rises exactly on an instruction boundary; Mednafen counts it visible |
| + `--raster-shift 1` (1, 2 or 3 clocks) | **none in 2,100,000 instructions**, 54 entries | the tie rule of U21, less than one high-speed cycle |

**Can M1's exit close?** The wording of the exit, "instruction-stream lockstep on the test ROM, 0
unexplained", **can now be met against Mednafen**: every difference above has a name and a tier, and
with the four overrides the 2.1 M-instruction stream, the 54 interrupt entries and every clock are
equal. Against MAME it still cannot (three overrides and an unrepeatable fourth, above). What this
does **not** show: that the board is right. A match to a tier-5 emulator is a detector result, and
the position at which the two streams agree (vblank at Mednafen's start of the display width) is the
one Covell's photographs say is too late, 24 dots from the -8 the board uses; the three overrides
that matter for timing (vblank position, VDC waits, the 1-3 clock tie) are exactly the places where
no tier 1-3 source speaks. **Covell's photographs remain the tier-1 criterion and that criterion
still cannot close**: the groups still sit -0.6 to +6.6 dots from the hardware's with a spread of 4
dots against the photographs' 2.4, and Mednafen, which has the vblank 24 dots later, cannot arbitrate.
So: the lockstep half of the exit closes against Mednafen; the photograph half is unchanged and M1
stays open on it.

### The brief's handoff checks

- **Block-transfer reads of `$0800-$13FF`**: the core calls `idle(address)`, not `read_byte`, so the
  device is not asked and the I/O buffer is not loaded (test). **Finding for the core, closed**: its
  range ended at `$13FF`, so a block read of the interrupt registers (`$1400-$1403`) reached them
  although pcetech 2 lists them among the unreadable. Raised as huc6280-python issue 0001 and fixed
  at `7f789e4` (range `$0800-$17FF`, the parenthesis reading; the end is still undecidable there);
  the board repinned to it on 2026-10-24 and its test now expects 0.
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
