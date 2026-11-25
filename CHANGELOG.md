<!-- SPDX-License-Identifier: MIT -->
# Changelog

Releases are git tags; install one with
`pip install "pcengine-python @ git+https://github.com/alewman/pcengine-python@v0.2.0"`.
Not on PyPI (the CPU core is pinned by git commit).

## Unreleased

The clean rewrite of 2026-11-19 ([docs/restart.md](docs/restart.md)): the parts the licence audit
marked "rewrite" or "unclear" were withdrawn unread and written again from Hudson's manuals,
pcetech.txt and MAME's BSD-3 files; no GPL source was read.

- **Mesen2 through mesen2-runner 0.2.0 only** (2026-11-24): `scripts/m2_refs.py` runs
  `$EMU_TOOLS_GPL/tools/mesen2/run.py --machine pce` with `--no-sprites` and `--input` (presses
  through `presses.contract_input`) instead of the old command line; pictures identical before and
  after (docs/validation.md, "Moved to mesen2-runner 0.2.0").

- **A display that starts before the row** (a small HDS puts it inside the sync) is cropped: its
  early columns are dropped and the row keeps its 1365/divider dots. The new line machine let
  this happen and `render_line` then inserted the pixels instead of overwriting them (the row
  grew to 682 dots at divider 4). Found by supergrafx-rust on the SuperGrafx probe card in
  compat mode, where pcengine-rust panicked; test in `tests/test_vdc_timing.py`.

- **VDC line machine** (`vdc/sequencer.py`, new): the line step at the end of the horizontal sync;
  the display (HDS + 1) characters later, HDW + 1 long; vertical periods VSW + 1, VDS + 2,
  VDW + 1 and VCR + 3 lines from the line the vertical sync falls on, the VDC running its own sync
  after the front porch; RCR compared as the sync falls, the counter set on the line before the
  display; burst mode taken when the VDC's frame begins; a display cut short by the vertical sync
  has its vertical blanking on the next line.
- **The picture moved 8 dots left in the row**: a 256-wide display starts at dot 24, not 32.
- **Vertical blanking default `vblank_dots=-16`** (was -8): the same place against Covell's
  photographs as before, the display having moved; `vblank_dots=None` is now the display start.
  -18 fits the photographs slightly better; Aubrey ruled on 2026-11-20 to keep -16 as the default,
  with -18 available as `Board(vblank_dots=-18)`.
- **Scroll**: the vertical scroll counter is loaded from BYR at the display period's start and on
  either BYR byte, +1 a line; BXR and the counter are taken 16 dots before the display start (a
  closed-box fit on Bomberman '94 and After Burner II). MWR's VM, SM and
  screen bits take effect at the vertical blanking, CM at each line.
- **Sprites**: the budget is the manual's table (entries searched by HDW, patterns fetched by
  HDE + HSW + HDS and SM); a short budget sets OR. `sprites.scan(..., searched=64)`;
  `CLOCKS_PER_SPRITE` removed.
- **DMA**: the SAT transfer starts at the vertical blanking and holds the VRAM three lines
  (`SAT_CLOCKS`, pcetech 5.4; was 1,024 dots); a VRAM word takes two accesses at the MWR access
  width (`ACCESS_DOTS`; 2 dots at VM 0 as before). `force_complete` replaced by
  `finish_without_display` (a VDC with no board).
- **Timer**: `underflow_window_mclk` 3 (was 15), one PPS3 clock; Battle Royale's picture is the
  same for any window from 1 to 60.
- **Removed**: `Board(vertical_at_line_start=...)`, `Vdc(vertical_at_line_start=...)` (the lockstep
  scripts' `--mame-vertical` stays and does nothing); `Vdc.commit_unless_dma`,
  `DmaEngine.force_complete`, `dma.SAT_DOTS`, `dma.DMA_DOTS_PER_WORD`.
- Judges (docs/restart.md): the 18-title gate identical to both referees; the 179-card sweep
  168 identical (was 170; Barbarian (Atari ST) and Pac-Land regressed, open); Covell's
  photographs as close as before at the new default; the Mednafen lockstep stops earlier (its
  "Full" conventions were built for the withdrawn geometry).
- Documents: no GPL code or internal names quoted; NOTICE.md acknowledges MAME's huc6270, huc6260
  and h6280 (BSD-3-Clause). `m5_sweep.py --refs-cache`; the compare scripts prefer the new
  alignment offsets.
- Licence notices (the audit's three "cite" items closed, comments and documents only, no
  behaviour change): `psg/chip.py` and `cards.py` carry SPDX headers naming MAME's c6280.cpp and
  pce_slot.cpp / pce_rom.cpp (BSD-3-Clause); NOTICE.md acknowledges the cartridge files;
  `scripts/psg_referees/` gains a README and SPDX headers: the Mednafen harness and its shim are a
  GPL-2.0-or-later tool outside the MIT package (binaries never distributed), the MAME harness and
  the build scripts MIT.

## 0.2.0 (2026-11-14)

- CPU core: huc6280-python 0.4.0 (265df88, its issue 0005): interrupt polling at the edges of
  an instruction follows the stated rule, and a save state now carries the lines the last poll saw
  (states from 0.1.0 still load).

- Issue 0004 (findings from the Rust port): a CPU access that waits on a VDC transfer no longer
  runs the VDC ahead of the line clock. `/BUSY` holds only the CPU, so the board now runs every
  device event by event until the access is served (`Board._serve_vram`, `Vdc(serve=...)`): a
  VRAM DMA the CPU waits on meets the display start, paused (C7) or cancelled
  (`dma_resumes=False`). The 18-title picture gate is byte-identical before and after.
- `Psg.silent_units` set on an instance now reaches the host-rate output.
- Unused `Psg._acc_steps`, `Psg._reload_lfo_channels`, `PopulousCard.RAM_BANKS` removed;
  docs/sockets.md cites U13 for the video bus; `Board.reset` documents that a power-on reset is
  not a power cycle.

## 0.1.0 (2026-11-12)

The first release: the PC Engine and TurboGrafx-16 with HuCards.

- Milestones M1 to M5: clocks, timer, interrupts and the raster (M1, closed as a documented
  provisional against Covell's photographs); the VDC's background and sprites (M2, M3: 27 pictures
  identical to Mesen2 and Beetle PCE); the PSG (M4); the mappers (Street Fighter II', Populous,
  Tennokoe), the 179-card sweep (170 identical, 9 different and triaged) and lockstep (M5).
- Sockets for add-on boards (docs/sockets.md): a second VDC and a pixel path (issue 0001, the
  SuperGrafx), port devices caught up by the scheduler (0002) and mixed audio sources (0003, the CD).
- Save states (`pcengine_python.state`), proven by round trip on 18 titles.
- Scripted pad input for the picture scripts (`scripts/presses.py`).
- CPU core: huc6280-python 0.3.0 (pinned at bf20330; 9c47c98 at the time of the sweep, the same
  results: decimal `ADC`/`SBC` with an
  invalid BCD digit follow Mednafen's formulas).
