"""The HuC6260 VCE: colour table, control register, dot clock, frame length.

[mfr: Hudson HuC6260 manual; hw: pcetech 6; doc: wiki "VCE pinout", "Timing"] (MacDonald's
headings swap the VDC and VCE names: C1.)

Registers ($FF:0400-07FF, 8-byte mirror):
    $0 control (write only)    D7 monochrome, D2 blur / line count (C3), D1-D0 dot clock
    $2/$3 colour address LSB/MSB (write only; 9 bits)
    $4/$5 colour data LSB/MSB  (the address advances after the MSB, read or write)

Everything else reads $FF. The palette is 512 entries of `-------GGGRRRBBB`.

Output colour: the board exposes the 9-bit pixel and palette values; turning GRB into RGB is a
replaceable table (`rgb_table`), because there is no standard conversion (docs/vce.md). The
default is a plain linear 3-bit expansion, which is *not* any emulator's colours.
"""

from __future__ import annotations

import random

# Dot clock divider by CR bits 1-0 [hw: pcetech 6, doc: wiki Timing]: 5.37, 7.16, 10.7 MHz.
# Hudson's manual knows only 4 and 3 (C8); bit 1 set is MacDonald's 10 MHz mode.
DOT_DIVIDERS = (4, 3, 2, 2)


def linear_rgb_table() -> list[tuple[int, int, int]]:
    """Entry `GGGRRRBBB` -> (r, g, b), each 3-bit value scaled by 255/7."""
    table = []
    for entry in range(512):
        g, rd, b = (entry >> 6) & 7, (entry >> 3) & 7, entry & 7
        table.append((rd * 255 // 7, g * 255 // 7, b * 255 // 7))
    return table


class Vce:
    def __init__(self, *, power_on: random.Random | None = None) -> None:
        # U7: zeros by default, random on request.
        if power_on is None:
            self.palette = [0] * 512
            self.control = 0
            self.address = 0
        else:
            self.palette = [power_on.getrandbits(9) for _ in range(512)]
            self.control = power_on.getrandbits(8)
            self.address = power_on.getrandbits(9)
        self.rgb_table = linear_rgb_table()
        # (mclk, entry, value) of every palette change, drained by the line capture.
        self.palette_log: list[tuple[int, int, int]] = []

    # -- derived ------------------------------------------------------------------------------

    @property
    def dot_divider(self) -> int:
        return DOT_DIVIDERS[self.control & 3]

    @property
    def monochrome(self) -> bool:
        return bool(self.control & 0x80)

    @property
    def bit2(self) -> bool:
        return bool(self.control & 0x04)

    def rgb(self, entry: int) -> tuple[int, int, int]:
        return self.rgb_table[self.palette[entry & 0x1FF]]

    # -- the CPU's port -----------------------------------------------------------------------

    def read(self, offset: int, mclk: int) -> int:
        reg = offset & 7
        if reg == 4:
            return self.palette[self.address] & 0xFF
        if reg == 5:
            value = 0xFE | ((self.palette[self.address] >> 8) & 1)
            self.address = (self.address + 1) & 0x1FF
            return value
        return 0xFF

    def write(self, offset: int, value: int, mclk: int) -> None:
        reg = offset & 7
        if reg == 0:
            self.control = value
        elif reg == 2:
            self.address = (self.address & 0x100) | value
        elif reg == 3:
            self.address = (self.address & 0x0FF) | ((value & 1) << 8)
        elif reg == 4:
            self._set_entry((self.palette[self.address] & 0x100) | value, mclk)
        elif reg == 5:
            self._set_entry((self.palette[self.address] & 0x0FF) | ((value & 1) << 8), mclk)
            self.address = (self.address + 1) & 0x1FF

    def _set_entry(self, value: int, mclk: int) -> None:
        self.palette[self.address] = value
        self.palette_log.append((mclk, self.address, value))
