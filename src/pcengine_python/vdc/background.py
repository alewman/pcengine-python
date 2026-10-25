"""The background layer: one line of 9-bit pixels from the BAT and the character generator.

[hw: pcetech 5.2; mfr: Hudson HuC6270 manual] Tiles are 8x8, 4 bits per pixel, planar: 16 words
per tile, word `y` holds bitplanes 0 (low byte) and 1 (high byte) of line `y`, word `y + 8`
bitplanes 2 and 3. The BAT starts at VRAM word 0, one word per tile `ppppnnnnnnnnnnnn`: palette
and name, no flips and no priority. Only names 0-2047 exist in 64 KiB of VRAM; the rest read as
0 here (U23).

The line is drawn in one go when the display width begins, from the scroll registers latched a few
dots earlier, as Mednafen does (tier 5, U3); a VRAM change during the line shows on the next one.
"""

from __future__ import annotations

# The planes of one byte as 8 bits, leftmost pixel first.
_BITS = tuple(tuple((b >> (7 - x)) & 1 for x in range(8)) for b in range(256))

BAT_WIDTHS = (32, 64, 128, 128)  # MWR D5-D4 [hw: pcetech 5.1 $09]
BAT_SHIFTS = (5, 6, 7, 7)
BAT_HEIGHTS = (32, 64)  # MWR D6

_cache_limit = 1 << 16


def _decode(w0: int, w1: int, mask: int) -> tuple[int, ...]:
    p0, p1 = _BITS[w0 & 0xFF], _BITS[w0 >> 8]
    p2, p3 = _BITS[w1 & 0xFF], _BITS[w1 >> 8]
    return tuple((p0[x] | p1[x] << 1 | p2[x] << 2 | p3[x] << 3) & mask for x in range(8))


class Background:
    """Per-instance decode cache (no module state: a second VDC is a second instance)."""

    def __init__(self) -> None:
        self._cache: dict[tuple[int, int, int], tuple[int, ...]] = {}

    def _pixels(self, w0: int, w1: int, mask: int) -> tuple[int, ...]:
        key = (w0, w1, mask)
        try:
            return self._cache[key]
        except KeyError:
            if len(self._cache) >= _cache_limit:
                self._cache.clear()
            self._cache[key] = value = _decode(w0, w1, mask)
            return value

    def row(self, vram, size: int, mwr: int, x_offset: int, y_offset: int, width: int) -> list[int]:
        """`width` pixels, each `palette << 4 | colour`; colour 0 is transparent."""
        bat_mask = BAT_WIDTHS[(mwr >> 4) & 3] - 1
        bat_row = ((y_offset >> 3) & (BAT_HEIGHTS[(mwr >> 6) & 1] - 1)) << BAT_SHIFTS[
            (mwr >> 4) & 3
        ]
        line = y_offset & 7
        # [hw: pcetech 5.2] MWR D1-D0 = 3 is the one-bitplane-pair mode: D7 picks planes 0/1 or
        # 2/3 and the other pair reads as zero.
        mask = 0x0F
        if mwr & 3 == 3:
            mask = 0x0C if mwr & 0x80 else 0x03
        out: list[int] = []
        skip = x_offset & 7
        column = (x_offset >> 3) & bat_mask
        while len(out) < width:
            bat = vram[bat_row | column]
            base = (bat & 0xFFF) * 16 + line
            w0 = vram[base] if base < size else 0
            w1 = vram[base + 8] if base + 8 < size else 0
            palette = (bat >> 8) & 0xF0
            pixels = self._pixels(w0, w1, mask)
            if skip:
                out.extend(palette | p for p in pixels[skip:])
                skip = 0
            else:
                out.extend(palette | p for p in pixels)
            column = (column + 1) & bat_mask
        del out[width:]
        return out
