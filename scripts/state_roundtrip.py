#!/usr/bin/env python3
"""Save states, proven complete: a run saved and loaded continues as the run that wasn't.

    .venv-pypy/bin/python scripts/state_roundtrip.py CARD.pce... [--tg16] [--at 120] [--to 180]
        [--extra 777] [--press BUTTONS@FRAME+HOLD ...]

For each card: power on, run to frame `--at` plus `--extra` instructions (so the save falls
anywhere in a frame, between two instructions), save, then build a second system the same way,
load the state into it, and run both to frame `--to`. Every frame after the save must be the same
on both: every CPU bus cycle (address, value, direction, master clock), the picture, the mixed
audio and the CPU's state. A third run loads the state into a system that has run elsewhere first
(to frame `--at` / 2), to show loading overwrites everything rather than relying on a fresh
system's values; and the loaded system, saved at once, must give the same bytes back.

`roundtrip()` is the check itself, for the tests and for the add-ons' own scripts: it takes a
function that builds one more machine and returns its board, the function that puts the CPU on
it, and the pad.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from array import array
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import presses as press_script

from pcengine_python.state import load_state, save_state

Machine = tuple[Any, Callable[[], Any], Any]  # board, build() -> System, pad (or None)


def observe(board: Any) -> array:
    """Log every CPU bus cycle of `board`: wraps its three bus callables before the CPU is
    built on them (instance attributes that are callables: wiring, so not part of a state)."""
    log = array("Q")
    append = log.append
    read, write, idle = board.read_byte, board.write_byte, board.idle

    def read_byte(address: int) -> int:
        value = read(address)
        append(address << 8 | value)
        append(board.mclk << 2)
        return value

    def write_byte(address: int, value: int) -> None:
        write(address, value)
        append(address << 8 | value)
        append(board.mclk << 2 | 1)

    def idle_cycle(*args: Any) -> Any:
        out = idle(*args)
        append(board.mclk << 2 | 2)
        return out

    board.read_byte, board.write_byte, board.idle = read_byte, write_byte, idle_cycle
    return log


def digest(system: Any, log: array) -> str:
    board = system.board
    out = hashlib.sha1(log.tobytes())
    del log[:]
    frame = board.capture.last_frame
    if frame is not None:
        for row in frame.rows:
            out.update(struct.pack(f"<{len(row)}H", *row))
        out.update(bytes(frame.dividers))
    for left, right in board.take_audio():
        out.update(struct.pack("<hh", left, right))
    out.update(repr(system.cpu.capture_state()).encode())
    out.update(struct.pack("<q", board.mclk))
    return out.hexdigest()


def run(system: Any, pad: Any, log: array, frames: int, presses: list) -> list[str]:
    out = []
    for _ in range(frames):
        if pad is not None:
            pad.pressed = press_script.board_mask(press_script.held(presses, system.frame))
        system.run_frame()
        out.append(digest(system, log))
    return out


def roundtrip(
    make: Callable[[], Machine], at: int, to: int, extra: int = 777, presses: list | None = None
) -> tuple[bool, str]:
    """(passed, what happened). `make()` builds one more machine, the same way each time."""
    presses = presses or []

    def start() -> tuple[Any, Any, array]:
        board, build, pad = make()
        log = observe(board)
        return build(), pad, log

    first, pad, log = start()
    run(first, pad, log, at, presses)
    for _ in range(extra):
        first.step()
    state = save_state(first)
    del log[:]
    first.board.take_audio()
    expected = run(first, pad, log, to - at, presses)

    for label, warm in (("a fresh system", 0), ("a system that had run", max(1, at // 2))):
        second, pad2, log2 = start()
        run(second, pad2, log2, warm, presses)
        load_state(second, state)
        if save_state(second) != state:
            return False, f"{label}: saved again at once, the state is not the same bytes"
        del log2[:]
        second.board.take_audio()
        got = run(second, pad2, log2, to - at, presses)
        for n, (a, b) in enumerate(zip(expected, got, strict=True)):
            if a != b:
                return False, f"{label}: differs in frame {n + 1} after the save"
    return True, f"{len(state):,} bytes; {to - at} frames after the save equal, twice"


def main() -> int:
    from pcengine_python import pads
    from pcengine_python.board import Board
    from pcengine_python.cards import card_from_path
    from pcengine_python.machine import PC_ENGINE, TURBOGRAFX_16
    from pcengine_python.system import build

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cards", type=Path, nargs="+")
    p.add_argument("--tg16", action="store_true")
    p.add_argument("--at", type=int, default=120)
    p.add_argument("--to", type=int, default=180)
    p.add_argument("--extra", type=int, default=777, help="instructions past frame --at")
    p.add_argument("--press", action="append", default=[], metavar="BUTTONS@FRAME+HOLD")
    a = p.parse_args()
    machine = TURBOGRAFX_16 if a.tg16 else PC_ENGINE
    failed = 0
    for card in a.cards:

        def make(card: Path = card) -> Machine:
            pad = pads.Pad2()
            board = Board(machine, card=card_from_path(card), pad=pad)
            return board, lambda: build(board), pad

        ok, what = roundtrip(make, a.at, a.to, a.extra, press_script.parse(a.press))
        print(f"{'ok  ' if ok else 'FAIL'} {card.name}: {what}", flush=True)
        failed += not ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
