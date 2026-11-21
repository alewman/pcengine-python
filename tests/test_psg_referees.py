"""The PSG model against MAME's c6280 and Mednafen's PCE_PSG at the step rate (M4).

A 0.84 s excerpt of Alien Crush's register writes (tests/psg_logs, recorded by
scripts/psg_record.py) is replayed into the model and into the two referees, built from the pinned
sources by scripts/psg_referees/ (g++ and reference/ needed; skipped otherwise). With each
referee's own switches the model reproduces its step stream with no difference; Mednafen's
volume latch (C21) is excluded as in docs/m4-record.md. Every result is tier 5.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "tests/psg_logs/alien-crush-first-0.84s.psglog"
SOURCES = [
    ROOT / "reference/src/mame/src/devices/sound/c6280.cpp",
    ROOT / "reference/src/mednafen-pce-dev/mednafen/src/hw_sound/pce_psg/pce_psg.cpp",
]

#: The Mednafen referee is a GPL tool kept outside this repository (scripts/psg_referees/README.md).
GPL_TOOLS = os.environ.get("PCE_GPL_TOOLS")

np = pytest.importorskip("numpy")
pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        shutil.which("g++") is None or not all(p.exists() for p in SOURCES),
        reason="g++ or the pinned referee sources are missing",
    ),
    pytest.mark.skipif(GPL_TOOLS is None, reason="PCE_GPL_TOOLS (the Mednafen referee) is not set"),
]


@pytest.fixture(scope="module")
def compare(tmp_path_factory):
    out = tmp_path_factory.mktemp("psg_referees")
    builders = [ROOT / "scripts/psg_referees/build_mame.py"]
    builders.append(Path(GPL_TOOLS) / "psg_referees/build_mednafen.py")
    env = dict(os.environ, PCENGINE_PYTHON_ROOT=str(ROOT))
    for script in builders:
        subprocess.run([sys.executable, str(script), str(out)], check=True, env=env)
    sys.path.insert(0, str(ROOT / "scripts"))
    import psg_compare

    return psg_compare, out


def test_the_model_with_each_referees_switches_reproduces_its_step_stream(compare, tmp_path):
    psg_compare, out = compare
    steps = 3_000_000
    records = psg_compare.read_log(LOG)
    log = tmp_path / "referee.log"
    log.write_bytes(psg_compare.referee_log(records, steps))
    from pcengine_python.psg import VARIANTS

    mame = psg_compare.run_referee(out / "mame_c6280", log, steps, 0)
    medn = psg_compare.run_referee(out / "mednafen_psg", log, steps, 0, "0")
    state = psg_compare.our_states(records, 0, steps, dict(VARIANTS["mame"]))
    assert (psg_compare.mame_profile(*state, 31) == mame).all()
    state = psg_compare.our_states(records, 0, steps, dict(VARIANTS["mednafen"]))
    settle = psg_compare.settle_mask(records, 0, steps, 9000)
    differs = (psg_compare.mednafen_profile(*state, 0, 31) != medn).any(axis=1) & ~settle
    assert not differs.any()
    assert settle.sum() < steps // 2  # the exclusion leaves most of the stream compared
