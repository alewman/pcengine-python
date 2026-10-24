#!/usr/bin/env python3
"""Instruction-stream lockstep of the board against MAME 0.285's trace (a detector, tier 5).

    python scripts/mame_lockstep.py TRACE_ERROR_LOG CARD.pce [--max N] [--context K]

MAME's `error.log` (scripts/mame_trace.py) holds one line per instruction *before* it runs:
`C PC A X Y S P totalcycles beamy beamx frame MPR1 MPR2 MPR3 MPR4` (hex, except the decimal
totalcycles/beamy/beamx/frame). `totalcycles` counts 7.16 MHz ticks (3 master clocks each).

The board starts as MAME's does: 263-line frames (MAME ignores VCE bit 2: the comparison only),
time zero placed so that the first instruction runs at beam line 260, clock 0. Nothing is masked
or adopted: the run stops at the **first** difference in PC, A, X, Y, S, P (B read as set, as
pcetech says it always is), MPR1-MPR4, or the clock since the first instruction, and prints the
neighbourhood of both streams. The first difference is a lead, not a verdict (MAME is tier 5).
"""

from __future__ import annotations

import argparse
import sys
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path

from pcengine_python.board import Board
from pcengine_python.cards import RomCard
from pcengine_python.machine import HSYNC_CLOCKS, LINE_CLOCKS, PC_ENGINE
from pcengine_python.system import build

# B is not a stored flag of the core; MAME shows it set normally and clear inside an interrupt
# handler, pcetech says it always reads set: it is left out of the comparison (named, not hidden).
B_FLAG = 0x10
RESET_CLOCKS = 7 * 12  # the core's start sequence: five internal cycles and two vector reads


@dataclass(frozen=True)
class Line:
    pc: int
    a: int
    x: int
    y: int
    s: int
    p: int
    ticks: int
    beamy: int
    beamx: int
    frame: int
    mpr: tuple[int, ...]

    def regs(self) -> tuple[int, ...]:
        return (self.pc, self.a, self.x, self.y, self.s, self.p & ~B_FLAG, *self.mpr)


def read_trace(path: Path):
    with path.open("rb") as log:
        for raw in log:
            if not raw.startswith(b"C "):
                continue
            f = raw.split()
            if len(f) != 15:
                continue
            h = [int(v, 16) for v in f[1:7]]
            ticks, beamy, beamx, frame = (int(v) for v in f[7:11])
            yield Line(*h, ticks, beamy, beamx, frame, tuple(int(v, 16) for v in f[11:15]))


def mame_core(speed: bool, blocks: bool, entry7: bool = False):
    """HuC6280 with MAME's behaviour where MAME and the core's defaults differ, to see what lies
    behind a difference. Experiments, never the default:

    - speed (C7): CSL/CSH take effect *after* the instruction (the core: for its last cycle);
    - entry7 (C3): an interrupt entry takes 7 cycles (the core's default is 8);
    - blocks (C14): a block transfer keeps A, X and Y in the CPU and writes nothing to the stack
      (the core: Mesen's and Mednafen's push of Y, A, X and pop, as Hudson's manual HB-6 says)."""
    from huc6280 import HuC6280

    class MameLike(HuC6280):
        interrupt_entry_cycles = 7 if entry7 else 8  # C3: MAME 7, the others 8

        def _speed(self, high: bool) -> None:
            if not speed:
                return super()._speed(high)
            self._implied()
            self._io()
            self.high_speed = high

        def _transfer(self, source_steps, destination_steps) -> None:
            if not blocks:
                return super()._transfer(source_steps, destination_steps)
            saved = (self.a, self.x, self.y)
            self._implied()
            self._io()
            for _ in range(3):
                self._io()  # where the three pushes would be
            source = self._fetch_word()
            destination = self._fetch_word()
            length = self._fetch_word() or 0x10000
            self._io()
            for index in range(length):
                self._io()
                value = self._block_read(source)
                self._io()
                self._cycle_write(destination, value)
                self._io()
                self._io()
                source = (source + source_steps[index % len(source_steps)]) & 0xFFFF
                destination = (
                    destination + destination_steps[index % len(destination_steps)]
                ) & 0xFFFF
            self._io()
            for _ in range(3):
                self._io()
            self.a, self.x, self.y = saved

    return MameLike


def make_system(
    card_path: str,
    speed: bool = False,
    blocks: bool = False,
    vblank_dots: int | None = None,
    mame_vertical: bool = False,
    entry7: bool = False,
):
    machine = replace(PC_ENGINE, lines_follow_vce_bit2=False)
    board = Board(
        machine,
        card=RomCard.from_path(card_path),
        # MAME's beam x = 0 is the *end* of the horizontal sync (huc6260.cpp: v++ at "End of
        # HSync"), which is HSYNC_CLOCKS after our line start: put that moment at the end of the
        # reset sequence, on line 260.
        start_line=260,
        start_offset=HSYNC_CLOCKS - RESET_CLOCKS,
        vblank_dots=vblank_dots,
        vertical_at_line_start=mame_vertical,
    )
    system = build(board, mame_core(speed, blocks, entry7) if speed or blocks or entry7 else None)
    system.step()  # the start sequence; the first traced instruction is next
    assert board.mclk == RESET_CLOCKS
    return system


def ours(system) -> tuple[int, ...]:
    cpu = system.cpu
    return (cpu.pc, cpu.a, cpu.x, cpu.y, cpu.s, cpu.p & ~B_FLAG, *cpu.mpr[1:5])


def fmt(values) -> str:
    return " ".join(f"{v:02X}" if i else f"{v:04X}" for i, v in enumerate(values))


def run(
    trace: Path,
    card: str,
    limit: int,
    context: int,
    speed=False,
    blocks=False,
    vblank=None,
    mame_vertical=False,
    entry7=False,
) -> int:
    system = make_system(card, speed, blocks, vblank, mame_vertical, entry7)
    board = system.board
    history: deque[str] = deque(maxlen=context)
    rom = RomCard.from_path(card).data
    vectors = {rom[0x1FF6 + 2 * i] | rom[0x1FF7 + 2 * i] << 8 for i in range(3)}  # IRQ2 IRQ1 TIQ
    entries = 0
    start_ticks = None
    start_mclk = board.mclk
    for count, line in enumerate(read_trace(trace)):
        if count >= limit:
            print(
                f"{count} instructions, {entries} interrupt entries: "
                "no difference (all registers and clocks equal)"
            )
            return 0
        if start_ticks is None:
            start_ticks = line.ticks
        theirs = line.regs()
        if ours(system)[0] != line.pc and line.pc in vectors:
            # MAME logs an instruction *after* the interrupt entry that precedes it; the core's
            # entry is a step of its own. The core decided to take it (its poll); the stream is
            # compared once the entry has run, and the entry is counted.
            system.step()
            entries += 1
        mine = ours(system)
        my_ticks = (board.mclk - start_mclk) // 3
        their_ticks = line.ticks - start_ticks
        beam = divmod(board.mclk - RESET_CLOCKS, LINE_CLOCKS)  # from the end of line 260's sync
        mine_beam = ((260 + beam[0]) % 263, beam[1])
        text = (
            f"#{count} MAME {fmt(theirs)} t={their_ticks} beam=({line.beamy},{line.beamx})"
            f"\n   ours {fmt(mine)} t={my_ticks} beam={mine_beam}"
        )
        if mine != theirs or my_ticks != their_ticks:
            print("FIRST DIFFERENCE")
            print("\n".join(history))
            print(text)
            what = "registers" if mine != theirs else "clock"
            print(f"differs in: {what}")
            # a few more of MAME's lines for context
            return 1
        history.append(text)
        system.step()
    print(f"trace ended after {count + 1} instructions, {entries} entries: no difference")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("trace", type=Path)
    ap.add_argument("card")
    ap.add_argument("--max", type=int, default=10**9)
    ap.add_argument("--context", type=int, default=6)
    ap.add_argument("--mame-csh", action="store_true", help="MAME's CSL/CSH timing (experiment)")
    ap.add_argument(
        "--mame-blocks", action="store_true", help="MAME's block transfers (experiment)"
    )
    ap.add_argument(
        "--vblank-dots", type=int, default=0, help="vblank test N dots after the sync (default 0)"
    )
    ap.add_argument(
        "--mame-vertical", action="store_true", help="MAME's vertical stepping (experiment)"
    )
    ap.add_argument(
        "--mame-entry7", action="store_true", help="7-cycle interrupt entry (experiment)"
    )
    args = ap.parse_args()
    return run(
        args.trace,
        args.card,
        args.max,
        args.context,
        args.mame_csh,
        args.mame_blocks,
        args.vblank_dots,
        args.mame_vertical,
        args.mame_entry7,
    )


if __name__ == "__main__":
    sys.exit(main())
