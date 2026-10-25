#!/usr/bin/env python3
"""Build the Mednafen PCE_PSG harness: python scripts/psg_referees/build_mednafen.py OUTDIR."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PSG = ROOT / "reference/src/mednafen-pce-dev/mednafen/src/hw_sound/pce_psg"

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
cmd = [
    "g++", "-O2", "-std=c++17", "-fpermissive", "-w", "-I", str(HERE / "mednafen_shim"), "-I", str(PSG),
    str(HERE / "mednafen_psg.cpp"), str(PSG / "pce_psg.cpp"), "-o", str(out / "mednafen_psg"),
]  # fmt: skip
sys.exit(subprocess.run(cmd, check=False).returncode)
