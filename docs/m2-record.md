# Milestone 2 record: the VDC background, DMA, burst mode, and the first ten titles

Status (2026-10-24): **the exit holds for the background**: the first ten library titles reach
their title screens and every one is pixel- and row-identical, at the 9-bit palette value, to
Mesen2 (sprites disabled) over the whole frame; where Beetle PCE and Mesen2 agree (which is
everywhere sprites are not) ours is identical to Beetle too. Sprites are M3 and are the only
difference from the pictures as the detectors ship them. The pinned core needed an experiment on
one title (core issue 0002). C7 is decided.

## What was built

| Module | What |
| --- | --- |
| `vdc/background.py` | a line of the background from the BAT and the planar tiles: BAT 32/64/128 x 32/64, scroll, CG mode, palette in the BAT word, a per-instance decode cache |
| `vdc/dma.py` | VRAM -> VRAM DMA (SOUR/DESR/LENR, DCR steps and done IRQ, two dots a word), VRAM -> SAT DMA (armed by DVSSR, run when the display ends or every frame with DCR D4, busy 1024 dots), CPU VRAM accesses waiting behind either |
| `vdc/sequencer.py` | the scroll latches (BYR, BXR) a few dots after the line's display start, the per-line draw at the display width, burst mode, display start and end hooks |
| `vdc/chip.py` | `render_line`, BYR/BXR/SATB/LENR register effects |

Tests: `tests/test_vdc_background.py` (18) against pcetech 5 (tier 2) and Hudson's VDC manual
(tier 3): tile decode, per-line words, scroll, BAT size and wrap, vertical scroll, CG mode, the
backdrop and overscan rules, burst mode, DMA copy and counters, DCR steps, done IRQ, the two
readings of C7, the SAT copy and its late done flag, auto-repeat, CPU VRAM access behind a DMA.

## The judge: ten titles against Mesen2 and Beetle PCE

`scripts/m2_ours.py` (the board with the real core, PyPy), `m2_refs.py` (Mesen2 with
`DisableSprites`, Mesen2 as shipped, Beetle PCE over a window of 21 frames) and `m2_compare.py`
(9-bit alignment; no mask). The first ten HuCards of `/data/emu/roms-retrobat/pcengine` in
alphabetical order, read in place (extracted to scratch for the detectors, removed afterwards),
300 frames from power-on (450 for the two whose frame 300 is still black).

| Title | Frames | A: ours = Mesen2, no sprites (px / rows) | C: ours = Beetle where Beetle = Mesen2 | E: Mesen2 = Beetle, both as shipped |
| --- | --- | --- | --- | --- |
| Aero Blasters (USA) | 300 | 1.0000 / 1.0000 | 1.0000 | 1.0000 |
| After Burner II (Japan) (En) | 300 | 1.0000 / 1.0000 (Mesen2 frame 302) **with the issue-0002 experiment**; 0.7708 without | 1.0000 | 1.0000 |
| Air Zonk (USA) | 450 | 1.0000 / 1.0000 | 1.0000 | 1.0000 |
| Alien Crush (USA) | 300 | 1.0000 / 1.0000 | 1.0000 | 1.0000 |
| Andre Panza Kick Boxing (USA) (7 MHz) | 300 | 1.0000 / 1.0000 | 1.0000 | 1.0000 |
| Armed F (Japan) (En) | 300 | 1.0000 / 1.0000 | 1.0000 | 1.0000 |
| Atomic Robo-Kid Special (Japan) (En) | 300 | 1.0000 / 1.0000 | 1.0000 | 1.0000 |
| Ballistix (USA) | 450 | 1.0000 / 1.0000 | 1.0000 | 1.0000 |
| Barbarian (Amiga 500) (7 MHz) | 300 | 1.0000 / 1.0000 | 1.0000 | 1.0000 |
| Barbarian (Amstrad CPC) (7 MHz) | 300 | 1.0000 / 1.0000 | 1.0000 | 1.0000 |

The overlap is the whole picture (70,664 pixels at 5 MHz, 94,138 at 7 MHz). Against the pictures
as the detectors ship them (B), ours differs only where sprites are: Armed F's ship, Ballistix's
and Air Zonk's text and balls, Alien Crush's and Armed F's titles (Alien Crush's logo is made of
sprites), After Burner II's HUD; B is 1.0000 for Aero Blasters and Andre Panza, which have none.

Alignment (the same for every title of a dot clock): Mesen2's column x is our dot x - 14 (5 MHz) or
- 24 (7 MHz); Beetle's is x - 32 and x - 46; Mesen2 and Beetle start on frame line 14; no vertical
offset. **The two detectors agree with each other on the whole of every picture (E = 1.0000)**, so there
is no disagreement to explain for these ten at the chosen frames. Their frame numbers differ from
ours by up to 12: After Burner II's title animation steps every four frames and ours (frame 300)
equals Mesen2's frames 302-305, and Barbarian's Beetle frames lag 2-19; the window absorbs it.

### The one title that needed the core to change: After Burner II

With the pinned core the game executes garbage after about 90 frames. Its timer handler runs
`CLI` and then `STZ $1403` (acknowledge the timer); the core polls in the instruction's
second-to-last cycle, sees TIQ asserted, the last cycle lowers it, and the entry happens with
nothing asserted, through the IRQ2 vector (`$EE7B`, which is data). Mesen2 re-checks the timer
source live and does not take the interrupt (its comment cites two other games). Raised as
core issue 0002 (`/data/emu/huc6280-python/docs/issues/`), commit `ea48c94` there; the board
cannot fix it. `scripts/m2_ours.py --drop-vanished-irq` is the experiment: an interrupt whose
sources are all gone at the boundary is not taken. It was used for the table above; the other
nine titles are identical with and without it. **C11**: which behaviour is the chip's is
*undecidable here* (tier 5, Mesen2's own comment says untested on hardware).

## Decisions

- **C7 decided: a VRAM -> VRAM DMA running when the display period starts is paused and resumes
  afterwards** (MacDonald, tier 2: "halted, not aborted"; Mesen2 does the same). Hudson's manual
  (tier 3) says the remainder is not transferred, and Mednafen cancels it: `Board(dma_resumes=False)`.
  No title here exercises the difference.
- **U2 (SAT DMA)**: the table is copied when the display period ends, the VDC is busy 1024 dots
  (Mednafen, Mesen2: tier 5), and the done flag follows then. At 5 MHz that is three lines: pcetech's
  "four lines after the last active line" counts from the last line; at 7 and 10 MHz it is 2.25 and
  1.5 lines and no tier 1-3 source says which holds. Provisional.
- **U3 (scroll latches)**: BYR latched one dot after the display-start phase begins and BXR two
  dots later for HDS <= 2 (Mednafen's positions, tier 5); a register change after that shows on the
  next line, and the line is drawn in one go as the display width begins. A game that changes
  BXR/BYR mid-line differs from hardware by an unknown amount (none of the ten does).
- **U25**: VRAM -> VRAM DMA speed, two dots a word (Mednafen and Mesen2 agree; tier 5).
- **U26**: when a DMA may run: here, whenever the display is not drawing a line (Mesen2 starts at the
  vblank flag, Mednafen after the SAT transfer; tier 5).
- **Burst mode** as Mednafen: decided once a frame from CR when the display period begins.

## The background, against the other emulator that was not run

MAME is not used for pictures (docs/mame-oracle.md): its snapshots are 1088 columns of four per
dot with the colour table's own conversion, and on Covell's test it draws different colours.
