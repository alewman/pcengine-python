"""The interrupt controller ($1400-$17FF, mirrored every 4 bytes).

[hw: pcetech 2.1] `$1402`: bits 2-0 are disable bits, 1 = disabled (bit 2 timer, bit 1 IRQ1, bit 0
IRQ2), readable and writable, bits 7-3 return the I/O buffer. `$1403`: reads the *line* state
in bits 2-0 even when masked, upper five bits the buffer; any write acknowledges the timer.
`$1400`/`$1401`: writes do nothing, reads return the buffer. The mask only stops the CPU from
taking the interrupt; the core gets the raw lines and the mask (`irq_disable`) and decides.
"""

from __future__ import annotations

from collections.abc import Callable

TIMER = 0b100
IRQ1 = 0b010
IRQ2 = 0b001


class IrqController:
    def __init__(
        self,
        acknowledge_timer: Callable[[], None],
        on_mask_change: Callable[[int], None] | None = None,
    ) -> None:
        self.disable = 0  # [hw: pcetech 2] power-up: the disable mask is zero
        self.irq1 = False
        self.irq2 = False
        self._acknowledge_timer = acknowledge_timer
        self._on_mask_change = on_mask_change

    def reset(self) -> None:
        self.disable = 0
        self.irq1 = False
        self.irq2 = False

    def status(self, timer_irq: bool) -> int:
        return (TIMER if timer_irq else 0) | (IRQ1 if self.irq1 else 0) | (IRQ2 if self.irq2 else 0)

    def read(self, offset: int, buffer: int, timer_irq: bool) -> int:
        if offset & 2 == 0:
            return buffer
        low = self.disable if offset & 1 == 0 else self.status(timer_irq)
        return low | (buffer & 0xF8)

    def write(self, offset: int, value: int) -> None:
        if offset & 3 == 2:
            self.disable = value & 7
            if self._on_mask_change is not None:
                self._on_mask_change(self.disable)
        elif offset & 3 == 3:
            self._acknowledge_timer()
