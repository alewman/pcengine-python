"""Run HuCards on three detectors (MAME 0.285, Mesen2, Beetle PCE = Mednafen) and compare the pictures.

    python -I scripts/detectors_compare.py CARD.pce [CARD.7z ...] [--jobs 8] [--seconds 5]

Each card runs 5 s on MAME (``pce`` driver; ``tg16`` for ``(USA)`` names, whose
images are the US console's, and ``sgx`` under a ``supergrafx`` directory; the
``pce`` driver shows a US card as a BRK loop, measured 2026-10-23), 300 frames on Mesen2 (scripts/mesen_run.py) and
300 frames on Beetle PCE (scripts/libretro_run.py). The three frames have
different geometry (MAME 1088 columns at 4 per 5 MHz dot; Mesen2 292; Beetle
256/341/512 by dot clock), so no pixel-for-pixel comparison is possible and
none is claimed. Two cheap statistics are printed per pair instead:

- ``tv``: total-variation distance (0..1) of the 3-bit-per-channel colour
  histograms of the middle 160 rows (0 = same mix of colours);
- ``rows``: the share of rows whose most common colour agrees, at the best
  vertical offset within 24 rows (the offset is printed; it measures where each
  tool starts its picture).

A large ``tv`` or low ``rows`` means at least one detector draws something
different (or the game is not at the same point after the run: games are
timed from power-on, and 5 s of MAME is 300 frames only if both ran flat out):
the card is a research question, not a verdict. Needs Pillow.
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "reference" / "src" / "beetle-pce" / "mednafen_pce_libretro.so"


def quant(img: Image.Image) -> list[list[int]]:
    """Rows of colours quantised to 3 bits per channel (the VCE's precision)."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    return [
        [
            (round(px[x, y][0] * 7 / 255) << 6)
            | (round(px[x, y][1] * 7 / 255) << 3)
            | round(px[x, y][2] * 7 / 255)
            for x in range(w)
        ]
        for y in range(h)
    ]


def dominant(row: list[int]) -> int:
    return collections.Counter(row).most_common(1)[0][0]


def histogram(rows: list[list[int]]) -> dict[int, float]:
    count = collections.Counter(c for r in rows for c in r)
    total = sum(count.values())
    return {k: v / total for k, v in count.items()}


def compare(a: list[list[int]], b: list[list[int]]) -> tuple[float, float, int]:
    mid = lambda f: f[max(0, len(f) // 2 - 80) : len(f) // 2 + 80]  # noqa: E731
    ha, hb = histogram(mid(a)), histogram(mid(b))
    tv = 0.5 * sum(abs(ha.get(k, 0) - hb.get(k, 0)) for k in set(ha) | set(hb))
    da, db = [dominant(r) for r in a], [dominant(r) for r in b]
    best = (0.0, 0)
    for off in range(-24, 25):
        pairs = [(da[y], db[y + off]) for y in range(30, len(da) - 30) if 0 <= y + off < len(db)]
        share = sum(1 for x, y in pairs if x == y) / max(len(pairs), 1)
        best = max(best, (share, off))
    return tv, best[0], best[1]


def frames(card: Path, work: Path, seconds: int) -> dict[str, Image.Image] | str:
    mame_out = work / "mame"
    driver = (
        "sgx" if "supergrafx" in str(card).lower() else "tg16" if "(USA)" in card.name else "pce"
    )
    subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "mame_trace.py"), driver,
                    str(card), "--no-trace", "--seconds", str(seconds), "--out", str(mame_out)],
                   capture_output=True, check=False)  # fmt: skip
    found = {}
    snaps = sorted((mame_out / "snap").rglob("*.png"))
    if snaps:
        found["mame"] = Image.open(snaps[-1])
    image = (
        next((p for p in mame_out.iterdir() if p.suffix in {".pce", ".sgx"}), None)
        if mame_out.exists()
        else None
    )
    if image is None:
        return "no image"
    for name, cmd in (
        ("mesen", [sys.executable, "-I", str(ROOT / "scripts" / "mesen_run.py"), str(image),
                   "--frames", str(seconds * 60), "--png", str(work / "mesen.png"), "--home", str(work / "home")]),
        ("beetle", [sys.executable, "-I", str(ROOT / "scripts" / "libretro_run.py"), str(CORE), str(image),
                    "--frames", str(seconds * 60), "--png", str(work / "beetle.png"), "--system", str(work)]),
    ):  # fmt: skip
        subprocess.run(cmd, capture_output=True, check=False)
        if (work / f"{name}.png").exists():
            found[name] = Image.open(work / f"{name}.png")
    return (
        found if len(found) == 3 else f"missing {sorted({'mame', 'mesen', 'beetle'} - set(found))}"
    )


def one(card: Path, seconds: int) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        got = frames(card, Path(tmp), seconds)
        if isinstance(got, str):
            return f"{card.name}: {got}"
        q = {k: quant(v) for k, v in got.items()}
    parts = []
    for x, y in (("mame", "mesen"), ("mame", "beetle"), ("mesen", "beetle")):
        tv, rows, off = compare(q[x], q[y])
        parts.append(f"{x[:2]}-{y[:2]} tv {tv:.2f} rows {rows:.2f} off {off:+d}")
    return f"{'; '.join(parts)}  {card.name}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cards", type=Path, nargs="+")
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--seconds", type=int, default=5)
    args = parser.parse_args()
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        for line in pool.map(lambda c: one(c, args.seconds), args.cards):
            print(line, flush=True)


if __name__ == "__main__":
    main()
