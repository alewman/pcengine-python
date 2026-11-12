# Changelog

Releases are git tags; install one with
`pip install "pcengine-python @ git+https://github.com/alewman/pcengine-python@v0.1.0"`.
Not on PyPI (the CPU core is pinned by git commit).

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
- CPU core: huc6280-python 0.3.0 (9c47c98 at the time of the sweep: decimal `ADC`/`SBC` with an
  invalid BCD digit follow Mednafen's formulas).
