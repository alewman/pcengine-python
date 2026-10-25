#!/usr/bin/env python3
"""Measure what the PixelPath socket costs on the per-line path (M3's measurement).

    .venv-pypy/bin/python scripts/pixelpath_bench.py CARD.pce [--frames 20] [--repeats 6]

The same card runs for the same frames with (a) the default `DirectPath` called once a line through
`Capture.finish_line` (the socket, as built) and (b) the same code with that call removed (the
row goes straight to the colour lookup). The two variants alternate so drift in the machine hits
both; per-variant wall time of the whole run (CPU core included: what matters is the share) is
reported with its spread, and the number of mix calls per frame.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

from pcengine_python import pads
from pcengine_python.board import Board
from pcengine_python.cards import RomCard
from pcengine_python.machine import PC_ENGINE, TURBOGRAFX_16
from pcengine_python.sockets import DirectPath
from pcengine_python.system import build


def run(card: Path, frames: int, tg16: bool, bypass: bool) -> float:
    board = Board(
        TURBOGRAFX_16 if tg16 else PC_ENGINE, card=RomCard.from_path(card), pad=pads.Pad2()
    )
    if bypass:
        board.capture.path = None
    system = build(board)
    began = time.perf_counter()
    for _ in range(frames):
        system.run_frame()
    return time.perf_counter() - began


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("card", type=Path)
    p.add_argument("--frames", type=int, default=20)
    p.add_argument("--repeats", type=int, default=6)
    p.add_argument("--tg16", action="store_true")
    a = p.parse_args()
    results = {"socket": [], "direct": []}
    run(a.card, 4, a.tg16, False)  # warm up the JIT
    for _ in range(a.repeats):
        for name in ("socket", "direct"):
            results[name].append(run(a.card, a.frames, a.tg16, name == "direct"))
    for name, times in results.items():
        print(
            f"{name:7s} {statistics.mean(times):7.3f} s for {a.frames} frames "
            f"(sd {statistics.stdev(times):.3f}, min {min(times):.3f})"
        )
    cost = statistics.mean(results["socket"]) / statistics.mean(results["direct"]) - 1
    noise = statistics.stdev(results["socket"]) / statistics.mean(results["socket"])
    print(f"socket / direct - 1 = {cost:+.4f}; run-to-run noise (sd/mean) {noise:.4f}")
    print("one mix call per line: 262 or 263 a frame")
    # the socket in isolation: one `mix` call per line against taking the row directly
    path, rows, timing = DirectPath(), [[0] * 341], None
    n = 1_000_000
    began = time.perf_counter()
    for _ in range(n):
        path.mix(timing, rows)
    call = (time.perf_counter() - began) / n
    began = time.perf_counter()
    for _ in range(n):
        rows[0]
    base = (time.perf_counter() - began) / n
    per_frame = 263 * (call - base)
    frame_time = min(results["direct"]) / a.frames
    print(
        f"the call alone: {1e9 * (call - base):.0f} ns a line, {1e6 * per_frame:.1f} us a frame = "
        f"{per_frame / frame_time:.2e} of a frame ({1e3 * frame_time:.0f} ms)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
