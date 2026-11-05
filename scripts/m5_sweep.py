#!/usr/bin/env python3
"""M5 library sweep: one HuCard (or all) on this board against Mesen2 and Beetle PCE.

    python3 -I scripts/m5_sweep.py LIBDIR SCRATCH RESULTS.jsonl [--only SUBSTR] [--names FILE]
        [--jobs 3] [--cards 10] [--targets 300 600]

For each .7z/.zip/.pce in LIBDIR (top level, read in place): the image is extracted into its own
directory under SCRATCH, run on this board under PyPy (`.venv-pypy`) to frame 300 and 600
(`m2_ours.py --then`), and Mesen2 (sprites on) and Beetle PCE are run over frames n-W..n+W
(`m2_refs.py`'s runner). Ours is compared at the 9-bit palette value after the detectors'
alignment offsets (Mesen2 dx 14 or 24, Beetle dx 32 or 46, dy -2..2): share of equal pixels, share
of equal rows, first differing pixel. One JSON line per card and frame is appended to RESULTS; a
card already in RESULTS is skipped. The extracted copies are deleted after each card by a small
Python helper (BYOR: no ROM bytes stay anywhere). Needs numpy and Pillow: the system python3
(the venvs lack them); the board itself runs under `.venv-pypy`. `--targets A B` picks the two
frames compared (pass 2 of the M5 record used 900 and 1500).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import pickle
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import m2_compare as cmp  # noqa: E402
import m2_refs  # noqa: E402

PYPY = ROOT / ".venv-pypy/bin/python"
IMAGE = {".pce", ".sgx", ".bin", ".rom"}
TARGETS = (300, 600)
WINDOW = 8


def remove_tree(path: Path) -> None:
    """Delete a scratch directory by name, file by file (no recursive shell command)."""
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            os.unlink(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    path.rmdir()


def extract(archive: Path, into: Path) -> Path:
    into.mkdir(parents=True)
    if archive.suffix.lower() in IMAGE:
        return archive  # read in place
    subprocess.run(["7z", "x", "-y", f"-o{into}", str(archive)], capture_output=True, check=True)
    found = [p for p in into.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE]
    if len(found) != 1:
        raise RuntimeError(f"{archive.name}: {len(found)} images")
    return found[0]


def best_frame_exact(pics, ours, dxs, dys, prefer):
    """`cmp.best_frame`, but ties are broken on the full picture, not the 1-in-3 sample.

    `best_alignment` scores a third of the pixels, so on a mostly flat picture several (frame, dx)
    pairs score a full 1.0 and the first one wins, even when the right frame differs from it in a
    few dozen pixels (Formation Soccer at 300: frame 297 at dx 197 beat frame 300 at dx 14 and the
    card read as NEAR; M5 record). Every candidate within 0.5 % of the best sampled share is
    scored on all pixels and rows, and the best of those is the answer."""
    scored = [(cmp.best_alignment(pic, ours, dxs, dys, prefer), n) for n, pic in pics.items()]
    top = max(a[0] for a, _ in scored)
    best = None
    for (share, dx, dy), n in scored:
        if share < top - 0.005:
            continue
        px, rows, _, _ = cmp.stats(pics[n], ours, dx, dy)
        if best is None or (rows, px) > best[0]:
            best = ((rows, px), (share, dx, dy), n)
    return best[1], best[2]


def compare(ours_pkl: Path, refs: Path, target: int) -> dict:
    ours = cmp.ours_array(pickle.loads(ours_pkl.read_bytes())["rows"])
    dys = range(-2, 3)
    out: dict = {"target": target}
    # 5 and 7 MHz rows have known offsets (the tie-break prefers them); 10 MHz rows (682 dots)
    # have their own, so the search covers every shift.
    wide = range(-120, 200)
    for name, stem, prefer in (("mesen", "mesen", (14, 24, 68)), ("beetle", "beetle", (32, 46))):
        pics = {n: p for n, p in cmp.load_window(refs, stem).items() if abs(n - target) <= WINDOW}
        if not pics:
            out[name] = None
            continue
        (_, dx, dy), n = best_frame_exact(pics, ours, wide, dys, prefer)
        px, rows, first, total = cmp.stats(pics[n], ours, dx, dy)
        out[name] = {"frame": n, "dx": dx, "dy": dy, "px": round(px, 4), "rows": round(rows, 4),
                     "first": first, "total": total}  # fmt: skip
    return out


def one(card: Path, scratch: Path, jobs: int) -> list[dict]:
    work = scratch / re.sub(r"\W+", "_", card.stem)
    image = extract(card, work / "rom")
    tg16 = "(USA)" in card.name
    began = time.monotonic()
    ours = work / "ours.pkl"
    cmd = [str(PYPY), "-I", str(ROOT / "scripts/m2_ours.py"), str(image), str(ours),
           "--frames", str(TARGETS[0]), "--then", str(TARGETS[1])]  # fmt: skip
    if tg16:
        cmd.append("--tg16")
    run = subprocess.run(cmd, capture_output=True, text=True, check=False)
    speed = time.monotonic() - began
    rows = []
    try:
        if run.returncode:
            raise RuntimeError(run.stderr.strip().splitlines()[-1] if run.stderr else "failed")
        refs = work / "refs"
        for target in TARGETS:
            m2_refs_jobs = [(n, w) for n in range(target - WINDOW, target + WINDOW + 1)
                            for w in ("mesen_sprites", "beetle")]  # fmt: skip
            with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
                list(
                    pool.map(
                        lambda j: m2_refs.run_one(image, refs, j[0], j[1]),
                        m2_jobs(refs, m2_refs_jobs),
                    )
                )
            pkl = ours if target == TARGETS[0] else ours.with_name(f"ours-{target}.pkl")
            r = compare(pkl, refs, target)
            r.update(
                card=card.name, tg16=tg16, size=image.stat().st_size, ours_seconds=round(speed, 1)
            )
            rows.append(r)
    except Exception as e:  # recorded, not hidden
        rows.append({"card": card.name, "tg16": tg16, "error": f"{type(e).__name__}: {e}"})
    finally:
        remove_tree(work)
    return rows


def m2_jobs(refs: Path, jobs):
    refs.mkdir(parents=True, exist_ok=True)
    return jobs


def main() -> int:
    global TARGETS
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("lib", type=Path)
    p.add_argument("scratch", type=Path)
    p.add_argument("results", type=Path)
    p.add_argument("--only", default="")
    p.add_argument("--names", type=Path, help="file of card file names, one per line")
    p.add_argument("--jobs", type=int, default=6)
    p.add_argument(
        "--targets",
        type=int,
        nargs=2,
        default=TARGETS,
        metavar=("A", "B"),
        help="the two frames compared (default 300 600; pass 2 uses later ones)",
    )
    p.add_argument("--cards", type=int, default=3, help="cards in parallel")
    a = p.parse_args()
    TARGETS = tuple(a.targets)
    done = set()
    if a.results.exists():
        done = {json.loads(line)["card"] for line in a.results.read_text().splitlines() if line}
    todo = sorted(
        c for c in a.lib.iterdir()
        if c.is_file() and c.suffix.lower() in IMAGE | {".7z", ".zip"} and a.only in c.name
        and (a.names is None or c.name in set(a.names.read_text().splitlines()))
        and c.name not in done
    )  # fmt: skip
    a.scratch.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(a.cards) as pool:
        for rows in pool.map(lambda c: one(c, a.scratch, a.jobs), todo):
            with a.results.open("a") as f:
                for r in rows:
                    f.write(json.dumps(r, default=int) + "\n")
            print(rows[0]["card"], [(r.get("mesen") or {}).get("rows") for r in rows], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
