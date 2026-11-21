"""Write a captured frame as a PNG for looking at (needs Pillow; not a judge).

    from frame_png import write_png
    write_png(board.capture.last_frame, "out.png", board.vce.rgb_table)

Rows have 1365 // divider dots (341, 455 or 682): the image is as wide as the widest row, shorter
rows are padded with the last colour. Compare pictures at the 9-bit values, never at RGB.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def write_png(frame, path: str | Path, rgb_table) -> None:
    width = max(len(row) for row in frame.rows)
    image = Image.new("RGB", (width, len(frame.rows)))
    pixels = image.load()
    for y, row in enumerate(frame.rows):
        for x in range(width):
            pixels[x, y] = rgb_table[row[min(x, len(row) - 1)]]
    image.save(path)
