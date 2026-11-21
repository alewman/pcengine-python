# SPDX-License-Identifier: MIT
# Behaviour informed by MAME's src/devices/video/huc6270.cpp and huc6260.cpp, BSD-3-Clause,
# copyright Wilbert Pol (notice in NOTICE.md): read, not transcribed. Written for the clean
# rewrite of 2026-11-19 (docs/restart.md) without the withdrawn module or any GPL source.
"""The HuC6270's line machine: the horizontal and vertical periods on the board's master clock.

Sources, in the order they decide a question:
    [mfr] Hudson, HuC6270 CMOS Video Display Controller Manual: registers HSR, HDR, VPR, VDW, VCR,
          RCR, BXR, BYR, CR (SB/BB, burst mode), MWR, the status bits, Fig. 2-2-1, 2.4.1 (6).
    [hw]  Charles MacDonald, pcetech.txt sections 5.1, 5.4 and 7 (tested on hardware).
    [emu] MAME huc6270.cpp / huc6260.cpp (BSD-3-Clause): an emulator, used where the two
          documents say nothing, and named where it is used.
    [fit] Covell's CPU-test photographs (tier 1) through `vblank_dots`.

**The line** (the board's frame: a line starts when the VCE's horizontal sync falls):

    0 ........ HSYNC_CLOCKS ......... display start .......... display end ........ 1365
    |  sync    | HDS+1 characters       | HDW+1 characters       | HDE+1, HSW+1 ...  |

- The VCE drives /HSYN and /VSYN [doc: wiki VDC pinout, "the VDC synchronizes its video output"];
  the sync is low for the first `HSYNC_CLOCKS` = 237 master clocks of a line [emu: MAME
  huc6260.cpp "HSync is low for 237 and high for 1128 master cycles"].
- **Line step**, at the end of the sync (the sync's rising edge) [emu: MAME: the VDC's line
  begins there; mfr: HDS is counted "from the rising edge of a horizontal sync signal"]: the
  vertical period counts one line, the raster counter and the vertical scroll counter count one,
  and on a display line the sprites of this line are fetched (2.4.1 (6): fetched during the
  horizontal blanking that precedes the line's display).
- **Display start** (HDS+1) characters of 8 dots after the line step [mfr: HSR, Fig. 2-2-1];
  each field is read at the start of its own period [mfr: HSR/HDR "valid at the beginning of
  each period"]. The display lasts HDW+1 characters, cut at the next line step if longer [emu:
  MAME: the sync's end restarts the horizontal periods]. The scroll registers and CR's SB/BB are
  taken before the display starts: CR's SB/BB at the display start [mfr: "valid from the next
  horizontal display period"], BXR and the vertical scroll counter `SCROLL_LATCH_DOTS` = 16 dots
  (two characters) before it. MAME takes BXR at the display start; that drew one line wrong in
  Bomberman '94, and a **closed-box measurement** (docs/restart.md; Bomberman '94 and After
  Burner II at frame 300 against Mesen2 b9fa69d and Beetle PCE b96c11e) gives both referees'
  pictures with the scroll taken 12 or 16 dots early, not 0, 8, 24 or 40: FITTED, emulator tier,
  provisional; the reason offered (the first character's fetch precedes its pixels) is a
  HYPOTHESIS. The line is drawn at the display start (vdc/chip.py `render_line`).
- **Raster compare** as the sync falls, against the counter as the previous line's step left
  it [emu: MAME compares at the falling edge]. The counter is set to $40 at the step of the line
  before the display period [mfr: RCR "set to '64' at the previous scanning line of start timing
  of display period and is incremented for each scan"], so RCR $40 interrupts as the first
  display line begins [hw: pcetech 5.1, $40 = line 25, $146 = line 24 of the next frame]. Where
  in the line no document says. A **closed-box measurement** (docs/restart.md) found no single
  place that suits both After Burner II (identical to both referees at 0 of the offsets tried,
  0-500 master clocks after the sync falls, and at the previous display's end) and Bomberman '94
  (identical from 40 to 333): MAME's place is kept, After Burner II being one of the 18 gate
  titles; Bomberman '94 was settled instead by the scroll latch below (provisional).

**The frame.** The vertical periods follow the manual's encodings, counted in line steps from the
line on which the vertical sync falls (the board calls `vsync` as line `frame_lines - 3` begins):
VSW+1 lines of sync, VDS+2 lines to the display, VDW+1 display lines [mfr: VPR, VDW], then the
front porch: VCR+3 lines [hw: pcetech 7: "3 blanked lines ... for as many lines as are specified
in VCR"; the manual's "VCR should be N" disagrees by the three lines: C-entry, pcetech taken].
After the front porch the VDC starts its own sync (VSW) without waiting for the VCE [hw: pcetech
7, "the display counter resets"]; the VCE's vertical sync restarts VSW wherever it lands. Each
field is read when its period begins [mfr: VPR "at the beginning of each period", VDW "at the
beginning of a vertical display period", VCR "at the beginning of a vertical front porch"].

- **Vertical blanking** begins on the first line after the display period [hw: pcetech 5, status
  bit 5]. Its time inside that line is `vblank_dots` dots after the line step, -16 by default
  (before it: FITTED to Covell's photographs, tier 1, U19: the place the earlier default of -8 held
  against the photographs before the display moved 8 dots nearer the sync; -18 fits them best,
  docs/restart.md), or the display start of that
  line with `vblank_dots=None` [emu: MAME's comment "VBlank IRQ happens at the beginning of HDW
  period after VDW ends"]. Then: the VD flag, the VRAM -> SAT transfer [mfr: "at the beginning of
  a vertical blanking period"] and the MWR fields that change only then [mfr: MWR VM/SM/SCREEN].
- A display period that the VCE's vertical sync cuts short has its vertical blanking on the next
  line [hw: pcetech 5: with more than 261 display lines "the interrupt will always occur on line
  261", the line after the sync begins on line 260].
- **Burst mode** is taken when the VDC's frame begins (its VSW): SB = BB = 0 then holds the frame
  in burst mode [mfr: CR "burst mode will start with the next frame ... cleared in next frame";
  hw: pcetech 5.1, "if bits 7 and 6 are cleared by the time the next frame starts", with his
  note that it may be the display start instead: provisional].

Power-on (U7-like, a choice): the registers are zero and the vertical counter runs from VSW, so
the VDC free-runs on its own short frames until the first vertical sync arrives.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from pcengine_python.machine import HSYNC_CLOCKS, LINE_CLOCKS
from pcengine_python.vdc import regs as r

if TYPE_CHECKING:
    from pcengine_python.vdc.chip import Vdc

CHARACTER_DOTS = 8  # [mfr: Fig. 2-2-1] the horizontal fields count characters of 8 dots
FRONT_PORCH_EXTRA_LINES = 3  # [hw: pcetech 7] the front porch is VCR + 3 lines
# Master clocks from the sync's fall to the raster compare [emu: MAME: 0]; an experiment's knob
# (docs/restart.md: no single value fits both After Burner II and Bomberman '94).
RASTER_COMPARE_CLOCKS = 0
# Dots before the display start at which the scroll registers are taken (closed-box fit, module
# doc): two characters, the fetch of the first character having to precede its pixels.
SCROLL_LATCH_DOTS = 16


class VPhase(enum.IntEnum):
    """The vertical periods, in the manual's order [mfr: Fig. 2-2-1]."""

    VSW = 0  # vertical sync
    VDS = 1  # to the display ("vertical back porch")
    VDW = 2  # the display period
    VCR = 3  # the front porch


class Sequencer:
    def __init__(self, chip: Vdc, vblank_dots: int | None = -16) -> None:
        self.chip = chip
        self.vblank_dots = vblank_dots
        self.divider = 4  # master clocks per dot on this line (the VCE's, read at the line start)
        self.origin = 0  # master-clock time at which this line's sync fell
        self.vphase = VPhase.VSW
        self.lines_left = 1  # line steps left in the vertical period (power-on: VSW = 0 + 1)
        self._vsync_this_line = False  # the period began at this line's start: its step counts it
        self.rcr_count = 0x3FF  # raster counter - $40; out of range until the first display period
        self._rcr_compared = self.rcr_count
        self.display_count = -1  # display lines begun in this display period, less one
        self.burst_mode = False
        self.cr_cache = 0  # CR as the display start of this line took it
        self.display_line = False  # this line draws (display period, not burst mode)
        self.active_display = False  # alias kept for the slot model: the display fetches VRAM
        self.active_start = 0  # this line's display, in master clocks
        self.active_end = 0
        self._vblank_owed = False  # the vertical sync cut a display period short
        self._events: list[tuple[int, int, str]] = []  # (time, order, name), sorted
        self._order = 0

    # -- the scheduler ------------------------------------------------------------------------

    def schedule(self, when: int, name: str) -> None:
        self._order += 1
        self._events.append((when, self._order, name))
        self._events.sort()

    def _drop(self, name: str) -> None:
        self._events = [e for e in self._events if e[2] != name]

    def next_event(self) -> int | None:
        return self._events[0][0] if self._events else None

    def run_to(self, t: int) -> None:
        """Handle every event due at or before master-clock time `t`."""
        chip = self.chip
        while self._events and self._events[0][0] <= t:
            when, _, name = self._events.pop(0)
            chip.now = when
            if name == "step":
                self._step(when)
            elif name == "latch":
                chip.latch_scroll()
            elif name == "display":
                self._display_start(when)
            elif name == "raster":
                chip.raster_test(self._rcr_compared)
            elif name == "vblank":
                chip.vblank_begins()
            elif name == "collision":
                chip.collision_hit()

    # -- the VCE's syncs ----------------------------------------------------------------------

    def hsync(self, mclk: int, divider: int) -> None:
        """The horizontal sync falls: a line begins (the board calls this at each line start)."""
        chip = self.chip
        chip.now = mclk
        self.origin = mclk
        self.divider = divider
        self._vsync_this_line = False
        self._rcr_compared = self.rcr_count  # the count as the previous line step left it
        if RASTER_COMPARE_CLOCKS:
            self.schedule(mclk + RASTER_COMPARE_CLOCKS, "raster")
        else:
            chip.raster_test(self._rcr_compared)  # [emu: MAME] as the sync falls
        step_at = mclk + HSYNC_CLOCKS
        self.schedule(step_at, "step")
        # The vertical blanking of the line after the display period (or the line after a cut).
        if self._vblank_owed or (self.vphase == VPhase.VDW and self.lines_left == 0):
            self._vblank_owed = False
            if self.vblank_dots is None:
                when = step_at + (chip.regs.hds + 1) * CHARACTER_DOTS * divider
            else:
                when = step_at + self.vblank_dots * divider
            self.schedule(max(when, mclk), "vblank")

    def vsync(self) -> None:
        """The vertical sync falls (the board calls this after `hsync` of the line it falls on)."""
        if self.vphase == VPhase.VDW and not any(e[2] == "vblank" for e in self._events):
            self._vblank_owed = True  # cut short: the vertical blanking comes on the next line
        self._enter(VPhase.VSW)
        self._vsync_this_line = True

    # -- the line step ------------------------------------------------------------------------

    def _step(self, now: int) -> None:
        chip = self.chip
        # [emu: MAME] the end of the sync restarts the horizontal periods: a display that ran on
        # from the last line ends here, and one that never started is dropped.
        self._drop("display")
        self._drop("latch")
        if self.active_end > now:
            self.active_end = now
        chip.line_begins()
        self.rcr_count += 1
        if self._vsync_this_line:
            self._vsync_this_line = False  # the vertical sync's first line: no period change
        elif self.lines_left <= 0:
            self._enter(self._following(self.vphase))
        self.lines_left -= 1
        if self.vphase == VPhase.VDS and self.lines_left == 0:
            self.rcr_count = 0  # [mfr: RCR] 64 on the line before the display period
        self.display_line = self.vphase == VPhase.VDW and not self.burst_mode
        self.active_display = self.display_line
        if self.vphase == VPhase.VDW:
            self.display_count += 1
            if self.display_line:
                chip.fetch_sprites(self.display_count)
        start = now + (chip.regs.hds + 1) * CHARACTER_DOTS * self.divider
        if start < self.origin + LINE_CLOCKS + HSYNC_CLOCKS:
            self.schedule(max(now, start - SCROLL_LATCH_DOTS * self.divider), "latch")
            self.schedule(start, "display")

    @staticmethod
    def _following(phase: VPhase) -> VPhase:
        return VPhase((phase + 1) % 4)

    def _enter(self, phase: VPhase) -> None:
        chip = self.chip
        regs = chip.regs
        self.vphase = phase
        if phase == VPhase.VSW:
            self.lines_left = regs.vsw + 1  # [mfr: VPR "N-1"]
            # [mfr: CR] the VDC's frame begins: SB = BB = 0 now holds the frame in burst mode
            burst = not regs.cr & (r.CR_SPRITES | r.CR_BACKGROUND)
            began = burst and not self.burst_mode
            self.burst_mode = burst
            if began:
                chip.burst_began()
        elif phase == VPhase.VDS:
            self.lines_left = regs.vds + 2  # [mfr: VPR "N-2"]
        elif phase == VPhase.VDW:
            self.lines_left = regs.vdw + 1  # [mfr: VDW "N-1"]
            self.display_count = -1
            chip.display_period_starts()
        else:
            self.lines_left = regs.vcr + FRONT_PORCH_EXTRA_LINES

    # -- the display width --------------------------------------------------------------------

    def _display_start(self, now: int) -> None:
        chip = self.chip
        self.active_start = now
        width = (chip.regs.hdw + 1) * CHARACTER_DOTS * self.divider  # [mfr: HDR "N-1"]
        self.active_end = min(now + width, self.origin + LINE_CLOCKS + HSYNC_CLOCKS)
        self.cr_cache = chip.regs.cr  # [mfr: CR SB/BB "valid from the next horizontal display"]
        chip.render_line()
