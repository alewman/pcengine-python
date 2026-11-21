#!/usr/bin/env python3
"""Run a HuCard on this board (with the real core) for N frames and save the frame as 9-bit rows.

    .venv-pypy/bin/python scripts/m2_ours.py CARD.pce OUT.pkl [--frames 300] [--tg16]

The picture is `board.capture.last_frame` after the N-th frame: 242 rows (frame lines 14-255) of
9-bit palette values, one per dot from the end of the line's horizontal sync. Run it under PyPy
(CPython is about 8 times slower). `--tg16` selects the TurboGrafx-16 row of the machine table
(US games check the country bit). The cards are read in place.
"""

from __future__ import annotations

import argparse
import pickle
import sys
import time
from pathlib import Path

from pcengine_python import pads
from pcengine_python.board import Board
from pcengine_python.cards import card_from_path
from pcengine_python.machine import PC_ENGINE, TURBOGRAFX_16
from pcengine_python.system import build

sys.path.insert(0, str(Path(__file__).resolve().parent))
import presses as press_script


def dropping_core():
    """HuC6280 that does not take an interrupt whose every source has gone by the boundary.

    An experiment for core issue 0002: the core polls the request one cycle before the
    instruction ends, and a `STZ $1403` that acknowledges the timer in its last cycle leaves the
    interrupt taken with nothing asserted, which the core sends to the IRQ2 vector (After Burner
    II then executes garbage). Mesen2 re-checks the timer source live and does not take it."""
    from huc6280 import HuC6280

    class Dropping(HuC6280):
        def _boundary_interrupt(self) -> int:
            taken = super()._boundary_interrupt()
            if taken == 1 and not (self._lines & ~self._irq_disable & 7):  # IRQ_LINE
                return 0
            return taken

    return Dropping


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("card", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--frames", type=int, default=300)
    p.add_argument("--tg16", action="store_true")
    p.add_argument(
        "--then", type=int, default=0, help="keep running to this frame, save OUT-<n>.pkl"
    )
    p.add_argument("--drop-vanished-irq", action="store_true", help="core issue 0002 experiment")
    p.add_argument(
        "--press",
        action="append",
        default=[],
        metavar="BUTTONS@FRAME+HOLD",
        help="pad 1 input (scripts/presses.py)",
    )
    a = p.parse_args()
    machine = TURBOGRAFX_16 if a.tg16 else PC_ENGINE
    pad = pads.Pad2()
    presses = press_script.parse(a.press)
    board = Board(machine, card=card_from_path(a.card), pad=pad)
    system = build(board, dropping_core() if a.drop_vanished_irq else None)
    began = time.monotonic()
    marks = [(a.frames, a.out)]
    if a.then > a.frames:
        marks.append((a.then, a.out.with_name(f"{a.out.stem}-{a.then}{a.out.suffix}")))
    done = 0
    for target, out in marks:
        for n in range(done, target):
            pad.pressed = press_script.board_mask(press_script.held(presses, n))
            system.run_frame()
        done = target
        frame = board.capture.last_frame
        with out.open("wb") as f:
            pickle.dump(
                {"rows": frame.rows, "dividers": frame.dividers, "number": board.timeline.frame}, f
            )
        print(
            f"{a.card.name}: {target} frames in {time.monotonic() - began:.1f} s, "
            f"{len(frame.rows)} rows of {len(frame.rows[0])} dots, VCE control {board.vce.control:#04x}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
