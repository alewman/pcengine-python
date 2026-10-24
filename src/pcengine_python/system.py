"""The machine as a whole: a board, a CPU on it, and frame-by-frame running.

The CPU is any object with the huc6280-python bus contract: it is built with the board's
`read_byte`, `write_byte` and `idle`, exposes `high_speed`, `set_irq_lines` and `irq_disable`,
and one `step()` runs one instruction, one interrupt entry or one whole block transfer. The
board prices every cycle inside its callbacks, so `step()`'s return value is never added to
the clock.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from pcengine_python.board import Board


class Cpu(Protocol):
    high_speed: bool
    irq_disable: int

    def step(self) -> int: ...

    def set_irq_lines(self, irq1: bool, irq2: bool, tiq: bool) -> None: ...


class System:
    def __init__(self, board: Board, make_cpu: Callable[[Board], Cpu]) -> None:
        self.board = board
        self.cpu = make_cpu(board)
        board.attach_cpu(self.cpu)

    @property
    def frame(self) -> int:
        return self.board.timeline.frame

    def step(self) -> None:
        self.cpu.step()

    def run_frame(self) -> None:
        """Run until the VCE starts the next frame."""
        start = self.frame
        while self.frame == start:
            self.cpu.step()

    def run_until(self, mclk: int) -> None:
        """Run whole instructions until the master clock has reached `mclk`."""
        while self.board.mclk < mclk:
            self.cpu.step()


def make_core(board: Board) -> Cpu:
    """The HuC6280 core (huc6280-python, pinned in pyproject) on this board's bus, with a reset
    requested: the first `step()` runs the start sequence and reads the reset vector."""
    from huc6280 import HuC6280

    cpu = HuC6280(board.read_byte, board.write_byte, board.idle)
    cpu.request_reset()
    return cpu  # type: ignore[return-value]


def build(board: Board) -> System:
    """A board with the real core on it."""
    return System(board, make_core)
