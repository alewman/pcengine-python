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
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import emu_tools  # noqa: E402
import presses as press_specs  # noqa: E402

#: Mesen2 is driven by a GPL tool outside this repository (docs/provenance.md), run as a
#: separate program: mesen2-runner at $EMU_TOOLS_GPL/tools/mesen2/run.py, machine pce, with
#: --no-sprites (0.2.0) for the background alone and --input for presses. Each run's
#: directory (OUTDIR/run-<name>_<n>/) keeps its manifest.json, the provenance of the picture.
MESEN_RUN = emu_tools.require(emu_tools.MESEN2_RUN)
#: Beetle PCE runs as a program: the core built here before 2026-11-24 (its source is not
#: fetched since, Aubrey's rule) or a shipped libretro build at the same path.
BEETLE = ROOT / "reference/build-beetle-pce/mednafen_pce_libretro.so"


def run_one(card: Path, out: Path, frames: int, which: str, presses: tuple[str, ...] = ()) -> None:
    """One detector to `frames`; `presses` are scripts/presses.py specs (Beetle PCE takes them
    unchanged; Mesen2 takes them as the contract's input script, presses.contract_input)."""
    if which in ("mesen", "mesen_sprites"):
        name = "mesen_ns" if which == "mesen" else "mesen"
        run = out / f"run-{name}_{frames}"
        run.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, "-I", str(MESEN_RUN), "--machine", "pce", "--rom", str(card),
               "--out", str(run), "--frames", str(frames), "--frames-out"]  # fmt: skip
        if which == "mesen":
            cmd.append("--no-sprites")
        if presses:
            script = run / "input.jsonl"
            records = press_specs.contract_input(press_specs.parse(list(presses)))
            script.write_text("".join(json.dumps(r) + "\n" for r in records))
            cmd += ["--input", str(script)]
        subprocess.run(cmd, capture_output=True, check=False)
        # mesen2-runner writes the last frame as frame-NNNNNN.png in its --out directory.
        png = run / f"frame-{frames:06d}.png"
        if png.exists():
            shutil.copyfile(png, out / f"{name}_{frames}.png")
        return
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
