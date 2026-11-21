"""The I/O port ($1000-$13FF, one register) and what answers on the pad pins.

[hw: pcetech 4] Reads: D7 CD-unit sense (1 = not attached; C6 records sgxtech's opposite
sentence), D6 country (1 = PC Engine, 0 = TurboGrafx-16), D5-D4 always 1, D3-D0 the pad pins.
Writes: D1 = CLR, D0 = SEL. The port never returns buffer bits, but a read does load the buffer.

[mfr: HuC6280 hardware manual 2.5, 2.6] The CPU's output port (port O, O0-O7) is a latch that
reads back nothing and is driven high by a system reset, so SEL and CLR both power up *high*;
the eight bits are kept because the SuperGrafx's S-EXP port uses O2-O7. Port K (K0-K7) is the
input the pad pins and the CD sense reach.
"""

from __future__ import annotations

from collections.abc import Callable

from pcengine_python.sockets import ControllerPort


class IoPort:
    def __init__(
        self,
        *,
        country_pc_engine: bool,
        cd_attached: Callable[[], bool],
        device: ControllerPort | None = None,
    ) -> None:
        self.country_pc_engine = country_pc_engine
        self._cd_attached = cd_attached
        self.device = device
        self.latch = 0xFF  # [mfr: HuC6280 manual 2.5] "H level is output to the output port"

    @property
    def sel(self) -> bool:
        return bool(self.latch & 1)

    @property
    def clr(self) -> bool:
        return bool(self.latch & 2)

    def reset(self) -> None:
        self.latch = 0xFF

    def read(self) -> int:
        # Pins pulled up on an empty port: every pad bit reads 1 (docs: controller-info
        # "all inputs default to high"; pcetech: unconnected controllers return $0F).
        nibble = 0x0F if self.device is None else self.device.read(self.sel, self.clr) & 0x0F
        value = 0x30 | nibble
        if not self._cd_attached():
            value |= 0x80
        if self.country_pc_engine:
            value |= 0x40
        return value

    def write(self, value: int) -> None:
        self.latch = value
        if self.device is not None:
            self.device.write(self.sel, self.clr)
