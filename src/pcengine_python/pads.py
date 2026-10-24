"""The pads: 2-button, 6-button and the 5-player multitap (the mouse is not modelled: U12).

All implement `sockets.ControllerPort`: the console drives SEL and CLR, the device answers a
nibble on D3-D0 (active low: 0 = pressed). Held-button state is a bit mask the host sets.

Sources: [hw: pcetech 4] for the 2-button pad and the Turbo Tap; [doc: pce-devel
PCE_Controller_Info] for the 6-button scan counting and the multitap port table.
"""

from __future__ import annotations

from collections.abc import Sequence

from pcengine_python.sockets import ControllerPort

# Button bits of the host-side state mask.
UP, RIGHT, DOWN, LEFT = 0x001, 0x002, 0x004, 0x008
I, II, SELECT, RUN = 0x010, 0x020, 0x040, 0x080  # noqa: E741
III, IV, V, VI = 0x100, 0x200, 0x400, 0x800


class Pad2:
    """A 2-button pad: SEL high shows the directions, SEL low the buttons.

    [hw: pcetech 4] While CLR is high the pad's multiplexer outputs 0 on D3-D0. [doc:
    controller-info] the 74HC157 gates all four outputs low on CLR."""

    def __init__(self) -> None:
        self.pressed = 0

    def write(self, sel: bool, clr: bool) -> None:
        pass

    def read(self, sel: bool, clr: bool) -> int:
        if clr:
            return 0
        if sel:
            return ~self.pressed & 0x0F
        return ~(self.pressed >> 4) & 0x0F


class Pad6(Pad2):
    """The Avenue Pad 6 shape: on alternating scans (counted by CLR pulses) the SEL-high read
    shows 0000 and the SEL-low read shows III-VI instead of I, II, Select, Run. [doc:
    controller-info] Which scan comes first at power-up is not stated (a game scans twice)."""

    def __init__(self) -> None:
        super().__init__()
        self.second_scan = False
        self._clr = False

    def write(self, sel: bool, clr: bool) -> None:
        if clr and not self._clr:
            self.second_scan = not self.second_scan
        self._clr = clr

    def read(self, sel: bool, clr: bool) -> int:
        if clr:
            return 0
        if not self.second_scan:
            return super().read(sel, clr)
        if sel:
            return 0
        return ~(self.pressed >> 8) & 0x0F


class MultiTap:
    """The Turbo Tap: a counter picks which of five ports answers.

    [hw: pcetech 4] The counter increments on each SEL 0 -> 1 transition while CLR is low and
    resets on a CLR 0 -> 1 transition with SEL high; after the fifth it answers $0 until reset;
    an empty port answers $F.

    C10: pcetech says that right after the reset write ($03: SEL and CLR high) D3-D0 already
    show pad 1's directions; the pce-devel table puts CLR high on every port at that moment,
    which would read 0. `clr_high_reads_pad` selects pcetech's reading (tier 2, the default).
    """

    PORTS = 5

    def __init__(
        self, pads: Sequence[ControllerPort | None], *, clr_high_reads_pad: bool = True
    ) -> None:
        if len(pads) != self.PORTS:
            raise ValueError("a multitap has five ports")
        self.pads = list(pads)
        self.clr_high_reads_pad = clr_high_reads_pad
        self.counter = self.PORTS  # no port selected until the first reset sequence
        self._sel = False
        self._clr = False

    def write(self, sel: bool, clr: bool) -> None:
        if clr and not self._clr and sel:
            self.counter = 0
        elif sel and not self._sel and not clr and self.counter < self.PORTS:
            self.counter += 1
        self._sel = sel
        self._clr = clr

    def read(self, sel: bool, clr: bool) -> int:
        if self.counter >= self.PORTS:
            return 0
        if clr and not self.clr_high_reads_pad:
            return 0
        pad = self.pads[self.counter]
        if pad is None:
            return 0x0F
        return pad.read(sel, False)
