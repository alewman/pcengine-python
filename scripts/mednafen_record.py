#!/usr/bin/env python3
"""Record Mednafen 1.32.1's per-instruction trace of a HuCard, for scripts/lockstep.py.

    python -I scripts/mednafen_record.py CARD.pce|CARD.7z --out DIR [--count 20000000]

Uses the trace build of the sibling repository (huc6280-python: `python -I scripts/build_mednafen.py`
builds `reference/build/mednafen-bin/bin/mednafen` from the pinned source plus
`tools/mednafen-trace.patch`; nothing is built or edited here). Writes DIR/cart.pce (the card,
a copier header dropped) and DIR/error.log (about 45 bytes per instruction plus the hardware-page
reads: keep DIR outside the repository, and delete it when done). See docs/m5-lockstep-record.md.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

BINARY = Path(
    os.environ.get(
        "MEDNAFEN",
        "/data/emu/huc6280-python/reference/build/mednafen-bin/bin/mednafen",
    )
)


def load_card(path: Path) -> bytes:
    """The first .pce/.sgx/.bin of a .7z/.zip (via 7z, through a pipe), or the file itself."""
    if path.suffix.lower() in (".7z", ".zip"):
        listing = subprocess.run(
            ["7z", "l", "-slt", str(path)], capture_output=True, text=True, check=True
        ).stdout
        names = [
            line.split(" = ", 1)[1]
            for line in listing.splitlines()
            if line.startswith("Path = ") and line.lower().endswith((".pce", ".sgx", ".bin"))
        ]
        if not names:
            raise SystemExit(f"{path.name}: no .pce/.sgx/.bin inside")
        data = subprocess.run(
            ["7z", "x", "-so", str(path), names[0]], capture_output=True, check=True
        ).stdout
    else:
        data = path.read_bytes()
    return data[512:] if len(data) % 8192 == 512 else data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("card", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--count", type=int, default=20_000_000, help="instructions to log")
    args = parser.parse_args()
    if not BINARY.exists():
        raise SystemExit(f"{BINARY} is missing: build it in huc6280-python (see the docstring)")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "home").mkdir(exist_ok=True)
    (out / "cart.pce").write_bytes(load_card(args.card.resolve()))
    env = dict(os.environ)
    env.update(
        SDL_VIDEODRIVER="dummy",
        SDL_AUDIODRIVER="dummy",
        MEDNAFEN_HOME=str(out / "home"),
        MEDNAFEN_TRACE=str(out / "error.log"),
        MEDNAFEN_TRACE_COUNT=str(args.count),
    )
    subprocess.run(
        [str(BINARY), "-sound", "0", "-video.fs", "0", "-pce.stretch", "0", "-nothrottle", "1",
         "-filesys.path_firmware", str(out / "home"), str(out / "cart.pce")],
        env=env, cwd=out, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=1800,
    )  # fmt: skip
    log = out / "error.log"
    size = log.stat().st_size if log.exists() else 0
    print(f"{log}: {size:,} bytes")
    return 0 if size else 1


if __name__ == "__main__":
    sys.exit(main())
