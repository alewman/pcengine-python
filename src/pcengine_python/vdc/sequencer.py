"""The VDC's vertical state machine and the horizontal events of one line.

Provisional, emulator tier 5 (U19): no tier 1-3 source gives the dot at which the vblank flag
rises or the raster compare fires. This is Mednafen's `huc6270/vdc.cpp` (HSync/VSync/IncRCR
and the HPHASE machine), restated in master clocks so that it runs from the board's one
timeline. What *is* published: the frame layout and "VDS+VSW lines before the first active
line", [hw: pcetech 7]; the flag rules of status bit 5 [hw: pcetech 5]; the RCR range
$40-$146 counted from the first active line [hw: pcetech 5.1].

Vertical phases run VSW -> VDS -> VDW -> VCR -> VSW, counted once per line at the end of the
displayed width (4 dots before it ends: Mednafen's HDW_FINAL). The VCE starts the VSW phase at
the vertical sync, which is the last three lines of its frame, so with VSW = $02 and VDS = $17
the first line of the display period is frame line 25, as pcetech 7 says.

Horizontal events within a line (dot = the VCE's dot divider in master clocks, measured from the
VCE's hsync start at the line's origin):

    origin + 237            hsync ends (`HSYNC_CLOCKS`, emu)
    + 8 dots                HDS: the display-start phase begins; a pending line counter step
                            from the previous line is taken here if not yet done
    + (HDS + 1) * 8 dots    HDW: the display width begins; vblank flag test, sprite scan (M3)
    + (HDW + 1) * 8 - 4     HDW final: the line counter steps (RCR compare, phase counters)
"""

from __future__ import annotations

from enum import IntEnum
from typing import Protocol

from pcengine_python.machine import HSYNC_CLOCKS
from pcengine_python.vdc.regs import VdcRegisters


class VPhase(IntEnum):
    VSW = 0
    VDS = 1
    VDW = 2
    VCR = 3


# [emu: Mednafen `Cycles_Between_RCRIRQ_And_HDWEnd = 4`]
FINAL_DOTS = 4
# [emu: Mednafen HSW phase counter 8 after leaving hsync]
HSW_DOTS = 8


class Sequencer:
    """State and events only; the chip owns the registers and reacts through `chip`."""

    def __init__(self, chip: _ChipSide) -> None:
        self.chip = chip
        # [emu: Mednafen Reset] power-up phase VDS with one line left; arbitrary but fixed (U1).
        self.vphase = VPhase.VDS
        self.vphase_counter = 1
        self.rcr_count = 0
        self.scanline_from_vsync = 0
        self.need_rcr_inc = False
        self.need_vb_irq_test = False
        self.burst_mode = False
        self.display_line = False  # this line is in the display period and not burst
        self.cr_cache = 0  # CR as the line's display start latched it
        # cached at the vertical sync / start of the VSW phase
        self.vds = self.vsw = self.vdw = self.vcr = 0
        # line geometry, set by hsync()
        self.divider = 4
        self.origin = 0
        self.hds_start = 0
        self.active_start = 0
        self.final_at = 0
        self.active_end = 0
        self._events: list[tuple[int, str]] = []
        self._next_line = (0, 4, 0, 0)
        self._cache_vertical()

    # -- the board's hooks --------------------------------------------------------------------

    def next_event(self) -> int | None:
        return self._events[0][0] if self._events else None

    def run_to(self, mclk: int) -> None:
        while self._events and self._events[0][0] <= mclk:
            _, kind = self._events.pop(0)
            if kind == "leave":
                self._leave_hsync()
            elif kind == "hds":
                self._hds()
            elif kind == "hdw":
                self._hdw()
            else:
                self._final()

    def hsync(self, mclk: int, divider: int) -> None:
        """The VCE's horizontal sync starts: cache the horizontal registers; the line proper
        begins when the sync ends. Events of the previous line may still be pending: with
        HDS = 2 and HDW = $1F a 5 MHz line's width-end lands 8 master clocks into the next
        line's sync, and it must still run (emu: Mednafen caches at sync start, restarts at
        sync end)."""
        regs = self.chip.regs
        self._next_line = (mclk, divider, regs.hds, regs.hdw)
        self._events.append((mclk + HSYNC_CLOCKS, "leave"))
        self._events.sort(key=lambda e: e[0])

    def _leave_hsync(self) -> None:
        origin, divider, hds, hdw = self._next_line
        self.origin = origin
        self.divider = divider
        self.hds_start = origin + HSYNC_CLOCKS + HSW_DOTS * divider
        self.active_start = self.hds_start + (hds + 1) * 8 * divider
        self.active_end = self.active_start + (hdw + 1) * 8 * divider
        self.final_at = self.active_end - FINAL_DOTS * divider
        # Stale events of the previous line are dropped, as Mednafen's HPhase is overwritten.
        self._events = [
            (self.hds_start, "hds"),
            (self.active_start, "hdw"),
            (self.final_at, "final"),
        ]

    def vsync(self) -> None:
        """The vertical sync starts (the last three lines of the VCE's frame).

        Deviation from Mednafen (tier 5), which drops the previous line's pending line-counter
        step here: pcetech 5.1 (tier 2) gives RCR a range of 263 values ($40-$146) counted from
        the first active line, so a 263-line frame must make 263 steps and the step is taken
        now instead (U19).
        """
        if self.need_rcr_inc:
            self._inc_rcr()
            self.need_rcr_inc = False
        self._cache_vertical()
        self.vphase = VPhase.VSW
        self.vphase_counter = self.vsw + 1
        self.scanline_from_vsync = 0

    # -- events -------------------------------------------------------------------------------

    @property
    def active_display(self) -> bool:
        """The current line is in the display period and not burst (valid from HDW start)."""
        return self.display_line

    def _hds(self) -> None:
        self.cr_cache = self.chip.regs.cr
        if self.need_rcr_inc:
            self._inc_rcr()
            self.need_rcr_inc = False

    def _hdw(self) -> None:
        self.display_line = self.vphase == VPhase.VDW and not self.burst_mode
        self.need_rcr_inc = True
        if self.vphase != VPhase.VDW and self.need_vb_irq_test:
            self.need_vb_irq_test = False
            self.chip.vblank_test()
        self.chip.commit_pending()

    def _final(self) -> None:
        if self.scanline_from_vsync == self.vsw + 1:
            # [emu: Mednafen] burst mode is decided once a frame, from CR as the display
            # period begins; pcetech 5.1 "locked when the next frame starts" (footnote 1).
            self.burst_mode = not (self.chip.regs.cr & 0xC0)
        if self.need_rcr_inc:
            self._inc_rcr()
            self.need_rcr_inc = False

    def _cache_vertical(self) -> None:
        regs = self.chip.regs
        self.vds, self.vsw, self.vdw, self.vcr = regs.vds, regs.vsw, regs.vdw, regs.vcr

    def _inc_rcr(self) -> None:
        self.rcr_count += 1
        self.vphase_counter -= 1
        self.scanline_from_vsync += 1
        if self.vphase_counter <= 0:
            self.vphase = VPhase((self.vphase + 1) % 4)
            if self.vphase == VPhase.VDS:
                self.vphase_counter = self.vds + 2
            elif self.vphase == VPhase.VDW:
                self.vphase_counter = self.vdw + 1
                self.rcr_count = 0
                self.need_vb_irq_test = True
            elif self.vphase == VPhase.VCR:
                self.vphase_counter = self.vcr
            else:
                self.vphase_counter = self.vsw + 1
                self.scanline_from_vsync = 0
                self._cache_vertical()
        self.chip.raster_test(self.rcr_count)


class _ChipSide(Protocol):
    """What the sequencer needs from the chip (`Vdc` satisfies it)."""

    regs: VdcRegisters

    def vblank_test(self) -> None: ...

    def raster_test(self, count: int) -> None: ...

    def commit_pending(self) -> None: ...
