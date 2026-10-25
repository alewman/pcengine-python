"""Sprites: the line scan of the sprite attribute table, and the drawing of the line's sprites.

[hw: pcetech 5.3; mfr: Hudson HuC6270 manual] The 64-entry table (SAT, filled only by the VRAM ->
SAT DMA) holds, per sprite: Y (10 bits, the first visible line is 64), X (10 bits, 32 is the
display's left edge), pattern (bits 10-1; bit 0 is the CG bit), and flags: palette (3-0), priority
(7), width 16/32 (8), flip X (11), height 16/32/64 (13-12), flip Y (15). A pattern is 16 x 16
pixels = 64 words, four planes of 16 words. Larger sprites use neighbouring patterns: width 32
clears pattern bit 0, height 32 clears bit 1, height 64 clears bits 2 and 1; flips act on the whole
sprite.

Per line the scan finds the sprites that cover the *next* line, in table order, up to 16 pattern
entries (a 32-wide sprite is two entries); a 17th needed entry sets the overflow flag and ends the
scan. The first opaque pixel in buffer order wins; a pixel is in front of the background if its
priority bit is set or the background pixel is transparent; sprite 0 colliding with another
sprite's opaque pixel sets the collision flag. When MWR's sprite access width is 1 the pattern
is two bitplanes, picked by the CG bit (SP0/SP1 or SP2/SP3).

Provisional (U3, tier 5): that the scan reads the pattern words when it finds the sprite (the
line before it is drawn), as Mednafen does; the narrow-display budget below is Mesen2's.
"""

from __future__ import annotations

from dataclasses import dataclass

HEIGHTS = (16, 32, 64, 64)
HEIGHT_MASKS = (~0, ~2, ~6, ~6)
CLOCKS_PER_SPRITE = (4, 4, 8, 16)  # [mfr: SM table; emu: Mesen2] dots of fetch time per entry

SPRITE_LIMIT = 16


@dataclass(slots=True)
class Entry:
    x: int  # left pixel, in display columns (may be negative or past the width)
    palette: int  # palette << 4
    priority: bool
    hflip: bool
    sprite0: bool
    planes: tuple[int, int, int, int]


def scan(vram, size: int, sat, line: int, mwr: int, *, limit: int = SPRITE_LIMIT):
    """The entries of sprites covering `line` (counted from the first display line), and whether
    a 17th entry was needed (overflow)."""
    entries: list[Entry] = []
    overflow = False
    cg_two_planes = ((mwr >> 2) & 3) == 1
    for i in range(64):
        w0, w1, w2, w3 = sat[4 * i], sat[4 * i + 1], sat[4 * i + 2], sat[4 * i + 3]
        y = (w0 & 0x3FF) - 64
        shape = (w3 >> 12) & 3
        height = HEIGHTS[shape]
        if not y <= line < y + height:
            continue
        wide = bool(w3 & 0x100)
        hflip = bool(w3 & 0x800)
        row = line - y
        if w3 & 0x8000:
            row = height - 1 - row
        pattern = ((w2 >> 1) & 0x3FF) & HEIGHT_MASKS[shape]
        pattern |= (row & 0x30) >> 3
        if wide:
            pattern &= ~1
        base_x = (w1 & 0x3FF) - 32
        for half in range(2 if wide else 1):
            if len(entries) == SPRITE_LIMIT:
                overflow = True  # [mfr] "17 or more": the rest of the scan is dropped
                return entries[:limit], overflow
            cell = pattern | ((half ^ hflip) if wide else 0)
            address = cell * 64 + (row & 15)
            if address + 48 >= size:  # [emu: Mesen2] an empty sprite past the VRAM; U23
                planes = (0, 0, 0, 0)
            elif cg_two_planes:
                shift = 32 if w2 & 1 else 0
                planes = (vram[address + shift], vram[address + shift + 16], 0, 0)
            else:
                planes = (vram[address], vram[address + 16], vram[address + 32], vram[address + 48])
            entries.append(
                Entry(base_x + 16 * half, (w3 & 0xF) << 4, bool(w3 & 0x80), hflip, i == 0, planes)
            )
    return entries[:limit], overflow


def draw(entries, width: int, row: list[int], first: int, enabled: bool = True):
    """Draw the entries over `row` (the line's 9-bit pixels; the display starts at index `first`).

    Returns the display column of the first pixel where sprite 0 hit another sprite, or None."""
    buffer = [0] * width
    hit = None
    for entry in reversed(entries):
        p0, p1, p2, p3 = entry.planes
        for x in range(16):
            column = entry.x + x
            if not 0 <= column < width:
                continue
            bit = x if entry.hflip else 15 - x
            raw = (
                (p0 >> bit & 1) | (p1 >> bit & 1) << 1 | (p2 >> bit & 1) << 2 | (p3 >> bit & 1) << 3
            )
            if not raw:
                continue
            if entry.sprite0 and buffer[column] & 0x0F and (hit is None or column < hit):
                hit = column
            buffer[column] = 0x100 | entry.palette | raw | (0x200 if entry.priority else 0)
    if enabled:
        for column, value in enumerate(buffer):
            if value & 0x0F:
                target = first + column
                if not row[target] & 0x0F or value & 0x200:
                    row[target] = value & 0x1FF
    return hit
