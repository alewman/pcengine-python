<!-- SPDX-License-Identifier: MIT -->
# PSG referees

Two small C++ harnesses (one of them now kept outside this repository) that compile another emulator's PSG unchanged and drive it step by step
from a register log, so `scripts/psg_compare.py` can compare this board's PSG with them
(docs/m4-record.md). They are **tools**, outside the MIT `pcengine_python` package: nothing under
`src/` uses them, and the board installs and runs without them.

## The Mednafen referee: a GPL tool, outside this repository

`mednafen_psg.cpp`, `mednafen_shim/` and `build_mednafen.py` are compiled together with
Mednafen's `pce_psg.cpp` (GPL-2.0-or-later) into a GPL program. They left this repository on
2026-11-21, with its history reset (docs/provenance.md), and are kept with the family's other
GPL tools; `tests/test_psg_referees.py` builds the referee with
`$EMU_TOOLS_GPL/tools/pcengine-python/psg_referees/build_mednafen.py` and skips, naming the
variable, without it. Running the referee is closed-box use: its outputs are
measurements, and no code of it enters the board.

## The MAME referee: MIT harness over a BSD-3-Clause file

`mame_c6280.cpp` and `mame_shim/emu.h` are our own MIT text, compiled with MAME 0.285's
`src/devices/sound/c6280.cpp` (BSD-3-Clause, copyright Charles MacDonald; the notice is in
`NOTICE.md`), read from the reference tree, never copied here.

`build_mame.py` is MIT: it only runs `g++`.
