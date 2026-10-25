#!/usr/bin/env python3
"""Compare this board's picture with Mesen2's and Beetle PCE's at the 9-bit palette value (M2).

    python scripts/m2_compare.py WORKDIR/TITLE [ours300d.pkl]   # a directory holding
        ours300.pkl     scripts/m2_ours.py            (rows of 9-bit palette values)
        mesen300.png    scripts/mesen_run.py          (sprites on)
        mesen300ns.png  scripts/mesen_run.py --no-sprites
        beetle300.png   scripts/libretro_run.py       (Beetle PCE: sprites always on)

Every picture is brought to 9-bit values (`round(c * 7 / 255)` per channel, which inverts both
detectors' colour tables exactly), then aligned to ours by the horizontal and vertical offset
that makes most pixels equal (dot clocks of 1 pixel per dot in all three). Nothing is masked: the
numbers are the share of equal pixels and of fully equal rows over the overlap, and the first
differing row with its first differing columns.

Sprites are milestone 3. So the judge for the background is Mesen2 with `DisableSprites` (A);
ours against the sprite-showing pictures (B, with Beetle) shows what M3 still owes; (C) is ours
against Beetle on the pixels where Beetle equals Mesen2-without-sprites, i.e. where the two
detectors agree on the background: that is the "wherever the two agree" of the exit.
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path

from PIL import Image


def nine_bit(path: Path) -> list[list[int]]:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    px = img.load()
    return [
        [
            (round(px[x, y][1] * 7 / 255) << 6)
            | (round(px[x, y][0] * 7 / 255) << 3)
            | round(px[x, y][2] * 7 / 255)
            for x in range(w)
        ]
        for y in range(h)
    ]


def overlap(a, b, dx, dy):
    """Pairs (a[y][x], b[y+dy][x+dx]) over the common area, as row-wise slices."""
    for y, row in enumerate(a):
        yy = y + dy
        if not 0 <= yy < len(b):
            continue
        other = b[yy]
        x0 = max(0, -dx)
        x1 = min(len(row), len(other) - dx)
        if x1 > x0:
            yield y, x0, row[x0:x1], other[x0 + dx : x1 + dx]


def best_alignment(a, b, dxs, dys):
    best = (-1.0, 0, 0)
    for dy in dys:
        for dx in dxs:
            equal = total = 0
            for y, _, ra, rb in overlap(a, b, dx, dy):
                if y % 4:
                    continue
                total += len(ra)
                equal += sum(1 for p, q in zip(ra, rb, strict=True) if p == q)
            if total > 2000 and equal / total > best[0]:
                best = (equal / total, dx, dy)
    return best


def stats(a, b, dx, dy, mask=None):
    """Equal share of pixels and of rows over the overlap; `mask(y, x)` limits the pixels."""
    equal = total = rows_equal = rows = 0
    first = None
    for y, x0, ra, rb in overlap(a, b, dx, dy):
        row_total = row_equal = 0
        for i, (p, q) in enumerate(zip(ra, rb, strict=True)):
            if mask is not None and not mask(y, x0 + i):
                continue
            row_total += 1
            if p == q:
                row_equal += 1
            elif first is None:
                first = (y, x0 + i, p, q)
        total += row_total
        equal += row_equal
        if row_total:
            rows += 1
            rows_equal += row_equal == row_total
    return equal / max(total, 1), rows_equal / max(rows, 1), first, total


def load_window(d: Path, stem: str):
    found = {}
    for path in sorted(d.glob(f"{stem}_*.png")):
        found[int(path.stem.rsplit("_", 1)[1])] = nine_bit(path)
    return found


def main() -> int:
    """m2_compare.py REFDIR OURS.pkl [FRAME]: the pictures of m2_refs.py against ours."""
    refs = Path(sys.argv[1])
    ours_data = pickle.loads(Path(sys.argv[2]).read_bytes())
    ours = ours_data["rows"]
    name = Path(sys.argv[2]).stem
    mesen = load_window(refs, "mesen_ns")
    beetle = load_window(refs, "beetle")
    out = [f"{refs.parent.name}  ({name}, {len(ours[0])} dots a row)"]
    dxs = range(-80, 140)
    # A: the best Mesen2 frame (sprites disabled) against ours
    best = max(
        ((best_alignment(pic, ours, dxs, range(-3, 4)), n) for n, pic in mesen.items()),
        key=lambda t: t[0][0],
    )
    (_, dx_m, dy_m), n_m = best
    px, rows, first, total = stats(mesen[n_m], ours, dx_m, dy_m)
    out.append(
        f"A mesen(no sprites) frame {n_m} vs ours: dx {dx_m:+d} dy {dy_m:+d}: "
        f"px {px:.4f} rows {rows:.4f} of {total} px"
    )
    if first:
        out.append(
            f"   first differing pixel: row {first[0]} col {first[1]}: mesen {first[2]:#05x} ours {first[3]:#05x}"
        )
    # B: the best Beetle frame (sprites on) against ours; C: only where Beetle equals Mesen2
    best_b = max(
        ((best_alignment(pic, ours, dxs, range(-3, 4)), n) for n, pic in beetle.items()),
        key=lambda t: t[0][0],
    )
    (_, dx_b, dy_b), n_b = best_b
    px_b, rows_b, _first_b, _ = stats(beetle[n_b], ours, dx_b, dy_b)
    out.append(
        f"B beetle frame {n_b} vs ours: dx {dx_b:+d} dy {dy_b:+d}: px {px_b:.4f} rows {rows_b:.4f}"
    )
    # the Beetle frame / Mesen2 frame pair that agrees most, as the two detectors' own agreement
    pair = max(
        (
            (best_alignment(mp, bp, range(-40, 40), range(-3, 4)), nb, nm)
            for nb, bp in beetle.items()
            for nm, mp in mesen.items()
            if abs(nb - nm) <= 6
        ),
        key=lambda t: t[0][0],
    )
    (_, dxb, dyb), nb, nm = pair
    px_d, rows_d, first_d, _ = stats(mesen[nm], beetle[nb], dxb, dyb)
    out.append(
        f"D mesen(no sprites) {nm} vs beetle {nb}: dx {dxb:+d} dy {dyb:+d}: px {px_d:.4f} rows {rows_d:.4f}"
    )
    if first_d:
        out.append(
            f"   first differing pixel: row {first_d[0]} col {first_d[1]}: mesen {first_d[2]:#05x} beetle {first_d[3]:#05x}"
        )

    def agree(y, x):  # (y, x) in Beetle coordinates: Beetle equals Mesen2 at the pair's frames
        ym, xm = y - dyb, x - dxb
        mp = mesen[nm]
        return 0 <= ym < len(mp) and 0 <= xm < len(mp[0]) and mp[ym][xm] == beetle[nb][y][x]

    px_c, rows_c, first_c, total_c = stats(
        beetle[nb], ours, *best_alignment(beetle[nb], ours, dxs, range(-3, 4))[1:], mask=agree
    )
    out.append(
        f"C ours vs beetle {nb} where it equals mesen {nm}: px {px_c:.4f} rows {rows_c:.4f} of {total_c} px"
    )
    if first_c:
        out.append(
            f"   first differing pixel: row {first_c[0]} col {first_c[1]}: beetle {first_c[2]:#05x} ours {first_c[3]:#05x}"
        )
    # E: the two detectors as they ship (Mesen2 with sprites, Beetle): where they differ
    full = load_window(refs, "mesen")
    if full:
        pair_e = max(
            (
                (best_alignment(mp, bp, range(-40, 40), range(-3, 4)), nb, nm)
                for nb, bp in beetle.items()
                for nm, mp in full.items()
                if abs(nb - nm) <= 6
            ),
            key=lambda t: t[0][0],
        )
        (_, dxe, dye), nbe, nme = pair_e
        px_e, rows_e, first_e, _ = stats(full[nme], beetle[nbe], dxe, dye)
        out.append(
            f"E mesen(sprites) {nme} vs beetle {nbe}: dx {dxe:+d} dy {dye:+d}: "
            f"px {px_e:.4f} rows {rows_e:.4f}"
        )
        if first_e:
            y, x = first_e[0], first_e[1]
            ns = mesen.get(nme)
            kind = "a sprite pixel (Mesen2 shows it only with sprites on)"
            if ns is not None and ns[y][x] == full[nme][y][x]:
                kind = "a BACKGROUND pixel: the detectors disagree on the background"
            out.append(
                f"   first differing pixel: row {y} col {x}: mesen {first_e[2]:#05x} "
                f"beetle {first_e[3]:#05x}: {kind}"
            )
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
