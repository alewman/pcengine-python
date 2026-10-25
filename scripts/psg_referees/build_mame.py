#!/usr/bin/env python3
"""Build the MAME c6280 harness: python scripts/psg_referees/build_mame.py OUTDIR (g++ needed)."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOUND = ROOT / "reference/src/mame/src/devices/sound"

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
cmd = [
    "g++", "-O2", "-std=c++17", "-I", str(HERE / "mame_shim"), "-I", str(SOUND),
    str(HERE / "mame_c6280.cpp"), str(SOUND / "c6280.cpp"), "-o", str(out / "mame_c6280"),
]  # fmt: skip
sys.exit(subprocess.run(cmd, check=False).returncode)
