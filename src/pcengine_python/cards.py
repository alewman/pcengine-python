"""HuCards. M1 has the standard ROM card; SF2, Populous and Tennokoe are M5.

A card is on the CPU's physical bus: PA20 is its chip enable, so it answers banks $00-$7F (the
1 MiB window = pages 0x0000-0x0FFF); there is no header (docs/cartridge.md). Mirroring of
smaller images:

- 384 KiB: the first 256 KiB fills banks $00-$3F twice, the last 128 KiB fills $40-$7F four
  times [emu: MAME `pce_slot.cpp` rom_map_setup `0 1 0 1 2 2 2 2`; Mednafen `huc.cpp`].
- 512 KiB: $00-$3F straight, $40-$7F the upper 256 KiB twice [emu: Mednafen; MAME generic].
- other power-of-two sizes: mirrored to fill the window.
- anything else (768 KiB, odd homebrew sizes): U18, provisional: banks repeat modulo the image.
All tier 3-4; confirmed only by games running.
"""

from __future__ import annotations

from pathlib import Path

from pcengine_python.sockets import BoardPins, ResetKind

BANK = 8 * 1024
WINDOW_BANKS = 128  # $00-$7F
COPIER_HEADER = 512


def strip_copier_header(data: bytes) -> bytes:
    """A 512-byte copier header is the only thing to strip (size mod 8192 = 512)."""
    return data[COPIER_HEADER:] if len(data) % BANK == COPIER_HEADER else data


def bank_map(rom_banks: int) -> list[int]:
    """For each of the 128 banks of the window, which 8 KiB bank of the image answers."""
    if rom_banks == 48:  # 384 KiB
        return [(b % 32) if b < 64 else 32 + (b % 16) for b in range(WINDOW_BANKS)]
    if rom_banks == 64:  # 512 KiB
        return [b if b < 64 else 32 + (b % 32) for b in range(WINDOW_BANKS)]
    return [b % rom_banks for b in range(WINDOW_BANKS)]


class RomCard:
    """The standard HuCard: ROM only, mirrored to fill the window."""

    grounds_cd = True  # [doc: wiki HuCard pinout] a card grounds /CD

    def __init__(self, data: bytes) -> None:
        data = strip_copier_header(data)
        if not data:
            raise ValueError("an empty HuCard image; an empty slot is CardSlot(None)")
        if len(data) % BANK:
            data = data + bytes(BANK - len(data) % BANK)  # U18: pad a ragged image with zeros
        self.data = data
        self._map = bank_map(len(data) // BANK)

    @classmethod
    def from_path(cls, path: str | Path) -> RomCard:
        """Read in place; BYOR, nothing is copied (the .gitignore refuses *.pce)."""
        return cls(Path(path).read_bytes())

    def bind(self, pins: BoardPins) -> None:
        pass

    def claims(self) -> list[tuple[int, int]]:
        return [(0x0000, 0x0FFF)]

    def read(self, address: int, mclk: int) -> int:
        bank = (address >> 13) & 0x7F
        return self.data[self._map[bank] * BANK + (address & 0x1FFF)]

    def write(self, address: int, value: int, mclk: int) -> None:
        pass  # a plain ROM ignores writes

    def reset(self, kind: ResetKind) -> None:
        pass
