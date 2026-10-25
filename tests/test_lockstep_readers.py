"""scripts/lockstep.py's two trace readers (no referee is run)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lockstep import read_mame, read_mednafen


def test_mednafen_reader_pairs_lines_and_skips_io_reads(tmp_path):
    log = tmp_path / "error.log"
    log.write_text(
        "E000 0 0 0 0 4 0\nM 0 0 0 0 0 0 0 0\n"
        "[luaengine] R 1FE000 20\n\n"
        "E001 1 2 3 FF 14 8\nM 0 F8 0 0 1 0 0 0\n"
    )
    lines = list(read_mednafen(log))
    assert [(x.pc, x.a, x.x, x.y, x.s, x.p, x.ticks) for x in lines] == [
        (0xE000, 0, 0, 0, 0, 4, 0),
        (0xE001, 1, 2, 3, 0xFF, 0x14, 8),
    ]
    assert lines[1].mpr == (0xF8, 0, 0, 1)
    assert lines[1].beamy == -1


def test_mame_reader_reads_the_c_lines(tmp_path):
    log = tmp_path / "error.log"
    log.write_text("noise\nC E000 0 0 0 FF 14 0 260 0 0 0 0 0 0\n")
    (line,) = read_mame(log)
    assert (line.pc, line.s, line.p, line.ticks, line.beamy) == (0xE000, 0xFF, 0x14, 0, 260)
