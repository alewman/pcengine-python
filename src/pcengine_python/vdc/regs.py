"""The HuC6270's register file and the fields the timing generator reads.

[hw: pcetech 5.1; mfr: Hudson HuC6270 manual] Registers are 16 bits, written a byte at a time.
Valid register numbers are $00-$02 and $05-$13; the rest do nothing.
"""

from __future__ import annotations

# Status port bits (read of $0). [hw: pcetech 5]
BSY = 0x40
VD = 0x20  # vertical blank
DV = 0x10  # VRAM -> VRAM DMA done
DS = 0x08  # VRAM -> SAT DMA done
RR = 0x04  # raster compare
OR = 0x02  # sprite overflow
CR_FLAG = 0x01  # sprite 0 collision
IRQ_BITS = 0x3F

# Control register enable bits.
CR_COLLISION_IRQ = 0x01
CR_OVERFLOW_IRQ = 0x02
CR_RASTER_IRQ = 0x04
CR_VBLANK_IRQ = 0x08
CR_SPRITES = 0x40
CR_BACKGROUND = 0x80

# [hw: pcetech 5.1 register $05] CR bits 12-11 select how much MAWR/MARR advance per access.
INCREMENTS = (1, 32, 64, 128)

VALID_REGISTERS = frozenset({0x00, 0x01, 0x02, *range(0x05, 0x14)})

(MAWR, MARR, VRW) = (0x00, 0x01, 0x02)
(CR, RCR, BXR, BYR, MWR, HSR, HDR, VPR, VDW, VCR) = range(0x05, 0x0F)
(DCR, SOUR, DESR, LENR, SATB) = range(0x0F, 0x14)


class VdcRegisters:
    """Raw 16-bit register values, with the fields the sequencer uses as properties."""

    def __init__(self) -> None:
        self.select = 0
        self.value = [0] * 0x20
        # [hw: pcetech 5.1] The read buffer is indeterminate on power-up, "usually $FFFF".
        self.read_buffer = 0xFFFF
        self.write_latch = 0

    def set_byte(self, register: int, byte: int, msb: bool) -> None:
        old = self.value[register]
        if msb:
            self.value[register] = (old & 0x00FF) | (byte << 8)
        else:
            self.value[register] = (old & 0xFF00) | byte

    # -- fields -------------------------------------------------------------------------------

    @property
    def cr(self) -> int:
        return self.value[CR]

    @property
    def increment(self) -> int:
        return INCREMENTS[(self.value[CR] >> 11) & 3]

    @property
    def rcr(self) -> int:
        return self.value[RCR] & 0x3FF

    @property
    def mwr(self) -> int:
        return self.value[MWR]

    @property
    def hds(self) -> int:
        return (self.value[HSR] >> 8) & 0x7F

    @property
    def hdw(self) -> int:
        return self.value[HDR] & 0x7F

    @property
    def hde(self) -> int:
        return (self.value[HDR] >> 8) & 0x7F

    @property
    def vsw(self) -> int:
        return self.value[VPR] & 0x1F

    @property
    def vds(self) -> int:
        return (self.value[VPR] >> 8) & 0xFF

    @property
    def vdw(self) -> int:
        return self.value[VDW] & 0x1FF

    @property
    def vcr(self) -> int:
        return self.value[VCR] & 0xFF
