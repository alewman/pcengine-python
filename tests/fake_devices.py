"""Test-only fakes for the sockets (docs/sockets.md): the Protocols are exercised without any
add-on, and without a CPU core.

`ScriptedCpu` stands in for huc6280-python's bus behaviour: it makes the same one-callback-per-
cycle calls (`read_byte`, `write_byte`, `idle`) with a `high_speed` flag and an IRQ-line sink, so
the board's pricing and device timing are tested before the core exists.
"""

from __future__ import annotations

from pcengine_python.sockets import BoardPins, ResetKind


class FakeCard:
    """A card claiming arbitrary page ranges; every access is recorded."""

    grounds_cd = True

    def __init__(self, ranges: list[tuple[int, int]], fill: int = 0xAA) -> None:
        self._ranges = ranges
        self.fill = fill
        self.reads: list[tuple[int, int]] = []
        self.writes: list[tuple[int, int, int]] = []
        self.resets: list[ResetKind] = []
        self.pins: BoardPins | None = None

    def bind(self, pins: BoardPins) -> None:
        self.pins = pins

    def claims(self) -> list[tuple[int, int]]:
        return self._ranges

    def read(self, address: int, mclk: int) -> int:
        self.reads.append((address, mclk))
        return self.fill

    def write(self, address: int, value: int, mclk: int) -> None:
        self.writes.append((address, value, mclk))

    def reset(self, kind: ResetKind) -> None:
        self.resets.append(kind)


class FakePort(FakeCard):
    """An expansion-port device: grounds nothing, but its presence pulls the I/O port's D7 low
    and it can hold IRQ2."""

    grounds_cd = False

    def __init__(self, ranges: list[tuple[int, int]], fill: int = 0xCC) -> None:
        super().__init__(ranges, fill)
        self.present = True
        self.caught_up: list[int] = []

    def catch_up(self, mclk: int) -> None:
        self.caught_up.append(mclk)

    def set_irq2(self, level: bool) -> None:
        assert self.pins is not None
        self.pins.irq2.set("fake-port", level)


class FakeAudioSource:
    rate_hz = 44100.0
    gain = 0.5

    def take_samples(self, mclk: int):
        return [(1, -1)]


class FakeController:
    """Records SEL/CLR and answers a fixed nibble."""

    def __init__(self, nibble: int = 0x05) -> None:
        self.nibble = nibble
        self.writes: list[tuple[bool, bool]] = []

    def write(self, sel: bool, clr: bool) -> None:
        self.writes.append((sel, clr))

    def read(self, sel: bool, clr: bool) -> int:
        return self.nibble


class FakePixelPath:
    """Replaces 'VDC 1 straight into the VCE' by mixing two rows: the second wins where its
    pixel is non-zero (a stand-in for the SuperGrafx's VPC)."""

    def __init__(self) -> None:
        self.lines_seen = 0

    def mix(self, timing, rows):
        self.lines_seen += 1
        if len(rows) == 1:
            return rows[0]
        return [b if b else a for a, b in zip(rows[0], rows[1], strict=True)]


class ScriptedCpu:
    """Drives a board's bus the way the core will: one callback per CPU cycle."""

    def __init__(self, board, *, high_speed: bool = False) -> None:
        self.board = board
        self.high_speed = high_speed
        self.irq_disable = 0
        self.lines = (False, False, False)
        self.line_log: list[tuple[int, tuple[bool, bool, bool]]] = []
        board.attach_cpu(self)

    def set_irq_lines(self, irq1: bool, irq2: bool, tiq: bool) -> None:
        self.lines = (irq1, irq2, tiq)
        self.line_log.append((self.board.mclk, self.lines))

    def read(self, address: int) -> int:
        return self.board.read_byte(address)

    def write(self, address: int, value: int) -> None:
        self.board.write_byte(address, value)

    def idle(self, cycles: int = 1) -> None:
        for _ in range(cycles):
            self.board.idle(None)
