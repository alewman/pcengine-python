# SPDX-License-Identifier: MIT
"""Find a family tool at its documented path (emu-tools docs/contract.md, section 5).

One variable per tool repository (Aubrey, 2026-11-24): ``EMU_TOOLS`` (MIT emu-tools),
``EMU_TOOLS_GPL`` (emu-tools-gpl) and ``EMU_TOOLS_GPL2`` (emu-tools-gpl2). Each tool sits at a
fixed path under its repository, listed in that repository's ``tools/README.md``. The tools are
run as separate programs; nothing here imports them.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: The Mesen2 runner on the contract (machine ``pce``; ``--no-sprites`` and ``--input`` from
#: mesen2-runner 0.2.0). The old pcengine-python command line, a shim at
#: ``tools/pcengine-python/mesen_run.py``, is no longer used here (2026-11-24).
MESEN2_RUN = ("EMU_TOOLS_GPL", "tools/mesen2/run.py")
#: The Mednafen PSG referee's build script (not regrouped yet).
MEDNAFEN_PSG_BUILD = ("EMU_TOOLS_GPL", "tools/pcengine-python/psg_referees/build_mednafen.py")


def find(tool: tuple[str, str]) -> Path | None:
    """The tool's path, or None when its variable is unset or the file is absent."""
    var, rel = tool
    root = os.environ.get(var)
    if not root:
        return None
    path = Path(root) / rel
    return path if path.exists() else None


def require(tool: tuple[str, str]) -> Path:
    """The tool's path; exit status 3 (a missing input, as the contract says) without it."""
    path = find(tool)
    if path is None:
        print(why_missing(tool), file=sys.stderr)
        sys.exit(3)
    return path


def why_missing(tool: tuple[str, str]) -> str:
    """The message (and test skip reason) naming the variable and the path expected."""
    return f"${tool[0]}/{tool[1]} not found: set {tool[0]} (emu-tools docs/contract.md, section 5)"
