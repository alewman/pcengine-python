"""One decode for every bus master: the 8192-entry page table.

A page is 256 bytes of the 21-bit physical space. Each page has a handler; the board fills
the base map (RAM, the hardware page, an empty slot answering $FF) and a card or expansion
device *claims* ranges of pages, which replaces the base handler there, as the hardware does
bank by bank (a Super System Card's RAM overrides the ROM mirror). There is no second bus master
on a PC Engine, so the CPU's data and fetch accesses, `ST0`-`ST2`, block transfers, the
debugger's peek and the lockstep probe all call `read`/`write` here.
"""

from __future__ import annotations

from pcengine_python.machine import ADDRESS_MASK, PAGE_BITS, PAGE_COUNT
from pcengine_python.sockets import PageHandler


class Unmapped:
    """[hw: pcetech 3] Unused banks always return $FF; writes do nothing."""

    def read(self, address: int, mclk: int) -> int:
        return 0xFF

    def write(self, address: int, value: int, mclk: int) -> None:
        pass


class Ram:
    """Work RAM: `size` bytes mirrored through the pages it is claimed on."""

    def __init__(self, size: int, initial: bytes | None = None) -> None:
        self.data = bytearray(initial if initial is not None else bytes(size))
        self._mask = size - 1  # sizes are powers of two (8 KiB, 32 KiB)

    def read(self, address: int, mclk: int) -> int:
        return self.data[address & self._mask]

    def write(self, address: int, value: int, mclk: int) -> None:
        self.data[address & self._mask] = value


class PageTable:
    def __init__(self) -> None:
        self._unmapped = Unmapped()
        self._base: list[PageHandler] = [self._unmapped] * PAGE_COUNT
        self._current: list[PageHandler] = list(self._base)

    # -- construction -------------------------------------------------------------------------

    def set_base(self, first_page: int, last_page: int, handler: PageHandler) -> None:
        """The board's own map. Replaces whatever is there, claims included."""
        for page in range(first_page, last_page + 1):
            self._base[page] = handler
            self._current[page] = handler

    def claim(self, first_page: int, last_page: int, handler: PageHandler) -> None:
        """A device takes a range of pages from the base map."""
        if not 0 <= first_page <= last_page < PAGE_COUNT:
            raise ValueError(f"page range {first_page:#x}-{last_page:#x} outside 0-{PAGE_COUNT:#x}")
        for page in range(first_page, last_page + 1):
            self._current[page] = handler

    def release(self, first_page: int, last_page: int, handler: PageHandler) -> None:
        """Give pages back to the base map, where `handler` still holds them."""
        for page in range(first_page, last_page + 1):
            if self._current[page] is handler:
                self._current[page] = self._base[page]

    def handler(self, address: int) -> PageHandler:
        return self._current[(address & ADDRESS_MASK) >> PAGE_BITS]

    # -- the bus ------------------------------------------------------------------------------

    def read(self, address: int, mclk: int) -> int:
        address &= ADDRESS_MASK
        return self._current[address >> PAGE_BITS].read(address, mclk)

    def write(self, address: int, value: int, mclk: int) -> None:
        address &= ADDRESS_MASK
        self._current[address >> PAGE_BITS].write(address, value & 0xFF, mclk)
