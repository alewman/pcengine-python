"""scripts/presses.py: the scripted pad input the picture scripts share."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import presses

from pcengine_python import pads


def test_a_press_holds_its_buttons_for_its_frames_only():
    script = presses.parse(["run@400+10", "right-ii@405"])
    assert presses.held(script, 399) == frozenset()
    assert presses.held(script, 400) == {"run"}
    assert presses.held(script, 405) == {"run", "right", "ii"}
    assert presses.held(script, 406) == {"run"}
    assert presses.held(script, 410) == frozenset()


def test_the_board_mask_and_the_detectors_spellings_name_the_same_buttons():
    assert presses.board_mask(frozenset({"run", "ii", "left"})) == pads.RUN | pads.II | pads.LEFT
    assert presses.LIBRETRO["run"] == 3 and presses.LIBRETRO["i"] == 8  # START, A
    lua = presses.mesen_lua(presses.parse(["run@400+10"]))
    assert "{400, 410, {run = true}}" in lua and "emu.setInput(down, 0, 0)" in lua
    assert presses.mesen_lua([]) == ""


@pytest.mark.parametrize("spec", ["start@400", "run", "run@x", "run@4+y"])
def test_a_bad_press_is_refused(spec):
    with pytest.raises(SystemExit):
        presses.parse([spec])
