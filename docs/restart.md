# The clean rewrite of 2026-11-19

Aubrey, 2026-11-19: "rewrite the modules that used GPL sources if we haven't already." The
licence audit of 2026-11-13 ([provenance.md](provenance.md), "Licence provenance") marked the
VDC's line machine and parts of the VDC chip **rewrite** (code that followed Mednafen's
`huc6270/vdc.cpp`, or took a formula from Mesen2) and a few constants **unclear** (their only
stated source was GPL code that had been read). This pass replaced them. It follows the family
charter (provenance rules 1-10) and the rules the sound cores' restart used
(`sn76489-python/docs/restart.md`, rules 1-11), adapted below.

## The rules this pass kept

1. **No GPL or LGPL source is read**: Mednafen, Beetle PCE, Mesen2, Geargrafx, the MiSTer core's
   `rtl/`, MAME's GPL files, the 240p Test Suite. Not to learn, not to check a constant, not when
   a comparison fails. Their trees under `reference/` were not opened, searched or grepped.
2. **The replaced code was not read.** Before writing, the tainted module and the tainted
   functions were moved, unread, into the git-ignored `scratch/withdrawn/` by a small Python
   helper (a whole-file move for `vdc/sequencer.py`; an `ast` cut by method name for
   `vdc/chip.py` and `vdc/dma.py`, which printed nothing of what it cut). They were not opened
   again. Untainted code in the same files, the call sites (`board.py`, `vdc/chip.py`,
   `vdc/dma.py`) and the tests defined the interface.
3. **Repository documents that quote GPL code or name GPL internals were not used as sources**;
   they were rewritten afterwards (wording only), after the code was written.
4. **Permitted sources** (licence checked in each file before reading):
   - Hudson's HuC6270 VDC, HuC6260 VCE and HuC6280 hardware manuals (the scans in the MiSTer
     repository's `docs/` folder: NEC/Hudson documents, not the GPL core);
   - Charles MacDonald's `pcetech.txt` (tested on hardware), the PCEdev wiki pages under
     `reference/docs/pcedev-wiki`;
   - MAME's `src/devices/video/huc6270.cpp` and `huc6260.cpp` (first line
     `license:BSD-3-Clause`, copyright Wilbert Pol) and `cpu/h6280/h6280.cpp` (BSD-3-Clause,
     Bryan McPhail): read as a permissive emulator's description; nothing transcribed; the
     notice is in [NOTICE.md](../NOTICE.md) and the headers of the files they informed;
   - Chris Covell's CPU-test photographs (tier 1).
5. **GPL emulators were run as closed boxes only**: Mesen2's library and Beetle PCE through the
   repository's harnesses (`scripts/mesen_run.py`, `scripts/libretro_run.py`), the patched
   Mednafen build through `scripts/lockstep.py`. A difference says where to look; a constant
   fitted to their output is marked "closed-box measurement" with the emulator named.
6. **Every rule in the new code names its source** with the family's tags ([mfr], [hw], [emu],
   FITTED, HYPOTHESIS) or says it is a choice.
7. **The gates are external**: the picture gate against Mesen2 and Beetle PCE, Covell's
   photographs, the library sweep, the lockstep. The withdrawn code's output was never a target;
   its recorded results are the "before" column.

## What was replaced

| Item | Before | Now | Source of the new behaviour |
| --- | --- | --- | --- |
| `vdc/sequencer.py` (whole module) | withdrawn: followed Mednafen's VDC line machine | new line machine: line step at the end of the horizontal sync, display start (HDS+1) characters later, vertical periods VSW+1 / VDS+2 / VDW+1 / VCR+3 lines from the line the vertical sync falls on | [mfr] HSR/HDR/VPR/VDW/VCR/RCR, Fig. 2-2-1; [hw] pcetech 5.1, 7; [emu] MAME huc6270.cpp (BSD-3) |
| `vdc/chip.py` scroll state, `_step_bg_y`, `latch_byr/bxr`, `line_counter_step` | withdrawn | `_bg_y_counter` loaded from BYR at the display period's start and on any BYR write, +1 per line step; both offsets taken at the display start | [mfr] BYR ("BYR+1"), BXR; [emu] MAME (BSD-3) |
| `vdc/chip.py` `commit_unless_dma` | withdrawn | not needed: nothing commits a pending access but its slot, a transfer's end, or a cancel | the slot model (chip.py) |
| `vdc/chip.py` `write` (BYR on both bytes) | withdrawn | rewritten from pcetech 5.1 and the manual; BYR's either byte reloads the counter | [hw] pcetech 5.1; [mfr]; [emu] MAME |
| `vdc/chip.py` `fetch_sprites` (sprite budget) | withdrawn: Mesen2's formula | the manual's table: entries searched by HDW, patterns fetched by HDE+HSW+HDS and SM | [mfr] 2.4.1 (6) and its note |
| `vdc/dma.py` `display_ended`, `force_complete` | withdrawn | `display_ended`: the SAT transfer at the vertical blanking; `finish_without_display` for a VDC with no board | [mfr] DVSSR note (b); a choice |
| `vdc/dma.py` 1024 dots, 2 dots a word | Mednafen's and Mesen2's constants | SAT busy three lines (pcetech's "four scanlines after the last line"); a word = a read and a write, one access per dot at VM 0 | [hw] pcetech 5.4; [mfr] MWR VM |
| `machine.py` `HSYNC_CLOCKS = 237` | quoted a Mednafen line | the same value from MAME huc6260.cpp's comment | [emu] MAME (BSD-3) |
| `cpu_io/timer.py` `underflow_window_mclk = 15` | read from Mesen2's code | see "The timer window" below | closed-box measurement |

## The judges, before and after

"Before" is the withdrawn code's recorded results (m1, m3, m5 records, 2026-11-04 to 2026-11-13);
"after" is this pass, run 2026-11-19 on the code at the commit that records it.

### The picture gate (18 titles) and the smoke sweep, against Mesen2 and Beetle PCE

`scripts/m5_sweep.py --names` over 30 cards (the 18 gate titles, the nine cards that were not
identical in the full sweep of 2026-11-12, Barbarian's other ports, R-Type I) at frames 300 and
600, closed-box referees over frames n-8..n+8: `tests/detectors/m5-sweep-smoke-clean-2026-11-19.txt`.

- **The 18 gate titles: every picture identical to both referees at 300 and 600**, as before
  (Air Zonk and Ballistix were gated at 450 before; here at 300 and 600, identical). After Burner
  II at 600 keeps its known Mesen2-only difference (rows 0.9587, Beetle identical): unchanged.
- The nine previously different cards: the same nine, same class. Unchanged numbers for
  Bomberman, Night Creatures, Santatlantean, Tiger Road; small moves within "different" for
  Battle Royale (600: rows 0.607 against 0.591 / 0.529 before), Davis Cup Tennis (600, Mesen2
  only: 0.369 against 0.349; Beetle identical as before), Galaga '90 (0.79-0.83 against
  0.77-0.81), Super Metal Crusher (300: 0.628 / 0.620 against 0.620 / 0.620).
- **One regression**: Barbarian (Atari ST), a 7 MHz card outside the gate, at 600: 10 pixels in
  four rows (152-179) differ from both referees (rows 0.9835 / 0.9876; before identical). The
  board's frame 595 is identical to both referees' 594-598; at 600 the referees show the next
  state of a small element and the board shows most of it. Insensitive to the vblank position
  (-8, -16, -18, display start), the timer window (3, 15), the SAT transfer's length (2 lines,
  3,072 clocks, 3 lines) and the sprite budget (off): so not those. The suspect is the CPU's
  phase against the beam (the raster compare and line step moved within the line), the same
  family as the lockstep's earlier stops. Open; what would settle it is the RCR placement below.

### The library sweep (179 HuCards), final code

`scripts/m5_sweep.py` over all 179 cards at 300 and 600 on the final code (5827480),
`tests/detectors/m5-sweep-full-clean-2026-11-19.txt`; class by the worse checkpoint against
Mesen2 (`scripts/m5_summary.py`'s rule).

| | IDENTICAL | NEAR | DIFFERENT | identical to Beetle at both frames |
| --- | --- | --- | --- | --- |
| before (2026-11-12, the withdrawn machine) | 170 | 0 | 9 | 171 |
| **after** | **168** | 0 | **11** | **169** |

The nine different before are the nine different now (After Burner II's Mesen2-only difference,
the three backup-memory cards, Davis Cup Tennis, Galaga '90, Battle Royale, Night Creatures,
Super Metal Crusher: the moves within "different" are listed under the smoke sweep). **Two
regressions**, both raster-timed pictures, both open:

- **Barbarian (Atari ST)** at 600: ten pixels (above).
- **Pac-Land (USA)** at 300 and 600: from row 40 down the picture is one line off against both
  referees (a mid-frame split; the comparator aligns it at dy = 1 with 16 rows left different).
  Not moved by the scroll latch (0, 8, 12, 24 dots) nor by reloading BYR one lower on a write.
  What would settle it: the same as Bomberman '94 (a hardware observation of a mid-frame
  scroll write, or a closed-box study of the game's writes against the referees).

### The raster compare's place and the scroll latch: two closed-box fits

The full sweep found Bomberman '94 (Japan), identical before, one line wrong at a split (row 51:
the board white, both referees black; at 600 four rows), from frame 300 on. Moving the compare
(`sequencer.RASTER_COMPARE_CLOCKS`, master clocks after the sync falls) and comparing at frame
300 against Mesen2 (frame 300; After Burner II's referee frame 302):

| Compare at | Bomberman '94 (pixels differing) | After Burner II |
| --- | --- | --- |
| 0 (MAME; kept) | 260 | 0 |
| the previous line's display end | 260 | 0 |
| 20 | 260 | 648 |
| 30 | 4 | 648 |
| 40, 50, 60, 120, 180, 237, 333 | 0 | 648 (60, 180), 648 (237: the gate run, rows 0.959 at 300) |
| 500 | 34,084 | not run |

No offset satisfies both: After Burner II, a gate title, wants the compare at the sync's fall;
Bomberman '94 wants it 40 clocks or more later. So the compare stays at MAME's place, and
Bomberman '94 was settled by the scroll latch instead (below). The two cards use the same display geometry
(HSR $0202, HDR $041F), so the place of the compare alone cannot be the whole story: the likely
missing piece is what a BYR (or BXR) write that lands between the sync's end and the display start
does to the line about to be drawn (the manual says only "the next scanning line (BYR+1)"). What
would settle it: a hardware observation of a mid-frame scroll write at a known time; failing that,
a closed-box study of both games' writes against the referees (which write, when, which line it
shows on), which this pass did not complete.

A lead, measured on the board (frame 299, the split's line 64, master clocks after the sync falls,
display start at 333): the RCR handler writes BYR's low byte at +315 and high byte at +348, BXR
at +396 and +429, CR at +546. So BYR's low byte lands 18 clocks before the display start and its
high byte 15 after: the line latches a half-written BYR, and how many clocks the handler needs
decides it. With the compare 40 clocks later both bytes land after the latch and the picture
equals the referees'. The rule the referees follow is therefore close to this boundary; a
latch a little earlier than the display start (the fetch of the first character must precede
its pixels) would also move it. Measured (compare at the sync's fall, frame 300):

| Scroll taken before the display start | Bomberman '94 | After Burner II |
| --- | --- | --- |
| 0 dots (MAME) | 260 | 0 |
| 8 | 4 (row 195) | 0 |
| **12, 16** | **0** | **0** |
| 24 (the line step itself), 40 | 260 | 0 |

**Adopted: 16 dots (two characters)**, `sequencer.SCROLL_LATCH_DOTS`: FITTED to the referees'
pictures, emulator tier, provisional; the stated reason (the first character's fetch precedes
its pixels) is a HYPOTHESIS. The raster compare stays at the sync's fall.

### Covell's CPU test (tier 1), `scripts/covell_calibrate.py` (anchored on the test's own text)

Ours minus the photographs, dots, groups 2-8 (one high-speed CPU cycle is 0.75 dot; the
photographs carry about 1.2 dots of error).

| Line machine, `vblank_dots` | RAM mode | ROM mode |
| --- | --- | --- |
| before, -8 (the old default) | +1.4 +1.0 +5.0 -0.6 +4.2 +2.0 +3.8 | +6.6 +5.0 +2.4 +6.2 +5.2 -0.4 +2.8 |
| before, -10 (the old best fit) | +1.4 +1.0 -1.0 -0.6 -1.8 +2.0 +3.8 | +0.6 -1.0 +2.4 +0.2 -0.8 -0.4 +2.8 |
| after, -8 | +9.4 +9.0 +13.0 +7.4 +12.2 +10.0 +11.8 | +14.6 +13.0 +10.4 +14.2 +13.2 +7.6 +10.8 |
| after, -12 | +3.4 +3.0 +7.0 +7.4 +6.2 +4.0 +5.8 | +8.6 +7.0 +4.4 +8.2 +7.2 +7.6 +4.8 |
| **after, -16 (the new default)** | +3.4 +3.0 +1.0 +1.4 +0.2 +4.0 +5.8 | +2.6 +1.0 +4.4 +2.2 +1.2 +1.6 +4.8 |
| after, -18 (the best fit) | -2.6 -3.0 +1.0 +1.4 +0.2 -2.0 +0.3 | +2.6 +1.0 -1.6 +2.2 +1.2 +1.6 -1.2 |
| after, -20 | -2.6 -3.0 +1.0 -4.6 +0.2 -2.0 +0.3 | +2.6 +1.0 -1.6 +2.2 +1.2 -4.4 -1.2 |

The new machine draws the display (HDS + 1) characters after the sync's end, 8 dots nearer the
sync than the withdrawn one did, so the photographs (which fix the vertical blanking's time
against the picture, not against the sync) move the fit by the same 8 dots: -16 holds the place
the old -8 held (mean +2.7 RAM, +2.5 ROM against +2.4 and +4.0), and the default moved there, by
the rule Aubrey set on 2026-11-04 (keep the default; a better fit that does not close the
criterion is a tuning). -18 is the best fit now (worst residual 3.0 RAM, 2.6 ROM; before, at -10:
3.8 and 2.8), available as `Board(vblank_dots=-18)`; Aubrey ruled on 2026-11-20 to keep -16 as the
default. Still not "within one cycle". The splits
are vertical in every group (`tests/test_covell.py`, which passes with its emulator-registered
band widened by the 8 dots).

### The timer window (C25), closed-box with Battle Royale

`underflow_window_mclk` in {0, 1, 3, 6, 9, 12, 15, 18, 24, 30, 45, 60}, the board at frames 300
and 600 against Mesen2 b9fa69d and Beetle PCE b96c11e: every window from 1 to 60 gives one and
the same picture (rows 0.9917 / 0.6074 against Mesen2, 0.9959 / 0.6074 against Beetle; before,
with 15 on the old line machine: 0.992 / 0.591), and 0 gives the stuck poll (0.27 / 0.17). The
referees therefore say "at least one master clock"; 3 (one PPS3 clock) is the manual-based
hypothesis inside that range.

### The Mednafen lockstep (tier 5, closed-box trace), "Full" flags, `--check-reads`

Fresh traces from the patched Mednafen 1.32.1 build, 2,000,000 instructions each (before: 20 M
for R-Type I, 5 M for the others), deleted after each run.

| Game | Before (2026-11-04) | After | First difference after |
| --- | --- | --- | --- |
| R-Type I | 20,000,000 (none) | **144,983** | registers: Mednafen enters an interrupt in the wait loop at E0F8 (tick 716,742) where the board does not yet |
| Gradius | 107,737 | **16,903** | registers: IRQ1 entry at E11C (tick 119,341), the board one entry late |
| Final Soldier | 630,583 | **17,352** | registers: an interrupt entry (tick 119,340), the board late |
| After Burner II | 187 | 187 | clock, the SAT-transfer hold (U32), unchanged |
| Bomberman '94 | 343,164 | **140,978** | registers: an interrupt entry (tick 716,741) |
| Bonk's Adventure | 235,057 | **58,063** | clock: the board enters an interrupt 4 ticks (12 master clocks) before Mednafen |

**Worse.** Every stop but After Burner II's comes earlier, at an interrupt entry a few ticks
apart. Sweeping the lockstep's `--vblank-dots` over {display start, -16, -8, 0, 8, 16, 32, 48}
moves none of Gradius's or Bonk's stops and R-Type I's by at most 13 instructions, so the
difference is not the vertical-blanking position: it is the raster interrupt's place in the line
(the new machine compares RCR as the sync falls, from MAME; the withdrawn one compared it near the
end of the display, Mednafen's place, which the "Full" flags were built around). Mednafen is a
tier-5 referee and no document places the raster compare inside the line; **what would settle it**
is a hardware observation of the RCR interrupt's time within its line (a Covell-style photograph
of a timed palette write after an RCR interrupt, or a logic-analyser capture). Moving the compare
to the line step and running the six again moved no stop either; the R-Type I stop, probed, is the
board entering the vertical-blanking interrupt (`--vblank-dots mednafen`, the display start of the
new geometry) a few ticks before Mednafen, whose display start is 8 dots later; the lockstep's
"Full" conventions were built for the withdrawn geometry and would need re-deriving. No VDC or
VCE read value differed before the stops.

## What the Rust transcription (pcengine-rust) must carry

Behaviour changes (every one changes the per-cycle trace):

1. The line machine of `vdc/sequencer.py`, wholesale: events "step" (sync end, `HSYNC_CLOCKS`
   after the line start), "display" ((HDS + 1) x 8 dots after the step, dropped if at or past the
   next step), "vblank", "collision"; the raster compare in `hsync` before the step is scheduled;
   the vertical periods VSW + 1, VDS + 2, VDW + 1, VCR + 3 counted at steps, with the vsync's line
   counted without a period change; the raster counter set to 0 on the last VDS line; burst mode
   taken at every VSW entry; a display cut by the vsync gets its vblank on the next line.
2. The picture's horizontal origin: the display starts 8 dots earlier in the row (256 wide: dot
   24).
3. `vblank_dots` default -16; `None` = the display start of that line.
4. The vertical scroll counter (`_bg_y_counter`): BYR at the display period's start, on either BYR
   byte, +1 (9 bits) at every step; `latch_scroll`, a "latch" event `SCROLL_LATCH_DOTS` = 16 dots
   before the display start (never before the step), takes BXR (10 bits) and the counter; the
   step drops a pending "latch" with the pending "display".
5. `_mwr_cache` = MWR bits 6-0 at each vblank; CM (bit 7) live; the background and the sprite scan
   use `_mwr_cache | (mwr & 0x80)`; the DMA's access width uses `_mwr_cache & 3`.
6. `fetch_sprites` at the step, on display lines only (not in burst mode), with the manual's
   searched/fetched budget; OR on a short budget.
7. The SAT transfer at the vblank event: copy 256 words (reads past VRAM give 0), busy for
   `SAT_CLOCKS` = 3 x 1365 master clocks; the done flag then. No `burst_mode = True` at its end.
8. VRAM -> VRAM: `ACCESS_DOTS[VM]` x divider clocks per access, two accesses a word.
9. `finish_without_display` for a VDC with no board (the standalone wait).
10. The timer's underflow window 3 master clocks.
11. `write`: VWR MSB waits (`_data_access`) then queues the word; MARR MSB waits then queues the
    read; LENR MSB starts the DMA; DVSSR MSB arms the SAT transfer (the LSB no longer arms it, if
    it ever did: the withdrawn code was not read, so say so in the Rust port's own check).

Interface changes: `Board(vertical_at_line_start=...)` and `Vdc(vertical_at_line_start=...)`
removed; `Sequencer(chip, vblank_dots)`; new `Vdc.line_begins`, `display_period_starts`,
`latch_scroll`, `vblank_begins`, `vsync`; removed `Vdc.latch_byr`, `latch_bxr`, `_step_bg_y`,
`line_counter_step`, `commit_unless_dma`, `DmaEngine.force_complete`; `sprites.scan(...,
searched=64)`; `sprites.CLOCKS_PER_SPRITE`, `dma.SAT_DOTS`, `dma.DMA_DOTS_PER_WORD` removed,
`dma.SAT_CLOCKS`, `dma.ACCESS_DOTS`, `sequencer.CHARACTER_DOTS`, `FRONT_PORCH_EXTRA_LINES` added;
the sequencer's state names (`lines_left`, `rcr_count`, `display_count`, `_events`, ...) are new,
so save states from 0.2.0 do not load into this code. The Rust port's own line machine (if it
transcribed the withdrawn one) is tainted the same way and must be rewritten from this one.

## What stays open, and what would settle it

- **The raster compare's place in the line, and mid-frame scroll writes** (the lockstep's earlier
  stops; Barbarian ST's ten pixels and Pac-Land's one-line split, the sweep's two regressions):
  MAME's "as the sync falls" is the only readable source. A hardware
  observation (a timed palette write after an RCR interrupt, photographed) would settle it; a
  closed-box fit to the Mednafen traces would give a provisional, emulator-tier default.
- **The scroll latch, 16 dots before the display start**: a closed-box fit on two games (12 and
  16 work, 8 and 24 do not); no document says it. A hardware capture of a mid-line scroll write
  would settle it.
- **The display start, (HDS + 1) characters after the sync's end** (manual, MAME): the 8 dots the
  withdrawn machine added are not in any readable source; Covell's photographs fix only the
  vblank against the picture, not the picture against the sync.
- **The front porch VCR + 3** (pcetech) against the manual's VCR: C-entry, untested by the
  library (every card here ends its frame on the VCE's sync).
- **The SAT transfer's length at 7 and 10 MHz**: pcetech's three lines measured (by his account)
  at 5 MHz; the 7 MHz cards of the gate are identical with it.
- **The timer window**: bounded below only; 3 is a hypothesis.
- The vblank fit: -18 fits the photographs better than the default -16. **Decided 2026-11-20
  (owner's ruling, Aubrey): -16 is kept as the default**; -18 stays available as
  `Board(vblank_dots=-18)`. No behaviour change.

## Progress (kept current for a later session)

- Steps 1-3 (code, documents, timer) committed; the raster compare tried at the line step and
  reverted; the scroll latch moved 16 dots early (5827480). Unit tests pass on CPython and PyPy;
  Covell's slow test passes.
- Judges recorded above: Covell, the timer window, the lockstep, the smoke sweep (on the code
  before the latch change; the latch change was checked on After Burner II and Bomberman '94).
- The full 179-card sweep on the final code is recorded above (168 identical, two regressions
  open: Barbarian (Atari ST), Pac-Land). Next steps if this is resumed: a closed-box study of
  Pac-Land's and Barbarian ST's mid-frame writes (scripts in the style of the Bomberman '94 lead),
  then rerun the sweep (`scripts/m5_sweep.py LIB SCRATCH OUT.jsonl --cards 6 --jobs 1
  --refs-cache DIR`).

## After the sweep: a display that starts before the row (03ac699, 2026-11-19)

supergrafx-rust found a line whose display starts before the row's first dot (a small HDS puts
the start inside the sync: `first` = -14 at divider 4 on its probe card in PC Engine position and
on the fallback). `render_line`'s slice then inserted the pixels and the row grew from 341 to 682
dots; pcengine-rust, transcribing it, panicked. `03ac699` draws such a line into a left-padded
work row (the sprites see every display column) and drops the pad, so the row keeps
1365 // divider dots (a choice; HYPOTHESIS that the early columns are fetched and lost, not
delayed). Test: `test_a_display_that_starts_before_the_row_is_cropped_and_the_row_keeps_its_length`.

**Does the library reach it?** All 179 cards were run as the sweep runs this board (600 frames
from power-on, no input, the TurboGrafx-16 row for "(USA)"), 6 niced PyPy processes, about half an
hour, with `Vdc.render_line` wrapped to count the lines whose display starts before the row and to
check every row's length (a throwaway wrapper, not kept: it monkeypatches `render_line`). **No card
reaches it**: no line with `first < 0` and no row of the wrong length on any card, including the 12
not identical to both referees in `tests/detectors/m5-sweep-full-clean-2026-11-19.txt`. The same
wrapper on supergrafx-rust's probe card (120 frames) counts 4 such lines in compat and base mode,
so it does see the case. On the 179 cards the fix changes no line, so the sweep's verdicts stand
as recorded above; the sweep was not rerun.
