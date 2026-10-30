# Milestone 5 as built: the library sweep, and where the lockstep stands

Run 2026-10-30 on the code after the DMA and status-flag work (commits f6fb910..5826715), then
again after two small board fixes this sweep found (below). Judges: **Mesen2 (sprites on) and
Beetle PCE, both emulators, tier 5**: neither is a judge, they are two votes ([validation.md](validation.md)).
The lockstep half is in [m5-lockstep-record.md](m5-lockstep-record.md).

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

## Counts

| | IDENTICAL | NEAR | DIFFERENT |
| --- | --- | --- | --- |
| Pass 1 before the DMA work (2026-10-25) | 156 | 7 | 16 |
| **Pass 1 now** (code 5826715) | **162** | **6** | **11** |
| After the two fixes (76 of the 179 re-run, see below; the rest assumed unchanged) | 164 | 6 | 9 |

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
| **Formation Soccer** | IDENTICAL | **NEAR** 0.992/1.000 | **a regression**: a loading bar's red line (36 px, rows 115-116) is missing at frame 300 and present at 600; the picture is one frame out of step with the referees now (pass 2: identical at 900 and 1500). Not run down |

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
Beetle identical) and HuZERO (both referees, 2.5 % of rows, row 79). Not run down; animated frames.
Of the 6 cards that had moved to identical, all 6 stayed identical at 900 and 1500.

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
identical to Mesen2 (C31), Santatlantean different (U36), HuZERO different at 1500 only (see above).

## The lockstep exit, honestly

The M5 exit asks for "6 games lockstep >= N M instructions with 0 unexplained". It is **not met**:

| Game | Mednafen, instructions equal | Where it stops | Named cause |
| --- | --- | --- | --- |
| R-Type I | **20,000,000** (668 entries, 0 read differences) | nowhere | none |
| Gradius | 107,737 | IRQ1 one instruction apart | U21 (the tie rule) |
| Final Soldier | 630,583 | an entry one instruction apart after 2,607 entries | U21; its waits are U33 (the 16-dot window) |
| After Burner II | 187 | a SAT transfer Mednafen does not start | U32 (the power-up display phase) |
| Bomberman '94 | 343,164 | a register read after a late-visibility resync | U21 |
| Bonk's Adventure | 235,057 | `RTI` returns to `C8D1`, Mednafen to `C8CE` | U21 (resync with another pushed address) |

Against MAME, none reaches 20 M (172,272 at best, R-Type). The remaining stops are U21 (the tie
rule of interrupt visibility, tier 5 against tier 5), U33 (the 16-dot window) and U32 (the power-up
phase): each is named, none is decided, and no stop has a tier-1 judge. Every stop has a named cause, so nothing is
"unexplained" in the sense of an unnamed cause; the count of games that run 20 M is still one.

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

`pytest` on PyPy 3.11.13 (7.3.20): 228 passed, 1 skipped (numpy), 24 s. CPython 3.14: 228 passed,
13 s. `ruff check` (2 errors: `scripts/psg_compare.py` C401, `src/pcengine_python/psg/chip.py` E501) and
`ruff format --check` (3 files, among them `scripts/m2_ours.py`) report exactly what they reported
before this work, and nothing in the files changed here. The sweep itself runs the board under PyPy for every card.

## Reproducing

```text
python3 -I scripts/m5_sweep.py /data/emu/roms-retrobat/pcengine SCRATCH RESULTS.jsonl --cards 10 --jobs 3
python3 -I scripts/m5_sweep.py LIB SCRATCH OUT.jsonl --names LIST.txt --targets 900 1500
python3 scripts/m5_summary.py RESULTS.jsonl --table
```

Needs the cards (BYOR), the Mesen2 and Beetle builds under `reference/`, `7z`, numpy and Pillow
(the system python3). Read-only for the cards; the pictures are compared at the 9-bit value, never
at RGB.
