"""Scripted pad input shared by the picture scripts: one spelling for the board and the detectors.

A press is `BUTTONS@FRAME+HOLD`: the buttons (joined with `-`) are held on pad 1 while the count
of completed frames is in FRAME .. FRAME+HOLD-1 (`+HOLD` omitted = 1 frame). Buttons: `up`, `down`,
`left`, `right`, `i`, `ii`, `select`, `run`. Example: `run@450+20`, `right-ii@900+60`.

Emulators differ by a few frames from power-on to the first picture, so a press lands a few frames
apart in each; the comparison's frame window absorbs that for a game that does not depend on the
exact frame of a press, and cannot for one that does (a random seed taken from the frame counter).
"""

from __future__ import annotations

NAMES = ("up", "down", "left", "right", "i", "ii", "select", "run")
# libretro joypad ids (RETRO_DEVICE_ID_JOYPAD_*): B 0, SELECT 2, START 3, UP 4, DOWN 5, LEFT 6,
# RIGHT 7, A 8. Beetle PCE maps I to A and II to B, RUN to START.
LIBRETRO = {"ii": 0, "select": 2, "run": 3, "up": 4, "down": 5, "left": 6, "right": 7, "i": 8}

Press = tuple[frozenset[str], int, int]  # buttons, first frame, frames held


def parse(specs: list[str]) -> list[Press]:
    out = []
    for spec in specs:
        buttons, _, when = spec.partition("@")
        start, _, hold = when.partition("+")
        names = frozenset(buttons.lower().split("-"))
        if not names <= set(NAMES) or not start.isdigit() or (hold and not hold.isdigit()):
            raise SystemExit(f"bad press {spec!r}: BUTTONS@FRAME+HOLD, buttons {', '.join(NAMES)}")
        out.append((names, int(start), int(hold or 1)))
    return out


def held(presses: list[Press], frame: int) -> frozenset[str]:
    """The buttons down while `frame` frames have completed."""
    down: set[str] = set()
    for names, start, hold in presses:
        if start <= frame < start + hold:
            down |= names
    return frozenset(down)


def board_mask(names: frozenset[str]) -> int:
    """The buttons as pcengine_python.pads' host-side mask."""
    from pcengine_python import pads

    bits = {"up": pads.UP, "down": pads.DOWN, "left": pads.LEFT, "right": pads.RIGHT,
            "i": pads.I, "ii": pads.II, "select": pads.SELECT, "run": pads.RUN}  # fmt: skip
    mask = 0
    for name in names:
        mask |= bits[name]
    return mask


def mesen_lua(presses: list[Press]) -> str:
    """Lua for Mesen2: sets pad 1 at every input poll; `frames` is the script's frame counter."""
    if not presses:
        return ""
    rows = ", ".join(
        "{" + f"{start}, {start + hold}, " + "{" + ", ".join(f"{n} = true" for n in sorted(names))
        + "}}" for names, start, hold in presses
    )  # fmt: skip
    return (
        f"local presses = {{{rows}}}\n"
        "emu.addEventCallback(function()\n"
        "  local down = {}\n"
        "  for _, p in ipairs(presses) do\n"
        "    if frames >= p[1] and frames < p[2] then\n"
        "      for k, v in pairs(p[3]) do down[k] = v end\n"
        "    end\n"
        "  end\n"
        "  emu.setInput(down, 0, 0)\n"
        "end, emu.eventType.inputPolled)\n"
    )
