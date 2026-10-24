"""The frame/line clock and the picture capture.

`Timeline` is the VCE's sync generator: it owns the line and frame counters on the board's one
master-clock timeline and decides 262 or 263 lines per frame (C3). `Capture` turns each line into
a row of 9-bit palette values (`-------GGGRRRBBB`), looking the VDC's pixel indices up in the
colour table *as it stood at each dot*, so a mid-line palette write splits the line exactly where
the CPU wrote it: that is what Covell's CPU test draws.

Compare pictures at the 9-bit values, never at RGB (docs/vce.md).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pcengine_python.machine import (
    ACTIVE_LINES,
    FRAME_LINES_LONG,
    FRAME_LINES_SHORT,
    HSYNC_CLOCKS,
    LINE_CLOCKS,
    TOP_BLANK_LINES,
    VSYNC_LINES,
    Machine,
)
from pcengine_python.sockets import DirectPath, PixelPath, VideoTiming
from pcengine_python.vce import Vce


class Timeline:
    def __init__(
        self, machine: Machine, vce: Vce, start_line: int = 0, start_offset: int = 0
    ) -> None:
        """Time zero is the start of line `start_line` of frame 0 (U1: the power-up phase of the
        raster against the CPU is not published; MAME's CPU test trace starts at line 260).
        `start_offset` puts time zero that many master clocks *into* the line instead."""
        self._machine = machine
        self._vce = vce
        self.frame = 0
        self.frame_lines = self._lines_for_frame()
        if not 0 <= start_line < self.frame_lines:
            raise ValueError(f"start_line {start_line} outside the {self.frame_lines}-line frame")
        self.line = start_line
        self.line_start = -start_offset

    def _lines_for_frame(self) -> int:
        # C3: sampled where the frame starts, as Mednafen samples it where the vsync ends.
        if self._machine.lines_follow_vce_bit2 and not self._vce.bit2:
            return FRAME_LINES_SHORT
        return FRAME_LINES_LONG

    @property
    def next_line_start(self) -> int:
        return self.line_start + LINE_CLOCKS

    @property
    def in_vsync(self) -> bool:
        return self.line >= self.frame_lines - VSYNC_LINES

    def timing(self) -> VideoTiming:
        return VideoTiming(
            frame=self.frame,
            line=self.line,
            start_mclk=self.line_start,
            dot_divider=self._vce.dot_divider,
            frame_lines=self.frame_lines,
            in_vsync=self.in_vsync,
        )

    def advance(self) -> None:
        """Step to the next line; at the end of a frame start the next and re-read the VCE."""
        self.line_start += LINE_CLOCKS
        self.line += 1
        if self.line >= self.frame_lines:
            self.line = 0
            self.frame += 1
            self.frame_lines = self._lines_for_frame()


@dataclass
class Frame:
    """The 242 active lines of a frame: `rows[i]` is the 9-bit palette values of line 14 + i."""

    number: int
    rows: list[list[int]]
    dividers: list[int]


class Capture:
    def __init__(
        self,
        vce: Vce,
        path: PixelPath | None = None,
        on_frame: Callable[[Frame], None] | None = None,
    ) -> None:
        self._vce = vce
        self.path = path if path is not None else DirectPath()
        self._on_frame = on_frame
        self._shadow = list(vce.palette)  # the colour table as the line capture has replayed it
        self._rows: list[list[int]] = []
        self._dividers: list[int] = []
        self.last_frame: Frame | None = None

    def finish_line(self, timing: VideoTiming, vdc_rows: list[list[int]]) -> None:
        """Called once the row of a line has ended.

        [emu: Mednafen vce.cpp] A row is the 1365 master clocks from the end of the line's
        horizontal sync to the end of the next line's: dot 0 is the first dot after the sync, so
        a 256-wide picture (HDS 2) starts at dot 32 and fits in the row. This is the same
        raster as `timing.start_mclk`, shifted by `HSYNC_CLOCKS`."""
        row = self.path.mix(timing, vdc_rows)
        first = timing.start_mclk + HSYNC_CLOCKS
        end = first + LINE_CLOCKS
        div = timing.dot_divider
        log = self._vce.palette_log
        used = 0
        while used < len(log) and log[used][0] < end:
            used += 1
        colours = []
        pending = 0
        shadow = self._shadow
        for x, pixel in enumerate(row):
            when = first + x * div
            while pending < used and log[pending][0] <= when:
                shadow[log[pending][1]] = log[pending][2]
                pending += 1
            if pixel & 0x0F == 0:  # colour 0 of every palette shows the backdrop/overscan entry
                pixel &= 0x100
            colours.append(shadow[pixel])
        while pending < used:
            shadow[log[pending][1]] = log[pending][2]
            pending += 1
        del log[:used]
        if timing.line == 0:
            self._rows, self._dividers = [], []
        if TOP_BLANK_LINES <= timing.line < TOP_BLANK_LINES + ACTIVE_LINES:
            self._rows.append(colours)
            self._dividers.append(div)
            if len(self._rows) == ACTIVE_LINES:
                self.last_frame = Frame(timing.frame, self._rows, self._dividers)
                if self._on_frame is not None:
                    self._on_frame(self.last_frame)
