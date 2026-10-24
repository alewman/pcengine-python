"""The hardware page, bank $FF ($1FE000-$1FFFFF), as 32 pages of 256 bytes.

[hw: pcetech 3]
    $0000-$03FF  VDC   (4-byte mirror)       $0800-$0BFF  PSG   (in the CPU)
    $0400-$07FF  VCE   (8-byte mirror)       $0C00-$0FFF  timer (2-byte mirror)
    $1000-$13FF  I/O port                    $1400-$17FF  interrupt controller (4-byte mirror)
    $1800-$1FFF  unmapped, reads $FF

The pages $1800-$1FFF are free for an add-on to claim (`CD` at $1800-$18FF, the Arcade Card at
$1A00-$1AFF); the page table's claim replaces these handlers.
"""

from __future__ import annotations

from pcengine_python.cpu_io import CpuIo
from pcengine_python.machine import HARDWARE_FIRST_PAGE
from pcengine_python.pagetable import PageTable
from pcengine_python.vce import Vce
from pcengine_python.vdc import Vdc


class VdcPage:
    def __init__(self, vdc: Vdc) -> None:
        self._vdc = vdc

    def read(self, address: int, mclk: int) -> int:
        return self._vdc.read(address & 3, mclk)

    def write(self, address: int, value: int, mclk: int) -> None:
        self._vdc.write(address & 3, value, mclk)


class VcePage:
    def __init__(self, vce: Vce) -> None:
        self._vce = vce

    def read(self, address: int, mclk: int) -> int:
        return self._vce.read(address & 7, mclk)

    def write(self, address: int, value: int, mclk: int) -> None:
        self._vce.write(address & 7, value, mclk)


class CpuIoPage:
    def __init__(self, cpu_io: CpuIo) -> None:
        self._io = cpu_io

    def read(self, address: int, mclk: int) -> int:
        return self._io.read(address & 0x1FFF, mclk)

    def write(self, address: int, value: int, mclk: int) -> None:
        self._io.write(address & 0x1FFF, value, mclk)


def map_hardware_page(pages: PageTable, vdc: Vdc, vce: Vce, cpu_io: CpuIo) -> None:
    """Install the board's own handlers on the 32 pages of bank $FF."""
    first = HARDWARE_FIRST_PAGE
    pages.set_base(first, first + 0x03, VdcPage(vdc))
    pages.set_base(first + 0x04, first + 0x07, VcePage(vce))
    pages.set_base(first + 0x08, first + 0x17, CpuIoPage(cpu_io))
