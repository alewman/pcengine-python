# Milestone 5 as built: the library sweep, and where the lockstep stands

Run 2026-10-30 on the code after the DMA and status-flag work (commits f6fb910..5826715), then
again after two small board fixes this sweep found (below). Judges: **Mesen2 (sprites on) and
Beetle PCE, both emulators, tier 5**: neither is a judge, they are two votes ([validation.md](validation.md)).
The lockstep half is in [m5-lockstep-record.md](m5-lockstep-record.md).

**Correction, 2026-11-04.** The sweep's frame choice had a flaw, found by running Formation Soccer
down: `best_alignment` scores every third pixel, so on a mostly flat picture several (frame, dx)
pairs score a full 1.0 and the first in window order won, even when another frame was exactly equal.
Formation Soccer's "regression" (frame 297 at dx 197 picked over frame 300 at dx 14, which is
identical to both referees), HuZERO's and the five "phase" NEARs below were this, not the board.
`scripts/m5_sweep.py` now scores every candidate within 0.5 % of the best on all pixels
(`best_frame_exact`, test `tests/test_m5_sweep_compare.py`). The 14 cards that were not identical (the three U36 cards, Binary Star and the two fixed cards, Rastan Saga II and Space
Harrier, were not), at 300 and 600 (HuZERO and Heavy Unit at 1500), were re-run with it
(`tests/detectors/m5-sweep-exact-2026-11-04.txt`, 26 lines); the earlier files keep the old,
flawed numbers and are not edited. Everything below that says "NEAR", "phase" or "Formation Soccer
regression" is superseded by the section "Corrections after the exact comparison".

## What ran

`scripts/m5_sweep.py` over `/data/emu/roms-retrobat/pcengine` (179 HuCards, read in place, extracted
per card into the scratchpad and deleted by a Python helper after each): the board under PyPy 3.11
to frame 300 and 600, Mesen2 and Beetle over frames n-8..n+8 around each, the 9-bit palette value
compared at the best alignment (Mesen2 dx 14/24, Beetle dx 32/46, dy -2..2). Per card: the share of
equal pixels and of **equal rows**, and the first differing pixel. Class by the worse of the two
checkpoints against Mesen2: IDENTICAL (every row equal), NEAR (>= 0.99 of rows), DIFFERENT
(`scripts/m5_summary.py`). The census says 153 listed and 26 unlisted images; the sweep covers all 179.
US cards ran as TurboGrafx-16.

Result files (JSON lines, one per card and checkpoint, `tests/detectors/`):

| File | What | Cards | Frames |
| --- | --- | --- | --- |
| `m5-sweep-pass1-2026-10-30.txt` | pass 1, code at 5826715 | 179 | 300, 600 |
| `m5-sweep-pass2-2026-10-30.txt` | pass 2, same code: every card not identical in pass 1 (17, plus Binary Star: Beetle only), the 6 whose verdict moved to identical, and 6 identical ones drawn with seed 5 | 30 | 900, 1500 |
| `m5-sweep-postfix-2026-10-30.txt` | pass-2 card list again after the two fixes below | 30 | 300, 600 |
| `m5-sweep-postfix2-2026-10-30.txt` | 46 more cards after the fixes (40 drawn with seed 11 from the 149 not in the file above, plus 6 unlisted images) | 46 | 300, 600 |
| `m5-sweep-full-2026-11-12.txt` | all 179 again in one run, code at fe1bb57 (core 9c47c98), the exact comparison | 179 | 300, 600 |

## Counts

| | IDENTICAL | NEAR | DIFFERENT |
| --- | --- | --- | --- |
| Pass 1 before the DMA work (2026-10-25) | 156 | 7 | 16 |
| **Pass 1 now** (code 5826715) | **162** | **6** | **11** |
| After the two fixes (76 of the 179 re-run, see below; the rest assumed unchanged) | 164 | 6 | 9 |
| **After the exact comparison (2026-11-04, 14 cards re-run; the rest unchanged)** | **170** | **0** | **9** |
| **Full re-run (2026-11-12, all 179, code fe1bb57, core 9c47c98)** | **170** | **0** | **9** |

The full re-run of 2026-11-12 removes the assumption below: every card and checkpoint has the same share of equal rows and pixels against both referees as its latest earlier result (358 lines; only Santatlantean's pixel share moved, 0.0004 to 0.0007-0.0012, rows 0.000 as before, U36). The nine different cards are the same nine. 171 cards are identical to Beetle PCE at both frames.

The 179 were not all re-run after the fixes: 30 + 46 = 76 were (all 17 non-identical cards included).
Of the 76, 2 moved (Rastan Saga II and Space Harrier, to identical); none of the 59 other cards
that were identical before moved (Davis Cup Tennis, Galaga '90 and Super Metal Crusher changed in their numbers, not in class). 103 identical cards were not re-run; "164 identical" assumes they
did not move, which 46 random ones out of 149 support (46 of 46 unchanged) but do not prove.

### Verdicts that moved between the two pass-1 runs

| Card | Before | Now | Why |
| --- | --- | --- | --- |
| Binary Star (Audio) | DIFFERENT 1.000/0.872 | IDENTICAL (Beetle 0.926, see C31) | the DMA/status work |
| Double Dungeons | DIFFERENT 0.880/0.868 | IDENTICAL | the same |
| Great Fumo Binning | DIFFERENT 0.091 | IDENTICAL | the same |
| Override | DIFFERENT 0.967 | IDENTICAL | the same |
| Parasol Stars | DIFFERENT 0.979 | IDENTICAL | the same |
| Legendary Axe | NEAR 0.992 | IDENTICAL | the same |
| Takin' It to the Hoop | NEAR 1.000/0.996 | IDENTICAL | the same |
| Battle Royale | DIFFERENT 0.270/0.167 | DIFFERENT 0.992/0.591 | C25 and the DMA work: the first frame is 23 pixels now |
| **Formation Soccer** | IDENTICAL | **NEAR** 0.992/1.000 | **a regression**: a loading bar's red line (36 px, rows 115-116) is missing at frame 300 and present at 600; the picture is one frame out of step with the referees now (pass 2: identical at 900 and 1500). Not run down. **Superseded 2026-11-04: a comparator artifact, identical (see "Corrections")** |

Everything else is the same class. The DMA and status work therefore moved 7 cards the right way
and one the wrong way, in the picture only.

## The causes, card by card

First differing row and cause for each of the 17 cards that were not identical, then the two
fixes. "Phase" means an animated element that is in a different state in the board's frame 300
or 600 than in any of the 17 referee frames compared; the cards' frame counts are not aligned to
the referees' (the best match is anywhere in 292-308), so a changing picture cannot be made equal
by the window alone. Where the referee's frame can be a few frames off, the other referee or a
later checkpoint agreeing is the evidence.

| Card | Class | First difference | Cause |
| --- | --- | --- | --- |
| Rastan Saga II | **fixed** | rows 64-111, the title's sword, at every checkpoint (300, 600, 900, 1500) | **C27**: VDS $18 + VDW $FF is 281 lines, the frame's sync cuts the display period short and the board never ran the SAT transfer (sprite table empty). Fixed: identical after |
| Space Harrier | **fixed** | rows 231-241 at every checkpoint | **C30**: the game writes CR $0C at line 245 (both layers off); the board drew overscan `$100` (black), all three emulators draw the backdrop `$000` (blue). Fixed: identical after |
| Santatlantean | U36 | row 0 at every checkpoint, 0.000 | no backup memory: the board shows the game's warning text, the referees the title. Not a defect |
| Tiger Road | U36 | rows 171-177 at every checkpoint | the "BACK UP" menu line is absent (no backup memory). Not a defect |
| Bomberman | U36 | rows 199-206 at 600, 900, 1500 (identical at 300) | the "LOAD" menu item is absent. Not a defect |
| Binary Star (Audio) | C31 | **Beetle only**: rows 0-10 and 235-241 | Beetle draws `$1FF` outside the display period; Mesen2 and the board agree (identical to Mesen2) |
| After Burner II | Mesen2 only | 600: 42 px in rows 103-119 (0x1b0 against 0x178), Beetle identical; 900: one element at row 223 against both | known from the lockstep record's picture gate; the board agrees with Beetle at 600. Not explained |
| Davis Cup Tennis | Mesen2 phase, then a sprite part | 300: Mesen2 4,035 px (the Loriciel logo's fade, Beetle identical at 296); 600: rows 129-175 against Beetle; 900/1500 0.806 against both | after the C27 fix Beetle is 1.000/1.000 at 300/600: part of it was the same missing-SAT-transfer cause. Mesen2 is still a phase apart; 900/1500 were measured before the fix |
| Galaga '90 | not run down | about 60 isolated pixels in 52-57 rows at every checkpoint, both referees | the starfield. Suspect: a random-number seed read from RAM that powers up as zeros here (U2) and as a pattern in the referees. Not checked |
| Battle Royale | phase | 300: 23 px in two text rows; 600: the fighters are elsewhere (5.9 k px); 900/1500 0.69/0.54 | the attract demo's moves depend on timing; no frame aligns. Not run down |
| Aero Blasters | phase | 600: one row (122), 19 px, both referees; 900/1500 identical | an element in flight |
| Final Soldier | phase | 300: rows 3-4 (the top two lines), both referees; 600, 900, 1500 identical | boot-time |
| Keith Courage | phase | 300: rows 1-2, both referees; later identical | boot-time |
| ImageFight | phase | 300: row 241, 73 px; 600 identical; 1500: row 3, 65 px (NEAR) | an element on the edge row |
| Ghost Manor | Mesen2 phase | 600: 12 px in rows 10-11, Beetle identical; 900/1500 identical | Mesen2 |
| Night Creatures | phase | 600: a bat sprite, 385 px; 900/1500 identical | animation |
| Super Metal Crusher | phase | 300: rows 109-198, Mesen2 4,316 px, Beetle 3,041; 600, 900, 1500 identical | a transition |
| Formation Soccer | regression | 300: rows 115-116, 36 px | see the table of moves |

Pass 2's extra sample (6 identical cards at 900/1500): 4 stayed identical (Neutopia II, Thunder
Blade, Skweek, Barbarian (Amstrad CPC)), **2 differ at 1500 only**: Heavy Unit (Mesen2 only, 3 % of rows,
Beetle identical) and HuZERO (both referees, 2.5 % of rows, row 79). Not run down; animated frames. **Run down 2026-11-04: HuZERO identical (comparator artifact), Heavy Unit a Mesen2-only fade-band phase (C32); see "Corrections".**
Of the 6 cards that had moved to identical, all 6 stayed identical at 900 and 1500.

## Corrections after the exact comparison (2026-11-04)

**Formation Soccer** (task: run the identical -> near move down). The board is deterministic (two runs
of the current code give the same frame 300). Dumping the
board's frames 290-306 and comparing each with Mesen2's and Beetle's 290-306: the game updates its
loading bar every third frame, and the board's frame 300 is **identical (rows 1.0000, pixels 1.0000)
to both referees' frame 300** at the usual dx 14 and 32, as are all 17 board frames to some referee
frame. The sweep had picked referee frame 297 at dx 197 (a 34,848 pixel overlap): on this flat
picture the 1-in-3 sample scores 1.0 for that pairing too, and it came first. With the exact
comparison the card is identical at 300 and 600 (rerun through the sweep script). No bisect over
2bd6665..f1a2f5a was run: the current board is identical to both referees here, so there is no board difference to
bisect (the older "identical" verdict came from a comparator without the wide dx search that
`d2a9b04` added; not re-run at the old commits). **Cause: harness (tie-break on a sampled score), not the board.**

**HuZERO at 1500.** The same flaw (frame 1492 chosen, 2.5 % of rows): all 17 board frames
1492-1508 are identical to both referees at the same frame number, on the pass-2 code
(5826715, checked) and on the current code. Identical.

**Heavy Unit at 1500.** Beetle PCE: identical at every one of the 17 frames (referee frame =
board frame + 1). Mesen2: the picture matches at some frames (board 1493, 1497, 1501) and at
others differs in exactly one 8-row band, rows 129-136, columns 86-205, 573 pixels, in two
colours: a text fade that steps every four frames through `$1FF, $1B6, $16D, $124` (the band's
palette value in the board's frames: 511, 438, 365, 292 for 1493-1496, 1497-1500, 1501-1504,
1505-1508), where Mesen2's band is one step ahead of its own scene (365 against the board's 438 at
the frame where the scene is equal). That is the phase of one fade counter against the scene in
Mesen2 only; the board agrees with Beetle on all 17 frames. Entered as **C32**; not shown to be
a board defect (two of three emulators, tier 5). The class stays NEAR for this checkpoint
(Mesen2 0.9669 of the rows), in the pass-2 sample only.

**The five "phase" NEARs.** Aero Blasters, Final Soldier, Keith Courage, ImageFight and Ghost
Manor are **identical to both referees at 300 and 600** under the exact comparison: the same flaw
(each had a frame chosen below the target, 292-299, at rows 0.9917-0.9959). Their old causes
("an element in flight", "boot-time", "Mesen2") were readings of an artifact and are withdrawn.
ImageFight's pass-2 NEAR at 1500 was not re-run.

**Not changed by it**: Night Creatures (600: a bat sprite, 0.9091 of the rows, both referees, the
same numbers as before), Super Metal Crusher (300: rows 109-198, 0.6198, both referees, no frame
in 292-308 equal), After Burner II (600: 42 pixels, rows 103-119, Mesen2 only, Beetle identical),
Davis Cup Tennis, Galaga '90 and Battle Royale (0.9917 at 300, 0.5909 at 600):
genuine differences with the old causes (phase, starfield, demo timing), all still "not run down".

Counts afterwards: **170 identical, 0 near, 9 different** (the three U36 cards; After Burner II,
Davis Cup Tennis, Galaga '90, Battle Royale, Super Metal Crusher, Night Creatures), assuming the
103 cards not re-run in the earlier pass did not move. The 6 non-U36 cards have named causes but
three are only suspicions (Galaga '90's seed U2, Battle Royale's demo timing, After Burner II's
Mesen2-only 42 pixels): they are triaged, not decided.

Findings the sweep made (new, in [handoff-brief.md](handoff-brief.md)):

- **C27 board fix** (`vdc/sequencer.py`): the vertical sync ends a VDW the sync cuts short and so
  runs the SAT transfer test, as Mednafen's "phase is not VDW" test does. The brief already said
  "Mednafen's (U31)"; the code only tested at the VDW to VCR step. Test
  `test_satb_dma_still_runs_when_the_sync_cuts_the_display_period_short`.
- **C30 board fix** (`vdc/chip.py`): a display line with both layers off draws `$000`, not
  `$100`. Tier 5 (three emulators agree) over tier 2 (pcetech 5.2 says overscan). Mednafen draws
  `$100` for "sprites on, background off", the board `$000`; no card in the library shows it, so
  it is left. Test `test_both_layers_off_inside_the_display_period_show_the_backdrop_not_the_overscan`.
- **U36**: no backup memory on a bare console; three cards differ only for that reason.
- **C31**: Beetle's `$1FF` outside a short display period.

Checks of these fixes: pytest 228 passed on CPython 3.14 and on PyPy 3.11 (the PSG referee test is
skipped on PyPy, no numpy); the 18-title picture gate was not repeated, but 76 cards were (above).
The lockstep traces are not stored, so R-Type's 20 M instructions were not replayed after the
fixes; the fixes act only where the display period is cut by the sync or a game turns both layers
off, which R-Type does not do (not checked beyond that reasoning).

## The 26 unlisted images

All 26 are in the 179 and were swept (the census calls "unlisted" the images the MAME software
lists do not know: 25 aftermarket or homebrew, 1 US dump of Bonk's Revenge). Result at 300 and 600:
**24 identical to both referees, Binary Star identical to Mesen2 and 0.926 against Beetle (C31),
Santatlantean different (U36, the backup-memory warning)**. Great Fumo Binning, different in the earlier pass (0.091), is identical since the DMA work. At 900
and 1500 five of them were run: Great Fumo and Barbarian (Amstrad CPC) identical, Binary Star
identical to Mesen2 (C31), Santatlantean different (U36), HuZERO identical at 1500 (it read as different in pass 2, a comparator artifact, see "Corrections").

## The lockstep exit, honestly

Replayed 2026-11-04 on the current code (f1a2f5a plus the sweep script fix, which does not touch
the board): Mednafen 1.32.1 traces recorded afresh (20 M instructions for R-Type I, 5 M for the
others), `scripts/lockstep.py mednafen` with the "Full" flags of
[m5-lockstep-record.md](m5-lockstep-record.md) plus `--check-reads`, CPython 3.14; traces deleted
after each run. f1a2f5a changed VDC behaviour; **no stop moved** against the 2026-10-29 table:

| Game | Mednafen, instructions equal | Where it stops | Named cause | Reads (`--check-reads`) |
| --- | --- | --- | --- | --- |
| R-Type I | **20,000,000** (668 entries, 1,390 waits adopted) | nowhere | none | 0 differences |
| Gradius | 107,737 | IRQ1 one instruction apart (Mednafen enters at the boundary) | U21 (the tie rule) | 0 |
| Final Soldier | 630,583 | an entry one instruction apart after 2,607 entries | U21; its long waits are U33 | 0 |
| After Burner II | 187 | a SAT transfer Mednafen does not start | U32 (the power-up display phase) | 0 |
| Bomberman '94 | 343,164 | `LDA $25` differs after a late-visibility resync | U21 | 0 |
| Bonk's Adventure | 235,057 | `RTI` returns to `C8D1`, Mednafen to `C8CE` | U21 (resync with another pushed address) | 0 |

Against MAME none reaches 20 M (172,272 at best, R-Type); not replayed (no MAME trace stored, 17
minutes of wall time each on a loaded machine).

### How the lockstep exit closes (proposal; the milestone was closed on this reading on 2026-11-04, see the M5 row of handoff-brief.md)

The exit as written asks for "6 games lockstep >= N M instructions with 0 unexplained". Proposed
reading, which the data supports and which Aubrey is asked to accept or refuse:

1. **R-Type I is exact at 20 M against Mednafen** (668 interrupt entries, every register, MPR,
   clock and VDC/VCE read value). This is the lockstep result; it uses five harness conventions
   (reset S, Mednafen's vblank position, VDC wait states, a 1-clock raster tie rule, the power-on
   colour table), all emulator-tier and off by default.
2. **The other five stops are named and measured, and left as U-entries**: four are U21 (Gradius,
   Final Soldier, Bomberman '94, Bonk's Adventure: Mednafen enters an interrupt at a boundary the
   board's sample reaches one instruction later, tier 5 against tier 5, the Covell photographs
   unable to place it), one is U32 (After Burner II: Mednafen's VDC counters cycle before the
   registers are programmed; the board's do not). Each stop is a point at which the board follows
   the tier-2/3 source and Mednafen a different convention; no tier-1 judge exists for either.
3. **No new referee switch is added.** The cheap ones already exist as `Board` options and
   `lockstep.py` flags and are in the "Full" set: `vblank_dots=None` (Mednafen's vblank position;
   default -8, the photograph fit), `start_offset` (the raster tie shift), `vertical_at_line_start`
   and `dma_resumes` (MAME's and the manual's readings). A switch for U21 would be a change in the
   core's interrupt sampling (not cheap, and the core is a separate repository); for U32 a second
   VDC line machine (tried 2026-10-29: After Burner II then stops at 2,389 for another phase
   reason, not kept); for U33 Mednafen's 48+16 dot window (tried: the stop moved from 630,583 to
   23,943, not kept). None of these was measured against the 18 pictures because none moves a stop
   the right way, which was the condition for adding one. Default stays tier 2/3; Mednafen's
   rule stays a lockstep flag. Low-tier referees are detectors here, not judges.
4. **M5 is closed on this reading.** What keeps the literal exit open: only R-Type of the six
   reaches 20 M; the others stop between 187 and 630,583 instructions. That cannot be closed
   without a judge for U21/U32 (hardware or a tier-1 capture), so it is recorded, not hidden.
   If Aubrey refuses the amendment, M5 stays open on exactly that item and nothing else (the sweep
   half, the mappers and the unlisted images are done).

## U17: the speed

Measured here for the first time, PyPy 3.11, Space Harrier (TurboGrafx-16), 300 frames: 167 s of
CPU time, **1.8 frames a second, 0.03x real time** (59.8 fps). The 20-frame CPython run of the same
card took 8.7 s CPU, 2.3 frames a second: **PyPy was not faster than CPython** on it (the warm-up
is the likeliest reason; not investigated; the instance attribute counts are all below 80, so
the dict limit of the 80-attribute dict limit is not the cause). The extrapolation in
[start-here.md](start-here.md) (0.2-0.5x on PyPy) is roughly ten times too high for the board as
built. Wall times in the sweep were worse because the machine ran at load 60-80 on 32 cores:
median 442 s per card for 600 frames in pass 1, 1,636 s for 1,500 in pass 2; the whole of pass 1 took
about 4 h with ten cards in parallel. The plain board is the reference, not the fast one
(speed is the `-fast` projects' job), so this is recorded, not fixed.

## The PyPy gate

2026-11-04, after the comparator fix: `pytest` on PyPy 3.11.13: 228 passed, 2 skipped (numpy: the
PSG referee test and the new `tests/test_m5_sweep_compare.py`), 13 s; CPython 3.14: 228 passed, 1
skipped (the new test: Pillow is missing from the venv), 6 s. The new test needs numpy and Pillow, so it
was run by hand under the system python3 (it passes there, and the old `best_frame` picks the wrong
frame on the same data). `ruff check`: the same 2 errors as before (`scripts/psg_compare.py` C401,
`src/pcengine_python/psg/chip.py` E501); `ruff format --check`: the same 3 files as before
(`scripts/m2_ours.py`, `scripts/m5_sweep.py` which was already unformatted at HEAD, and `psg/chip.py`).
The sweep itself runs the board under PyPy for every card.

## Reproducing

```text
python3 -I scripts/m5_sweep.py /data/emu/roms-retrobat/pcengine SCRATCH RESULTS.jsonl --cards 10 --jobs 3
python3 -I scripts/m5_sweep.py LIB SCRATCH OUT.jsonl --names LIST.txt --targets 900 1500
python3 scripts/m5_summary.py RESULTS.jsonl --table
```

Needs the cards (BYOR), the Mesen2 and Beetle builds under `reference/`, `7z`, numpy and Pillow
(the system python3). Read-only for the cards; the pictures are compared at the 9-bit value, never
at RGB.
