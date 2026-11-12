#!/usr/bin/env python3
"""Run Mesen2 (sprites disabled) and Beetle PCE over a window of frames for one HuCard (M2).

    python -I scripts/m2_refs.py CARD.pce OUTDIR --around 300 [--window 12]

writes OUTDIR/mesen_ns_<n>.png (sprites off), mesen_<n>.png (sprites on) and beetle_<n>.png for n in around-window .. around+window.
The window absorbs the few frames by which emulators' power-on to first picture differ
(measured: After Burner II's title animation is 2-5 frames apart). Beetle PCE has no
layer switch in its libretro build, so its pictures keep their sprites; Mesen2's do not.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEETLE = ROOT / "reference/src/beetle-pce/mednafen_pce_libretro.so"


def run_one(card: Path, out: Path, frames: int, which: str, presses: tuple[str, ...] = ()) -> None:
    """One detector to `frames`; `presses` are scripts/presses.py specs, given to it unchanged."""
    if which in ("mesen", "mesen_sprites"):
        name = "mesen_ns" if which == "mesen" else "mesen"
        flags = ["--no-sprites"] if which == "mesen" else []
        cmd = [sys.executable, "-I", str(ROOT / "scripts/mesen_run.py"), str(card), "--frames",
               str(frames), *flags, "--png", str(out / f"{name}_{frames}.png"),
               "--home", str(out / f"home{frames}")]  # fmt: skip
    else:
        cmd = [sys.executable, "-I", str(ROOT / "scripts/libretro_run.py"), str(BEETLE), str(card),
               "--frames", str(frames), "--png", str(out / f"beetle_{frames}.png"),
               "--system", str(out)]  # fmt: skip
    for spec in presses:
        cmd += ["--press", spec]
    subprocess.run(cmd, capture_output=True, check=False)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("card", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--around", type=int, default=300)
    p.add_argument("--window", type=int, default=12)
    p.add_argument("--jobs", type=int, default=16)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    jobs = [
        (n, w)
        for n in range(a.around - a.window, a.around + a.window + 1)
        for w in ("mesen", "mesen_sprites", "beetle")
    ]
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as pool:
        list(pool.map(lambda j: run_one(a.card, a.out, j[0], j[1]), jobs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
