"""The HuC6280's on-die peripherals that are not the CPU: timer, $1400 interrupt
controller, I/O port and the I/O buffer (Aubrey's rule: in the board, behind a module boundary).

Nothing here imports from the rest of pcengine_python except the `sockets` Protocols
(tests/test_boundaries.py enforces it), so the package can move into a core or a repository of
its own if a second consumer appears (a Data East arcade board's HuC6280). Never copied.

`CpuIo` answers the hardware-page offsets $0800-$17FF: the PSG range is forwarded to an
object the board supplies, so this package does not import the PSG.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from pcengine_python.cpu_io.io_buffer import IoBuffer
from pcengine_python.cpu_io.io_port import IoPort
from pcengine_python.cpu_io.irq_ctl import IrqController
from pcengine_python.cpu_io.timer import Timer
from pcengine_python.sockets import ControllerPort

__all__ = ["CpuIo", "IoBuffer", "IoPort", "IrqController", "PsgPins", "Timer"]


class PsgPins(Protocol):
    """What CpuIo needs from the sound generator: its register writes."""

    def write(self, offset: int, value: int, mclk: int) -> None: ...


class CpuIo:
    def __init__(
        self,
        psg: PsgPins,
        *,
        country_pc_engine: bool,
        cd_attached: Callable[[], bool] = lambda: False,
        pad: ControllerPort | None = None,
        on_irq_disable: Callable[[int], None] | None = None,
    ) -> None:
        self.buffer = IoBuffer()
        self.timer = Timer()
        self.irq = IrqController(self.timer.acknowledge, on_irq_disable)
        self.port = IoPort(country_pc_engine=country_pc_engine, cd_attached=cd_attached, device=pad)
        self._psg = psg

    def reset(self) -> None:
        self.buffer.reset()
        self.timer.reset()
        self.irq.reset()
        self.port.reset()

    def catch_up(self, mclk: int) -> None:
        self.timer.catch_up(mclk)

    def next_event(self) -> int | None:
        return self.timer.next_event()

    @property
    def tiq(self) -> bool:
        return self.timer.irq

    def read(self, offset: int, mclk: int) -> int:
        """`offset` is the hardware-page offset, $0800-$17FF. Loads the buffer, as pcetech 3."""
        offset &= 0x1FFF
        if offset < 0x0C00:  # PSG: every address returns the buffer in full
            return self.buffer.value
        if offset < 0x1000:
            value = self.timer.read(self.buffer.value, mclk)
        elif offset < 0x1400:
            value = self.port.read()
        else:
            self.timer.catch_up(mclk)
            value = self.irq.read(offset, self.buffer.value, self.timer.irq)
        self.buffer.value = value
        return value

    def write(self, offset: int, value: int, mclk: int) -> None:
        offset &= 0x1FFF
        self.buffer.value = value
        if offset < 0x0C00:
            self._psg.write(offset & 0x0F, value, mclk)
        elif offset < 0x1000:
            self.timer.write(offset, value, mclk)
        elif offset < 0x1400:
            self.port.write(value)
        else:
            self.timer.catch_up(mclk)
            self.irq.write(offset, value)

    def peek(self, offset: int) -> int:
        """A read with no side effects, for the debugger and the lockstep probe."""
        offset &= 0x1FFF
        buf = self.buffer.value
        if offset < 0x0C00:
            return buf
        if offset < 0x1000:
            return self.timer.count | (buf & 0x80)
        if offset < 0x1400:
            return self.port.read()
        return self.irq.read(offset, buf, self.timer.irq)
