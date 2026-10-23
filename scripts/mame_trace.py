#!/usr/bin/env python3
"""Record MAME 0.285's per-instruction HuC6280 trace and hardware-page access log for a HuCard.

Runs the recipe in docs/mame-oracle.md in a fresh directory (default
``tests/mame_traces/<driver>-<card stem>``, gitignored) and leaves ``error.log``
there. The ``pce``, ``tg16`` and ``sgx`` drivers need **no ROM set**: the machine
has no BIOS (``mame -listroms pce``: "No ROMs required"). A ``.7z``/``.zip`` card
is extracted into the run directory with ``7z``; nothing is written elsewhere.

    python -I scripts/mame_trace.py pce tests/test_roms/CPU_Test/CPU_Test_10.pce --seconds 2
    python -I scripts/mame_trace.py pce "/data/emu/roms-retrobat/pcengine/Bonk's Adventure (USA).7z" \\
        --no-trace --seconds 20      # a snapshot only (snap/pce/0000.png at exit)
    python -I scripts/mame_trace.py sgx "/data/emu/roms-retrobat/supergrafx/Battle Ace (Japan) (En).7z" --seconds 3

``error.log`` then holds, in execution order:

- ``C PC A X Y S P totalcycles beamy beamx frame MPR1 MPR2 MPR3 MPR4``: one line per
  instruction, before it executes (hex, then decimal). PC is the 16-bit logical
  address; ``totalcycles`` counts the CPU's cycles at the CPU clock (MAME's
  ``h6280`` device is clocked at 21.477272 MHz / 3), not master clocks.
  A ``logerror`` action silently drops values past 14 (found on the Z80 boards);
  the C line has 14, so MPR0 (always $FF after reset) and MPR5-MPR7 are omitted:
  rerun with ``--mprs`` to log MPR0-MPR7 instead of the clock fields;
- ``R addr value cycles`` / ``W addr value cycles``: every CPU access to the
  hardware page (physical ``$1FE000-$1FFFFF``: VDC, VCE, PSG, timer, I/O, IRQ,
  CD interface), stamped with the cycle count when the watchpoint fired
  (the access, not the instruction start);
- MAME's own ``unmapped program memory`` complaints.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAME = "/usr/games/mame"

# Tags from `mame -listdevices pce` (0.285): maincpu = HuC6280 (h6280),
# huc6270 (VDC), huc6260 (VCE), pce_cd, cartslot, ctrl. sgx has huc6270_0,
# huc6270_1 and huc6202 (VPC).
DRIVERS = {
    "pce": "PC Engine (NTSC-J), 21.477272 MHz master clock",
    "tg16": "TurboGrafx-16 (NTSC-U)",
    "sgx": "SuperGrafx",
}

TRACE_LUA = """\
local dbg = manager.machine.debugger
dbg.visible_cpu = manager.machine.devices[":maincpu"]
dbg:command('trace cpu.trace,:maincpu,noloop,{{logerror "C %X %X %X %X %X %X {tail}\\\\n",\
pc,a,x,y,s,p,{tailargs}}}')
dbg:command('wpset 1fe000,2000,r,1,{{logerror "R %X %X %d\\\\n",wpaddr,wpdata,totalcycles; g}}')
dbg:command('wpset 1fe000,2000,w,1,{{logerror "W %X %X %d\\\\n",wpaddr,wpdata,totalcycles; g}}')
dbg:command("go")
"""
CLOCK = ("%d %d %d %d %X %X %X %X", "totalcycles,beamy,beamx,frame,mpr1,mpr2,mpr3,mpr4")
MPRS = ("%X %X %X %X %X %X %X %X", "mpr0,mpr1,mpr2,mpr3,mpr4,mpr5,mpr6,mpr7")


def extract(cart: Path, out: Path) -> Path:
    """The card image inside a .7z/.zip, extracted into ``out``; a plain image is copied."""
    if cart.suffix.lower() not in {".7z", ".zip"}:
        target = out / cart.name
        shutil.copyfile(cart, target)
        return target
    subprocess.run(["7z", "e", "-y", f"-o{out}", str(cart)], check=True, stdout=subprocess.DEVNULL)
    images = [p for p in out.iterdir() if p.suffix.lower() in {".pce", ".sgx", ".bin"}]
    if len(images) != 1:
        raise SystemExit(
            f"expected one card image in {cart.name}, found {[p.name for p in images]}"
        )
    return images[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("driver", choices=sorted(DRIVERS))
    parser.add_argument("cart", type=Path, help=".pce/.sgx image, or a .7z/.zip holding one")
    parser.add_argument("--seconds", type=int, default=2, help="emulated seconds")
    parser.add_argument("--no-trace", action="store_true", help="no instruction or register trace")
    parser.add_argument(
        "--mprs", action="store_true", help="log MPR0-7 instead of the clock fields"
    )
    parser.add_argument("--out", type=Path)
    parser.add_argument("--mame", default=MAME)
    args = parser.parse_args()
    cart = args.cart.resolve()
    stem = cart.stem.split(" (")[0].replace(" ", "_")
    out = (args.out or ROOT / "tests" / "mame_traces" / f"{args.driver}-{stem}").resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    image = extract(cart, out)
    script = []
    if not args.no_trace:
        tail, tailargs = MPRS if args.mprs else CLOCK
        (out / "trace.lua").write_text(
            TRACE_LUA.format(tail=tail, tailargs=tailargs), encoding="utf-8"
        )
        script = ["-autoboot_script", str(out / "trace.lua")]
    version = subprocess.run(
        [args.mame, "-version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    debug = ["-debug", "-debugger", "none"] if script else []
    began = time.monotonic()
    # error.log lands in the working directory, not under -homepath.
    subprocess.run(
        [args.mame, args.driver, "-cart", image.name, "-rompath", str(out / "no-roms"),
         "-homepath", str(out), "-snapshot_directory", "snap",
         "-video", "none", "-sound", "none", "-nothrottle",
         "-noreadconfig", "-skip_gameinfo", *debug, "-log",
         "-seconds_to_run", str(args.seconds), *script],
        cwd=out, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip
    wall = time.monotonic() - began
    counts = {b"C": 0, b"R": 0, b"W": 0}
    with (out / "error.log").open("rb") as log:
        for line in log:
            key = line[:1]
            if line[1:2] == b" " and key in counts:
                counts[key] += 1
    print(
        f"MAME {version}, {args.driver}, {args.seconds} s emulated in {wall:.1f} s: {out / 'error.log'}"
    )
    if not args.no_trace:
        print(
            f"  {counts[b'C']:,} instructions, {counts[b'R']:,} hardware-page reads, "
            f"{counts[b'W']:,} writes"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
