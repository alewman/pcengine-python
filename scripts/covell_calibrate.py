#!/usr/bin/env python3
"""Place the split of Covell's CPU test on the board's raster and against the hardware photographs.

    python scripts/covell_calibrate.py [--vblank-dots N ...] [--mode ram|rom]   # needs Pillow

M2's background layer draws the test's own text, which M1 could not: the heading's left edge and
the HuCard icon's right edge are the same two features in our picture and in each photograph, so
the photograph's columns convert to our dots with a scale (photo px per dot) and an offset taken
from them, no emulator in between. For each group of 2-8 cycle instructions the split's column in
our picture (median over the striped rows) is printed with the photograph's converted column
(8M_<n>.png is a real PC Engine running from RAM, 8MROM_<n>.png from ROM) and their difference.
Photographic precision is about +-1.2 dots. Takes about 40 s a vblank position.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

from PIL import Image

from pcengine_python import pads
from pcengine_python.board import Board
from pcengine_python.cards import card_from_path
from pcengine_python.system import build

ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "tests/test_roms/CPU_Test/CPU_Test_10.pce"
IMAGES = ROOT / "tests/test_roms/CPU_Test/images"
WHITE = 0x1FF


def photo_anchor(path: Path) -> tuple[int, int]:
    """Left edge of the heading and right edge of the icon, in photograph columns."""
    image = Image.open(path).convert("RGB")
    px, (w, _) = image.load(), image.size
    k = w / 355  # the 2-cycle RAM photograph is twice the size of the others
    xs = [x for y in range(int(8 * k), int(14 * k)) for x in range(w) if min(px[x, y]) > 190]
    return min(xs) / k, max(xs) / k


def photo_split(path: Path) -> float:
    image = Image.open(path).convert("RGB")
    px, (w, _) = image.load(), image.size
    k = w / 355
    found = []
    for y in range(int(62 * k), int(176 * k)):
        best = (0.0, 0)
        for x in range(int(28 * k), int(62 * k)):
            d = sum(
                abs(
                    sum(px[x - k, y][c] for k in range(1, 4)) / 3
                    - sum(px[x + k, y][c] for k in range(1, 4)) / 3
                )
                for c in range(3)
            )
            best = max(best, (d, x))
        if best[0] > 150:
            found.append(best[1])
    return statistics.median(found) / k


def our_anchor(frame) -> tuple[int, int]:
    xs = [x for y in range(5, 14) for x, v in enumerate(frame.rows[y]) if v == WHITE]
    return min(xs), max(xs)


def our_split(frame) -> float:
    found = []
    for row in frame.rows[60:175]:
        changes = [x for x in range(40, 160) if row[x] != row[x - 1]]
        if changes:
            found.append(changes[0])
    return statistics.median(found)


def run(vblank_dots: int, mode: str) -> None:
    pad = pads.Pad2()
    system = build(Board(card=card_from_path(ROM), pad=pad, vblank_dots=vblank_dots))
    frames = lambda n: [system.run_frame() for _ in range(n)]  # noqa: E731

    def tap(mask: int) -> None:
        pad.pressed = mask
        frames(3)
        pad.pressed = 0
        frames(10)

    frames(30)
    if mode == "rom":
        tap(pads.SELECT)
    prefix = "8MROM" if mode == "rom" else "8M"
    print(
        f"vblank {vblank_dots:+d} dots, {mode.upper()} mode: ours, photograph (in our dots), ours - hw"
    )
    for group in range(2, 9):
        if group > 2:
            tap(pads.RIGHT)
        name = "8M_2L.png" if (group == 2 and mode == "ram") else f"{prefix}_{group}.png"
        path = IMAGES / name
        if not path.exists():
            continue
        left, right = photo_anchor(path)
        ours_left, ours_right = our_anchor(system.board.capture.last_frame)
        scale = (right - left) / (ours_right - ours_left)  # photograph px per dot
        hw = ours_left + (photo_split(path) - left) / scale
        ours = our_split(system.board.capture.last_frame)
        print(f"  {group}-cycle: {ours:6.1f} {hw:6.1f} {ours - hw:+6.1f}   (scale {scale:.3f})")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vblank-dots", type=int, nargs="+", default=[0, -8])
    p.add_argument("--mode", choices=("ram", "rom"), default="ram")
    a = p.parse_args()
    for dots in a.vblank_dots:
        run(dots, a.mode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
