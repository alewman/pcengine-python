"""The HuC6280 PSG package (board-owned, import-boundary tested).

Milestone 1 holds only the register file that `$0800-$0809` writes reach, so the page table
and the I/O buffer have something real behind them. The six channels, noise, LFO, DDA and the
`AudioSource` come in M4 (docs/psg.md); until then `take_samples` returns nothing.
"""

from __future__ import annotations

from collections.abc import Sequence


class Psg:
    rate_hz = 3_579_545 / 32  # M4: the native step rate is master/6 divided down; placeholder
    gain = 1.0

    def __init__(self) -> None:
        # [mfr: Hudson PSG manual] R0 channel select, R1 main amplitude, R2-R7 per channel,
        # R8 LFO frequency, R9 LFO control. Unused offsets $0A-$0F ignore writes.
        self.global_regs = [0] * 10
        self.channel_regs = [[0] * 10 for _ in range(6)]
        self.waveform = [[0] * 32 for _ in range(6)]

    def write(self, offset: int, value: int, mclk: int) -> None:
        offset &= 0x0F
        if offset >= 10:
            return
        self.global_regs[offset] = value
        select = self.global_regs[0] & 7
        if 2 <= offset <= 7 and select < 6:
            self.channel_regs[select][offset] = value

    def take_samples(self, mclk: int) -> Sequence[tuple[int, int]]:
        return ()
