#!/usr/bin/env python3
"""Record the PSG register writes a HuCard makes, with their master-clock times (M4).

    .venv-pypy/bin/python scripts/psg_record.py CARD.pce OUT.bin [--frames 600] [--tg16]

The board runs the card with the real core and a recorder in the PSG's place; each write to
`$0800-$0809` is stored as `<I B B` (master clock since power-on, register 0-9, value), 6 bytes.
`psg_compare.py` replays the file into the model and into the two referees. Cards are read in
place; the file holds only register writes (a few KB per second of music).
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

from pcengine_python import pads
from pcengine_python.board import Board
from pcengine_python.cards import RomCard
from pcengine_python.machine import PC_ENGINE, TURBOGRAFX_16
from pcengine_python.system import build


class Recorder:
    def __init__(self) -> None:
        self.records: list[tuple[int, int, int]] = []

    def write(self, offset: int, value: int, mclk: int) -> None:
        if offset < 10:
            self.records.append((mclk, offset, value))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("card", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--frames", type=int, default=600)
    p.add_argument("--tg16", action="store_true")
    a = p.parse_args()
    board = Board(
        TURBOGRAFX_16 if a.tg16 else PC_ENGINE, card=RomCard.from_path(a.card), pad=pads.Pad2()
    )
    recorder = Recorder()
    board.cpu_io._psg = recorder  # the recorder takes the PSG's place on the bus
    system = build(board)
    for _ in range(a.frames):
        system.run_frame()
    with a.out.open("wb") as f:
        for record in recorder.records:
            f.write(struct.pack("<IBB", *record))
    print(
        f"{a.card.name}: {len(recorder.records)} writes in {a.frames} frames ({board.mclk} clocks)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
