"""The HuC6280's 7-bit timer ($0C00-$0FFF, mirrored every 2 bytes).

[hw: pcetech 2.2] One tick per 1024 high-speed CPU cycles (master/3072) whatever the CPU speed.
`$0C00` is a latch (0 counts as 1, $7F as 128); `$0C01` bit 0 enables. The interrupt line is
asserted when the counter goes from 0 to $7F; at that moment it is reloaded from the latch and
keeps counting, whether or not the interrupt has been acknowledged.

[mfr: HuC6280 hardware manual 2.7] "When 0 is written in the Timer Start/Stop flag, the timer
stops and the prescaler is reset", and the down-counter is loaded from the reload register when the
flag goes from 0 to 1. So a tick is one full prescaler period (1024 cycles of master/3, 3072 master
clocks) after the enabling write, and a stop and restart always begin a fresh period (U24, closed
as far as the sources go: tier 3 for the reset, the full first period follows from it; what stays
tier 5 is Mednafen's one-clock-late reload after an underflow, which MAME does not have, and
this model follows pcetech 2.2's "reloaded when it occurs"). The manual also cautions that the
count can read invalid while it changes; that is not modelled.
"""

from __future__ import annotations

TICK_CLOCKS = 1024 * 3


class Timer:
    def __init__(self) -> None:
        self.latch = 0  # [hw: pcetech 2] power-up: count 0, disabled
        self.count = 0
        self.enabled = False
        self.irq = False  # the TIQ line: held until $1403 is written
        self._next_tick = 0

    def reset(self) -> None:
        self.latch = 0
        self.count = 0
        self.enabled = False
        self.irq = False

    def catch_up(self, mclk: int) -> None:
        while self.enabled and self._next_tick <= mclk:
            self._next_tick += TICK_CLOCKS
            if self.count == 0:
                # 0 -> $7F underflow: assert the line, reload from the latch (pcetech 2.2).
                self.irq = True
                self.count = self.latch
            else:
                self.count -= 1

    def next_event(self) -> int | None:
        """Master-clock time of the next underflow, or None while disabled."""
        if not self.enabled:
            return None
        return self._next_tick + self.count * TICK_CLOCKS

    def read(self, buffer: int, mclk: int) -> int:
        self.catch_up(mclk)
        # Bit 7 returns the I/O buffer; the low seven bits are the live count.
        return self.count | (buffer & 0x80)

    def write(self, offset: int, value: int, mclk: int) -> None:
        self.catch_up(mclk)
        if offset & 1 == 0:
            # The latch only; the running count is untouched until the next reload.
            self.latch = value & 0x7F
        else:
            enable = bool(value & 1)
            if enable and not self.enabled:
                # Disabled -> enabled: reload from the latch, restart the prescaler (U24).
                self.count = self.latch
                self._next_tick = mclk + TICK_CLOCKS
            self.enabled = enable

    def acknowledge(self) -> None:
        """[hw: pcetech 2.1] any write to $1403 acknowledges the timer."""
        self.irq = False
