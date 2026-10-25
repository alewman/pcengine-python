#!/usr/bin/env python3
"""Compare this board's picture with Mesen2's and Beetle PCE's at the 9-bit palette value (M2).

    python scripts/m2_compare.py REFDIR OURS.pkl      # needs Pillow and numpy

REFDIR holds the pictures of scripts/m2_refs.py over a window of frames (mesen_ns_<n>.png with
sprites off, mesen_<n>.png with them on, beetle_<n>.png) and OURS.pkl is scripts/m2_ours.py's
frame (rows of 9-bit palette values).

Every picture is brought to 9-bit values (`round(c * 7 / 255)` per channel inverts both
detectors' colour tables exactly) and aligned to ours by the horizontal and vertical offset that
makes most pixels equal (one pixel per dot in all three). Nothing is masked: the numbers are the
share of equal pixels and of fully equal rows over the overlap, and the first differing pixel.

Sprites are milestone 3. So the judge for the background is Mesen2 with `DisableSprites`:

- A  ours against the best Mesen2 frame, sprites off (the window absorbs a few frames of
     power-on phase difference between the emulators; the frame found is printed);
- B  ours against the best Beetle frame (its sprites stay on: what M3 still owes);
- C  ours against Beetle on the pixels where Beetle equals Mesen2-without-sprites, i.e. where
     the two detectors agree on the background: the "wherever the two agree" of the M2 exit;
- D  Mesen2 without sprites against Beetle (the sprites are the difference);
- E  the two detectors as shipped (Mesen2 with sprites, Beetle): the first differing pixel, and
     whether it is a sprite or a background pixel.
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def nine_bit(path: Path) -> np.ndarray:
    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)
    q = np.rint(rgb * 7 / 255).astype(np.uint16)
    return (q[..., 1] << 6) | (q[..., 0] << 3) | q[..., 2]


def window(a, b, dx, dy):
    """Aligned views: a[y][x] against b[y + dy][x + dx] over the common area."""
    y0, y1 = max(0, -dy), min(a.shape[0], b.shape[0] - dy)
    x0, x1 = max(0, -dx), min(a.shape[1], b.shape[1] - dx)
    if y1 <= y0 or x1 <= x0:
        return None
    return (y0, x0), a[y0:y1, x0:x1], b[y0 + dy : y1 + dy, x0 + dx : x1 + dx]


def best_alignment(a, b, dxs, dys, prefer=()):
    """The (share, dx, dy) with most equal pixels; ties go to the dx nearest `prefer` (a flat
    picture matches everywhere, and the dot clock's known offset is the honest answer then)."""
    best = (-1.0, 0, 0)
    order = sorted(dxs, key=lambda d: min((abs(d - p) for p in prefer), default=0))
    for dy in sorted(dys, key=abs):
        for dx in order:
            w = window(a, b, dx, dy)
            if w is None or w[1].size < 4000:
                continue
            share = float((w[1][::3] == w[2][::3]).mean())
            if share > best[0]:
                best = (share, dx, dy)
    return best


def stats(a, b, dx, dy, mask=None):
    """Equal share of pixels and of rows, and the first differing pixel (row, col in a's
    coordinates). `mask` is a boolean array over `a` limiting the pixels counted."""
    w = window(a, b, dx, dy)
    if w is None:
        return 0.0, 0.0, None, 0
    (y0, x0), wa, wb = w
    keep = (
        np.ones(wa.shape, bool)
        if mask is None
        else mask[y0 : y0 + wa.shape[0], x0 : x0 + wa.shape[1]]
    )
    equal = (wa == wb) & keep
    total = int(keep.sum())
    rows = keep.any(axis=1)
    rows_equal = ((wa == wb) | ~keep).all(axis=1) & rows
    differ = np.argwhere(keep & (wa != wb))
    first = None
    if len(differ):
        y, x = differ[0]
        first = (y + y0, x + x0, int(wa[y, x]), int(wb[y, x]))
    return (
        float(equal.sum()) / max(total, 1),
        float(rows_equal.sum()) / max(int(rows.sum()), 1),
        first,
        total,
    )


def load_window(d: Path, stem: str) -> dict[int, np.ndarray]:
    return {
        int(p.stem.rsplit("_", 1)[1]): nine_bit(p) for p in sorted(d.glob(f"{stem}_[0-9]*.png"))
    }


def ours_array(rows) -> np.ndarray:
    return np.array(rows, dtype=np.uint16)


def best_frame(frames, target, dxs, dys, prefer=()):
    return max(
        ((best_alignment(pic, target, dxs, dys, prefer), n) for n, pic in frames.items()),
        key=lambda t: t[0][0],
    )


def main() -> int:
    refs = Path(sys.argv[1])
    ours = ours_array(pickle.loads(Path(sys.argv[2]).read_bytes())["rows"])
    mesen = load_window(refs, "mesen_ns")
    beetle = load_window(refs, "beetle")
    full = load_window(refs, "mesen")
    dxs, dys = range(-80, 140), range(-3, 4)
    out = [f"{refs.parent.name}  ({Path(sys.argv[2]).stem}, {ours.shape[1]} dots a row)"]

    (_, dx, dy), n_m = best_frame(mesen, ours, dxs, dys, (14, 24))
    px, rows, first, total = stats(mesen[n_m], ours, dx, dy)
    out.append(
        f"A mesen(no sprites) frame {n_m} vs ours: dx {dx:+d} dy {dy:+d}: "
        f"px {px:.4f} rows {rows:.4f} of {total} px"
    )
    if first:
        out.append(
            f"   first differing pixel: row {first[0]} col {first[1]}: mesen {first[2]:#05x} ours {first[3]:#05x}"
        )

    if full:  # M3: sprites on in both
        (_, dx_f, dy_f), n_f = best_frame(full, ours, dxs, dys, (14, 24))
        px_f, rows_f, first_f, total_f = stats(full[n_f], ours, dx_f, dy_f)
        out.append(
            f"F mesen(sprites on) frame {n_f} vs ours: dx {dx_f:+d} dy {dy_f:+d}: "
            f"px {px_f:.4f} rows {rows_f:.4f} of {total_f} px"
        )
        if first_f:
            wa, wb = window(full[n_f], ours, dx_f, dy_f)[1:]
            bad = np.argwhere(wa != wb)
            rows_bad = sorted({int(y) for y, _ in bad})
            out.append(
                f"   first differing pixel: row {first_f[0]} col {first_f[1]}: mesen {first_f[2]:#05x} "
                f"ours {first_f[3]:#05x}; {len(bad)} px in {len(rows_bad)} rows, "
                f"rows {rows_bad[0]}-{rows_bad[-1]}, cols {int(bad[:, 1].min())}-{int(bad[:, 1].max())}"
            )
    (_, dx_b, dy_b), n_b = best_frame(beetle, ours, dxs, dys, (32, 46))
    px_b, rows_b, _first_b, _ = stats(beetle[n_b], ours, dx_b, dy_b)
    out.append(
        f"B beetle frame {n_b} vs ours: dx {dx_b:+d} dy {dy_b:+d}: px {px_b:.4f} rows {rows_b:.4f}"
    )

    def best_pair(mesen_frames):
        return max(
            (
                (best_alignment(mp, bp, range(-40, 40), range(-3, 4), (-18, -22)), nb, nm)
                for nb, bp in beetle.items()
                for nm, mp in mesen_frames.items()
                if abs(nb - nm) <= 6
            ),
            key=lambda t: t[0][0],
        )

    (_, dxd, dyd), nb, nm = best_pair(mesen)
    px_d, rows_d, first_d, _ = stats(mesen[nm], beetle[nb], dxd, dyd)
    out.append(
        f"D mesen(no sprites) {nm} vs beetle {nb}: dx {dxd:+d} dy {dyd:+d}: px {px_d:.4f} rows {rows_d:.4f}"
    )
    if first_d:
        out.append(
            f"   first differing pixel: row {first_d[0]} col {first_d[1]}: mesen {first_d[2]:#05x} beetle {first_d[3]:#05x}"
        )

    # C: Beetle's pixels that equal Mesen2's (sprites off), against ours, in Beetle coordinates:
    # Beetle's frame nearest ours (B), and Mesen2's frame (within 6) nearest that Beetle frame
    nb = n_b
    (_, dxd, dyd), nm = max(
        (
            (best_alignment(mp, beetle[nb], range(-40, 40), range(-3, 4), (-18, -22)), nm_)
            for nm_, mp in mesen.items()
            if abs(nb - nm_) <= 6
        ),
        key=lambda t: t[0][0],
    )
    bpic, mpic = beetle[nb], mesen[nm]
    w = window(mpic, bpic, dxd, dyd)
    agree = np.zeros(bpic.shape, bool)
    if w is not None:
        (y0, x0), wm, wbp = w
        agree[y0 + dyd : y0 + dyd + wm.shape[0], x0 + dxd : x0 + dxd + wm.shape[1]] = wm == wbp
    (_, dxc, dyc), _n_c = best_frame({nb: bpic}, ours, dxs, dys, (32, 46))
    px_c, rows_c, first_c, total_c = stats(bpic, ours, dxc, dyc, mask=agree)
    out.append(
        f"C ours vs beetle {nb} where it equals mesen {nm}: px {px_c:.4f} rows {rows_c:.4f} of {total_c} px"
    )
    if first_c:
        out.append(
            f"   first differing pixel: row {first_c[0]} col {first_c[1]}: beetle {first_c[2]:#05x} ours {first_c[3]:#05x}"
        )

    if full:
        (_, dxe, dye), nbe, nme = best_pair(full)
        px_e, rows_e, first_e, _ = stats(full[nme], beetle[nbe], dxe, dye)
        out.append(
            f"E mesen(sprites) {nme} vs beetle {nbe}: dx {dxe:+d} dy {dye:+d}: px {px_e:.4f} rows {rows_e:.4f}"
        )
        if first_e:
            y, x = first_e[0], first_e[1]
            kind = "a pixel Mesen2 draws only with sprites on (a sprite)"
            if nme in mesen and mesen[nme][y, x] == full[nme][y, x]:
                kind = (
                    "background in Mesen2 (the same with its sprites off); Beetle shows another "
                    "value there: a Beetle sprite or a background difference"
                )
            out.append(
                f"   first differing pixel: row {y} col {x}: mesen {first_e[2]:#05x} beetle {first_e[3]:#05x}: {kind}"
            )
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
