"""The I/O port ($1000-$13FF, one register) and what answers on the pad pins.

[hw: pcetech 4] Reads: D7 CD-unit sense (1 = not attached; C6 records sgxtech's opposite
sentence), D6 country (1 = PC Engine, 0 = TurboGrafx-16), D5-D4 always 1, D3-D0 the pad pins.
Writes: D1 = CLR, D0 = SEL. The port never returns buffer bits, but a read does load the buffer.
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
        self.sel = False
        self.clr = False

    def reset(self) -> None:
        self.sel = False
        self.clr = False

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
        self.sel = bool(value & 1)
        self.clr = bool(value & 2)
        if self.device is not None:
            self.device.write(self.sel, self.clr)
