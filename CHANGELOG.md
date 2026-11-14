# Changelog

Releases are git tags; install one with
`pip install "pcengine-python @ git+https://github.com/alewman/pcengine-python@v0.2.0"`.
Not on PyPI (the CPU core is pinned by git commit).

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
