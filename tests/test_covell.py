"""Covell's CPU timing test (tier 1) through the board and the real core.

What holds: every instruction group draws a *vertical* split (over 115 scanlines the interquartile
range is at most two dots; the photographs show two to three pixels), as they do. What does not
yet: the split sits up to 6 dots right of the photographed position at the -8 default (0 to 12 at 0) (docs/m1-record.md), so
"within one cycle of the photographs" is NOT claimed. The offsets are pinned
here as a regression record, not as a pass of the exit.

Needs the test ROM (scripts/fetch_references.py) and the pinned core. The band is the coarse
regression of M1's registration through Mednafen's screenshot; `scripts/covell_calibrate.py` is the
measurement anchored on the test's own text (docs/m1-record.md, "Calibration with the
background").
"""

import json
import statistics
from pathlib import Path

import pytest

from pcengine_python import pads
from pcengine_python.board import Board
from pcengine_python.cards import RomCard
from pcengine_python.system import build

ROOT = Path(__file__).resolve().parent
ROM = ROOT / "test_roms" / "CPU_Test" / "CPU_Test_10.pce"

pytestmark = [
    pytest.mark.slow,
    pytest.mark.needs_cpu,
    pytest.mark.skipif(not ROM.exists(), reason="CPU_Test_10.pce not fetched"),
]


def splits(frame):
    xs = []
    for row in frame.rows[60:175]:
        changes = [x for x in range(40, 160) if row[x] != row[x - 1]]
        if changes:
            xs.append(changes[0])
    return sorted(xs)


def test_every_rom_group_draws_a_vertical_split_at_a_recorded_offset():
    pad = pads.Pad2()
    system = build(Board(card=RomCard.from_path(ROM), pad=pad))
    hardware = json.loads((ROOT / "covell_hardware_splits.json").read_text())[
        "groups_2_to_8_cycles_x_m"
    ]
    for _ in range(30):
        system.run_frame()
    for group in range(7):
        if group:
            pad.pressed = pads.RIGHT
            for _ in range(3):
                system.run_frame()
            pad.pressed = 0
            for _ in range(10):
                system.run_frame()
        xs = splits(system.board.capture.last_frame)
        assert len(xs) > 100
        assert xs[3 * len(xs) // 4] - xs[len(xs) // 4] <= 2  # vertical, like the photographs
        offset = statistics.median(xs) - 20 - hardware[group]  # in Mednafen columns
        assert -3 <= offset <= 8  # a coarse band (M1's registration); -8 dots default, docs/m1-record.md
