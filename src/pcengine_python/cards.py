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


# --- the mappers beyond plain ROM (M5) --------------------------------------------------------

SF2_THRESHOLD = (
    2048 * 1024
)  # [emu: Mednafen huc.cpp sf2_threshold] an image this big has the mapper
SF2_FIXED = 512 * 1024


class Sf2Card(RomCard):
    """Street Fighter II' Champion Edition (2.5 MiB) and the larger homebrew form.

    The first 512 KiB answer banks $00-$3F; banks $40-$7F show one of the further 512 KiB pages,
    chosen by a write to bank $00 at $1FF0-$1FFF (the page is the low bits of the address). MAME's
    `pce_sf2` decodes $1FF0-$1FF3 and four pages; Mednafen decodes $1FF0-$1FFF and masks by the
    page count: the same for the real card. [emu: both; no manufacturer document]
    (docs/cartridge.md)
    """

    def __init__(self, data: bytes) -> None:
        data = strip_copier_header(data)
        if len(data) < SF2_THRESHOLD:
            raise ValueError("an SF2 image is at least 2 MiB")
        pages = -(-(len(data) - SF2_FIXED) // SF2_FIXED)  # whole 512 KiB pages after the fixed part
        pages = 1 << (pages - 1).bit_length()  # a power of two, as Mednafen rounds the image up
        self.data = data + bytes(SF2_FIXED * (1 + pages) - len(data))
        self.page_mask = pages - 1
        self.page = 0

    def reset(self, kind: ResetKind) -> None:
        self.page = 0

    def read(self, address: int, mclk: int) -> int:
        offset = address & 0xFFFFF
        if offset < SF2_FIXED:
            return self.data[offset]
        return self.data[offset + self.page * SF2_FIXED]  # banks $40-$7F: the chosen page

    def write(self, address: int, value: int, mclk: int) -> None:
        if address & 0x1FFFF0 == 0x1FF0:  # bank $00, $1FF0-$1FFF
            self.page = (address & 0xF) & self.page_mask


class PopulousCard(RomCard):
    """Populous: 32 KiB of battery RAM in banks $40-$43 (four 8 KiB banks, not mirrored);
    the rest as a plain card. [emu: Mednafen: detected by "POPULOUS" at $1F26; MAME `pce_populous`
    at $80000-$87FFF.] Power-up contents are Mednafen's $FF (U7: arbitrary for a battery RAM)."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.ram = bytearray(b"\xff" * 0x8000)

    def read(self, address: int, mclk: int) -> int:
        if 0x40 <= (address >> 13) <= 0x43:
            return self.ram[address & 0x7FFF]
        return super().read(address, mclk)

    def write(self, address: int, value: int, mclk: int) -> None:
        if 0x40 <= (address >> 13) <= 0x43:
            self.ram[address & 0x7FFF] = value


class TennokoeCard(RomCard):
    """Tennokoe Bank: a 512 KiB HuCard with 8 KiB of backup RAM (four 2 KiB banks) at $80000-$81FFF
    of the card's space (banks $40, mirrored through the 64 KiB up to $8FFFF), locked at power-up
    (reads $FF, writes ignored); a write of a non-zero value anywhere in $F0000-$FFFFF unlocks it, a
    zero locks it. [emu: MAME `pce_tennokoe`, whose own comment calls the lock "a complete guess"
    (U29, tier 5); none in the library, so only unit-tested.]"""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.ram = bytearray(b"\xff" * 0x2000)
        self.locked = True

    def reset(self, kind: ResetKind) -> None:
        self.locked = True

    def read(self, address: int, mclk: int) -> int:
        bank = (address >> 13) & 0x7F
        if bank < 0x40:
            return super().read(address, mclk)
        if bank < 0x48:
            return 0xFF if self.locked else self.ram[address & 0x1FFF]
        return 0xFF  # nothing else is decoded above the ROM

    def write(self, address: int, value: int, mclk: int) -> None:
        offset = address & 0xFFFFF
        if 0x80000 <= offset < 0x90000:
            if not self.locked:
                self.ram[address & 0x1FFF] = value
        elif offset >= 0xF0000:
            self.locked = value == 0


def make_card(data: bytes) -> RomCard:
    """The card an image is: SF2 from 2 MiB up (Mednafen's threshold), Populous by its title string
    at $1F26, else a plain ROM. Tennokoe has no detection (no header): build it explicitly."""
    body = strip_copier_header(data)
    if len(body) >= SF2_THRESHOLD:
        return Sf2Card(data)
    if body[0x1F26 : 0x1F26 + 8] == b"POPULOUS":
        return PopulousCard(data)
    return RomCard(data)


def card_from_path(path: str | Path) -> RomCard:
    """`make_card` over a file read in place (BYOR: nothing is copied)."""
    return make_card(Path(path).read_bytes())
