"""Measure where the raster split starts in Covell's hardware photographs (tier 1).

    python scripts/covell_photo_splits.py            # needs Pillow; reads tests/test_roms/CPU_Test

For each of images/8MROM_2..8.png (a real PC Engine, ROM mode, one instruction group each) the
column of the strongest step per scanline of the striped area is found; the median is converted
to Mednafen-screenshot columns by registering the photograph to Mednafen's screenshot on its
text (see tests/covell_hardware_splits.json). The result is a measurement with about +-1.5 px of
photographic error, not a number from a logic analyser.
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

from PIL import Image

IMAGES = Path(__file__).resolve().parent.parent / "tests" / "test_roms" / "CPU_Test" / "images"


def row_splits(path: Path, y0=62, y1=176, x0=28, x1=62, threshold=150):
    px = Image.open(path).convert("RGB").load()
    found = []
    for y in range(y0, y1):
        best = (0.0, None)
        for x in range(x0, x1):
            d = sum(
                abs(
                    sum(px[x - k, y][c] for k in range(1, 4)) / 3
                    - sum(px[x + k, y][c] for k in range(1, 4)) / 3
                )
                for c in range(3)
            )
            best = max(best, (d, x), key=lambda t: t[0])
        if best[0] > threshold:
            found.append(best[1])
    return found


def to_mednafen(x: float) -> float:
    return 20 + (x - 24.7) / 1.255


def main() -> int:
    for cycles in range(2, 9):
        rows = row_splits(IMAGES / f"8MROM_{cycles}.png")
        median = statistics.median(rows)
        print(
            f"{cycles}-cycle group: {len(rows)} rows, median x {median}, x_m {to_mednafen(median):.1f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
