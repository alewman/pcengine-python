# Milestone 3 record: sprites

Status (2026-10-24): **the exit holds.** With sprites on, the board's picture is pixel- and
row-identical (9-bit palette value, whole frame) to Mesen2 as shipped and to Beetle PCE for the first ten
library titles, for the four sprite-heavy games (Blazing Lazers, R-Type, Bonk's Adventure,
Samurai-Ghost) at 300 and 600 frames, and for the U15 outliers that are plain PC Engine cards
(Barbarian ZX, Death Sword PC, Mai Nurse, Gunboat). No difference needed a name: there is none to
name at those frames. Results: `tests/detectors/m3-sprites-2026-10-24.txt`.

After the core's fix for issue 0002 (a379416, pinned the same day) the full gate is green on CPython
and PyPy (183 tests; Covell's slow test too), After Burner II is identical to both detectors with no
experiment flag, and the MAME lockstep is unchanged (first difference at instruction 2, `CSH`; with
C7 and C14 overridden, 136,975 instructions, then the first vblank interrupt: m1-record.md).

## Built

`vdc/sprites.py` (scan and draw), hooks in `vdc/chip.py` and `vdc/sequencer.py`; 15 tests
(`tests/test_vdc_sprites.py`) against pcetech 5.3 (tier 2) and Hudson's VDC manual (tier 3):
placement, X/Y flips, 32-wide as two patterns with the halves swapped by flip X, 32/64-tall
pattern masking and row selection, priority against the background, first-in-table wins,
clipping, the 16-entry limit (a 32-wide sprite counts twice and keeps only its left half when one
place is left), the overflow flag and its enable bit, sprite 0's collision flag, raised when the
beam reaches the pixel, and the two-plane mode (manual: SM = 1, the pattern's low bit picks planes
0/1 or 2/3; pcetech says "2 or 3": the manual and both emulators agree on 1, used here, C12).

Per-line behaviour is Mednafen's (tier 5, U3): the scan for the next line runs as the
line counter steps, reading the pattern words then; the line is drawn when its display width
begins. A narrow-display budget (4, 4, 8 or 16 dots of fetch per entry between one line's display
end and 16 dots before the next line's display start) is Mesen2's; it never bound at any title here.

## Judges

| Group | Frames | ours = Mesen2 (sprites on) | ours = Beetle |
| --- | --- | --- | --- |
| first ten | 300 / 450 | 1.0000 px, 1.0000 rows, 10 of 10 | 1.0000, 10 of 10 |
| Blazing Lazers, R-Type, Bonk's Adventure, Samurai-Ghost | 300, 600 | 1.0000 / 1.0000, 8 of 8 | 1.0000, 8 of 8 |
| Barbarian ZX, Death Sword PC, Mai Nurse, Gunboat | 300, 600 | 1.0000 / 1.0000, 8 of 8 | 1.0000, 8 of 8 |

Mesen2 and Beetle agree with each other on every one of those pictures (E = 1.0000). Without
sprites ours is below 1.0 on the sprite-bearing titles (Samurai-Ghost 0.844, R-Type 0.944), as it
must be. The outliers' disagreement in M0's crude statistic (docs/validation.md) was the emulators
being at different frames after power-on, not a difference in drawing: with a window of frames each
detector has a frame that is identical to ours (the offsets are 0 to 19 frames, e.g. Mai Nurse's
Mesen2 frame is 299 against ours 300, Barbarian CPC's 300).

**Not run: Battle Ace and Madou King Granzort** (the other two U15 outliers). They are SuperGrafx cards
(second VDC, VPC, 32 KiB RAM): M6, not this board. **Frames 300 and 600 are title and attract
screens**: sprites in motion in game play, the 16-entry limit and the overflow flag under load,
and sprite 0 collision timing are exercised only as far as those screens go (the unit tests cover them
against the manuals; the narrow-display budget and the collision flag's position inside a line are
provisional, U3, tier 5).

## PixelPath on the per-line path (measured)

`scripts/pixelpath_bench.py`: one `mix` call a line (262 or 263 a frame), `DirectPath`. The call
costs **2 ns a line, 0.5 us a frame, 9e-7 of a frame** (a frame is about 0.5 s on PyPy). Whole runs
(Armed F, 12 frames, 10 repeats, socket against no socket) read 10.0 s against 7.9 s on average
(sd 3.9 s and 1.4 s: the box ran at load 80) and 6.41 s against 6.15 s at the minimum, +4 %,
inside the noise: the socket is **within noise**; the decision to fold the SuperGrafx into the
base as a mode (docs/sockets.md) is not forced.

## New entries

| # | Entry | Default and tier |
| --- | --- | --- |
| C12 | sprite CG bit: pcetech says it matters for MWR sprite width 2 or 3, the manual and both emulators for SM = 1 | SM = 1 (manual, tier 3) |
| U26 | the sprite collision flag's time inside a line | at the pixel's dot (Mesen2's idea; Mednafen raises it as the line is drawn), tier 5 |
| U27 | pattern reads past VRAM (pattern >= 512) | an empty sprite (Mesen2; the hardware reads garbage, pcetech) |

Note (2026-10-29): this record's **U26** (the collision flag's time) shares its number with m2-record's
U26 (when a DMA may run); the flag-time comparison across the four emulators is U35 and C29 in the
[brief](handoff-brief.md), the sources in [vdc.md](vdc.md).
