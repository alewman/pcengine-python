"""The sockets: narrow Protocols an add-on board implements to plug into this one.

Designed after the Sega console pattern (docs/sockets.md): `pcenginecd-python` and
`supergrafx-python` pin this board by git revision and never copy from it. Every Protocol is
small enough to transcribe to a Rust trait. Test-only fakes for each live in
`tests/fake_devices.py`; the base board implements only what it uses.

Numbering follows docs/sockets.md.

 1. CardSlot / Card        the HuCard slot
 2. PortDevice             the expansion port (EXT BUS)
 3. PageHandler            one decode for every bus master (the page table is in pagetable.py)
 4. BoardPins.hold         bus timing: wait states go through the board
 5. Clocked                clock domains: catch_up(mclk) callable inside an access
 6. IrqLine                interrupt levels, one bit per source, wired-OR
 7. PixelPath              per-line 9-bit pixels between the VDC(s) and the VCE
 8. VideoTiming            one record per line
 9. AudioSource            a source with a changeable rate and gain
10. ResetKind              reset events
11. ControllerPort         the pad port
12. Instances              `Vdc`, `Vce`, `Psg` hold no module state (tests/test_sockets.py)
"""

from __future__ import annotations

import enum
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# --- 10. Reset -------------------------------------------------------------------------------


class ResetKind(enum.Enum):
    """The PC Engine has no reset button or reset instruction on the console itself; a
    CD unit is reset by a register write inside the add-on (docs/sockets.md). BUTTON exists for
    the Duo/Shuttle-class consoles (unverified)."""

    POWER_ON = "power_on"
    BUTTON = "button"


# --- 6. Interrupts ---------------------------------------------------------------------------


class IrqLine:
    """A wired-OR level with one bit per source (never a max).

    The line is high while any source holds it; a source lowers its own bit when acknowledged.
    """

    def __init__(self, name: str = "") -> None:
        self.name = name
        self._sources: set[str] = set()

    def set(self, source: str, level: bool) -> None:
        if level:
            self._sources.add(source)
        else:
            self._sources.discard(source)

    @property
    def level(self) -> bool:
        return bool(self._sources)

    @property
    def sources(self) -> frozenset[str]:
        return frozenset(self._sources)


# --- 3 and 4. The decode and bus timing, seen from a device ------------------------------------


@runtime_checkable
class PageHandler(Protocol):
    """Anything a range of 256-byte pages can be claimed by.

    `address` is the 21-bit physical address after the MMU; `mclk` is the master-clock time of
    the access, so a device may run itself up to it inside the access (the CD unit's registers
    need that).
    """

    def read(self, address: int, mclk: int) -> int: ...

    def write(self, address: int, value: int, mclk: int) -> None: ...


@dataclass
class BoardPins:
    """What the board hands a card or port device when it is plugged in."""

    # The shared IRQ2 level (HuCard, expansion port, CD ADPCM): the device sets its own bit.
    irq2: IrqLine
    # Stretch the current CPU cycle by this many master clocks (RDY held low), applied by the
    # board once the access returns.
    hold: Callable[[int], None]


# --- 5. Clock domains ------------------------------------------------------------------------


@runtime_checkable
class Clocked(Protocol):
    """A device with its own clock domain keeps its own rational ratio and remainder and runs up
    to `mclk` when asked, including from inside a bus access."""

    def catch_up(self, mclk: int) -> None: ...


# --- 1. The HuCard slot ----------------------------------------------------------------------


class Card(PageHandler, Protocol):
    """A HuCard: standard ROM, SF2, Populous, Tennokoe, a System Card, ...

    A card is not confined to the ROM window (a Super System Card claims banks $68-$7F as RAM
    and the $18C1-$18C6 id registers), and a claim replaces the page's handler.
    """

    # The /CD line: a card grounds it so a CD unit can tell one is inserted.
    # [doc: wiki HuCard pinout]
    grounds_cd: bool

    def claims(self) -> list[tuple[int, int]]:
        """Inclusive (first_page, last_page) ranges over the 8192 pages of 256 bytes."""
        ...

    def reset(self, kind: ResetKind) -> None: ...


class CardSlot:
    """The slot. Empty is a real state: it answers $FF, does not ground /CD, and the I/O
    port's CD-sense bit follows the expansion port, not the slot (docs/sockets.md)."""

    def __init__(self, card: Card | None = None) -> None:
        self.card = card

    @property
    def grounds_cd(self) -> bool:
        return self.card is not None and self.card.grounds_cd


# --- 2. The expansion port -------------------------------------------------------------------


class PortDevice(PageHandler, Protocol):
    """The EXT BUS device: A0-A20, D0-D7, /RD, /WR, IRQ2, audio in, K7 (I/O port bit 7).

    The video-bus pins (VD0-8, HSYNC, VSYNC, DCK, VCESEL) are not a socket until a device that
    uses them is found (U13).
    """

    # K7: a device on the port pulls the I/O port's D7 low ("CD unit attached", C6 polarity).
    present: bool

    def claims(self) -> list[tuple[int, int]]: ...

    def catch_up(self, mclk: int) -> None: ...

    def reset(self, kind: ResetKind) -> None: ...


# --- 7 and 8. Pixels and per-line timing -----------------------------------------------------


@dataclass(frozen=True)
class VideoTiming:
    """One record per line, handed to anything that mixes or captures video."""

    frame: int  # frame counter since power-on
    line: int  # line index within the frame, 0 = first line after the vertical sync
    start_mclk: int  # master-clock time of the line's start (the VCE's hsync)
    dot_divider: int  # master clocks per dot: 4, 3 or 2 (VCE dot clock at the line's start)
    frame_lines: int  # 262 or 263
    in_vsync: bool


class PixelPath(Protocol):
    """Where the VDC(s) meet the VCE. The default is VDC 1 straight into the VCE; the
    SuperGrafx's VPC replaces it, mixing two VDC lines. Line granularity, not dot.

    Each row is the VDC's 9-bit pixel values for one line: bit 8 sprite/background, bits 7-4
    palette, bits 3-0 colour [hw: sgxtech], with palette index 0x000/0x100 for the
    backdrop/overscan colour. Returns the row handed to the VCE.
    """

    def mix(self, timing: VideoTiming, rows: Sequence[Sequence[int]]) -> Sequence[int]: ...


class DirectPath:
    """VDC 1 straight into the VCE."""

    def mix(self, timing: VideoTiming, rows: Sequence[Sequence[int]]) -> Sequence[int]:
        return rows[0]


# --- 9. Audio --------------------------------------------------------------------------------


class AudioSource(Protocol):
    """A mixer input with a changeable rate and gain. The PSG is board-owned and in the list
    from the start; the CD adds CD-DA (44.1 kHz) and ADPCM (variable)."""

    rate_hz: float
    gain: float

    def take_samples(self, mclk: int) -> Sequence[tuple[int, int]]:
        """Stereo samples produced up to `mclk` since the last call."""
        ...


# --- 11. Controllers -------------------------------------------------------------------------


class ControllerPort(Protocol):
    """What plugs into the pad port: a 2-button pad, a multitap, a 6-button pad, a mouse.

    SEL and CLR are the two lines the console drives ($1000 D0 and D1); the device answers a
    4-bit nibble on D3-D0. The SuperGrafx S-EXP port shares the nibble through a mux and exposes
    output bits 2-7 (add-on)."""

    def write(self, sel: bool, clr: bool) -> None: ...

    def read(self, sel: bool, clr: bool) -> int: ...
