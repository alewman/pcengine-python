"""scripts/m5_sweep.py's frame choice: ties on the sampled score go to the exact picture."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("PIL")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from m5_sweep import best_frame_exact  # noqa: E402


def test_a_flat_picture_does_not_let_a_near_frame_win_on_the_sample():
    # A mostly flat picture: the sampled score (every third pixel) is 1.0 for the exact frame and
    # for a frame that differs in pixels the sample skips (Formation Soccer at 300, M5 record).
    ours = np.zeros((60, 120), dtype=np.uint16)
    ours[10, 10:40] = 7
    near = ours.copy()
    near[10, 11] = 0  # the sample (every third pixel) misses columns 11 and 14 ...
    near[10, 14] = 0  # ... of a flat row, so both frames score 1.0 on it
    frames = {297: near, 300: ours}
    (_, dx, dy), n = best_frame_exact(frames, ours, range(0, 4), range(0, 1), ())
    assert (n, dx, dy) == (300, 0, 0)
