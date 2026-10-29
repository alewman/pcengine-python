#!/usr/bin/env python3
"""Instruction-stream lockstep of the board against MAME 0.285 or Mednafen 1.32.1 (tier 5 each).

    python scripts/lockstep.py mame     TRACE CARD.pce [--tg16] [--max N]
    python scripts/lockstep.py mednafen TRACE CARD.pce [--max N]

Neither referee is a judge: a first difference is a lead to name with its tier, not a verdict.
The run stops at the **first** difference in PC, A, X, Y, S, P (B left out: not a stored flag of
the core), MPR1-MPR4 or the clock since the first instruction, and prints the neighbourhood.

The traces (docs/mame-oracle.md; /data/emu/huc6280-python/scripts/mednafen_trace.py, whose binary
is used by `scripts/mednafen_record.py`) both log one line per instruction *before* it runs:

- MAME: `C PC A X Y S P totalcycles beamy beamx frame MPR1..MPR4` (hex, the clock and beam in
  decimal). MAME starts at beam line 260, ignores VCE bit 2 (263-line frames: the comparison only,
  `lines_follow_vce_bit2=False`), and its beam x = 0 is the end of the horizontal sync.
- Mednafen: `PC A X Y S P ticks` then `M MPR0..MPR7`; `[luaengine] R ...` lines (hardware-page
  reads) are skipped. No beam position. Its VCE starts at line 0 with the horizontal sync
  beginning at the first instruction (`hblank_counter = 237` at reset), it honours VCE bit 2, it
  always reports the TurboGrafx-16 country, it resets with S = 0 (not $FF) and MPR1-MPR6 = 0.

Experiments (off by default; each names what it overrides, to look behind a difference):

  --mame-csh --mame-blocks --mame-entry7 --mame-vertical   MAME's behaviour (docs/m1-record.md)
  --adopt-reset-s    Mednafen's S = 0 at reset (the core: $FF; random on hardware, U2)
  --resync-late      when the referee takes an interrupt entry one instruction before the board
                     does (the line was visible to it in time, to the board a cycle late), run
                     that instruction, enter, and carry on if all registers then equal the
                     referee's; the board's clock is then ahead by the instruction (`skew`), and
                     every resync is counted with the instruction it ran (U21, tier 5 vs 5)
  --adopt-power-on   Mednafen's power-on colour table (a checkerboard of $000/$1FF; the board's is
                     zeros, hardware's random: U7), for games that read the table before writing it
  --adopt-cd-sense   $1000 bit 7 clear (MAME reads it so with no CD unit; pcetech, Mednafen: set; C6)
  --adopt-timer-lag  show the timer interrupt to the CPU only when the referee enters it (see
                     TimerGate); the lags are reported
  --adopt-io-waits   add Mednafen's VDC/VCE wait states to the board's clock after an instruction
                     that touched $FF:0000-07FF (Mednafen's board model, U18; the board charges one
                     cycle); the count and the clocks adopted are reported
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, deque
from dataclasses import dataclass, replace
from pathlib import Path

from mame_lockstep import B_FLAG, RESET_CLOCKS, mame_core

from pcengine_python.board import Board
from pcengine_python.cards import RomCard
from pcengine_python.machine import (
    HSYNC_CLOCKS,
    LINE_CLOCKS,
    PC_ENGINE,
    TURBOGRAFX_16,
    Machine,
)
from pcengine_python.system import build

ZERO_PAGE_VIDEO = range(0x1FE000, 0x1FE800)  # VDC and VCE, as physical addresses


@dataclass(frozen=True)
class Line:
    pc: int
    a: int
    x: int
    y: int
    s: int
    p: int
    ticks: int
    beamy: int  # -1: the referee has no beam
    beamx: int
    mpr: tuple[int, ...]
    reads: tuple[tuple[int, int], ...] = ()  # (address, value) of the VDC/VCE reads it made

    def regs(self) -> tuple[int, ...]:
        return (self.pc, self.a, self.x, self.y, self.s, self.p & ~B_FLAG, *self.mpr)


def read_mame(path: Path):
    with path.open("rb") as log:
        for raw in log:
            if not raw.startswith(b"C "):
                continue
            f = raw.split()
            if len(f) != 15:
                continue
            h = [int(v, 16) for v in f[1:7]]
            ticks, beamy, beamx, _frame = (int(v) for v in f[7:11])
            yield Line(*h, ticks, beamy, beamx, tuple(int(v, 16) for v in f[11:15]))


def read_mednafen(path: Path):
    """Lines of the trace. The hardware-page reads logged after an instruction's line pair
    (`[luaengine] R addr value`) are attached to it as `reads` (VDC and VCE addresses only)."""
    first = None  # the instruction line, waiting for its MPR line
    cur = None  # the complete Line, collecting the reads that follow
    reads: list[tuple[int, int]] = []
    with path.open("rb") as log:
        for raw in log:
            c = raw[:1]
            if c == b"M":
                if first is not None:
                    m = raw.split()
                    cur = Line(*first, -1, -1, tuple(int(v, 16) for v in m[2:6]))
                    first = None
                    reads = []
            elif c == b"[":
                f = raw.split()
                if len(f) == 4 and int(f[2], 16) in ZERO_PAGE_VIDEO:
                    reads.append((int(f[2], 16), int(f[3], 16)))
            elif c in (b"\n", b""):
                continue
            else:
                f = raw.split()
                if len(f) == 7:
                    if cur is not None:
                        yield replace(cur, reads=tuple(reads))
                        cur = None
                    first = (*(int(v, 16) for v in f[:6]), int(f[6]))
        if cur is not None:
            yield replace(cur, reads=tuple(reads))


READERS = {"mame": read_mame, "mednafen": read_mednafen}


def make_system(referee: str, card_path: str, tg16: bool, args):
    """The board started as the referee starts. MAME: the first instruction runs at beam line 260,
    x = 0 (the end of the sync). Mednafen: line 0 begins (the sync with it) at the first
    instruction, which is the end of the core's start sequence."""
    if referee == "mame":
        machine: Machine = replace(
            PC_ENGINE if not tg16 else TURBOGRAFX_16, lines_follow_vce_bit2=False
        )
        start_line, start_offset = 260, HSYNC_CLOCKS - RESET_CLOCKS
    else:
        machine = TURBOGRAFX_16  # Mednafen's I/O port reports TG16 for every card
        start_line, start_offset = mednafen_start()
    if args.start_line is not None:
        start_line = args.start_line
    if args.start_offset is not None:
        start_offset = args.start_offset
    if args.raster_shift:
        # the raster N master clocks earlier against the CPU (an experiment: where in a cycle
        # the board's lines are seen, U21)
        start_offset += args.raster_shift
        start_line = (start_line + start_offset // LINE_CLOCKS) % 263
        start_offset %= LINE_CLOCKS
    board = Board(
        machine,
        card=RomCard.from_path(card_path),
        start_line=start_line,
        start_offset=start_offset,
        vblank_dots=args.vblank_dots,
        vertical_at_line_start=args.mame_vertical,
    )
    watch = (
        IoWatch(board) if args.adopt_io_waits or args.check_reads else None
    )  # before the core binds the methods
    custom = args.mame_csh or args.mame_blocks or args.mame_entry7
    system = build(
        board, mame_core(args.mame_csh, args.mame_blocks, args.mame_entry7) if custom else None
    )
    system.step()  # the start sequence; the first traced instruction is next
    assert board.mclk == RESET_CLOCKS
    if referee == "mednafen" and args.adopt_reset_s:
        system.cpu.s = 0
    if args.adopt_cd_sense:
        board.cpu_io.port._cd_attached = lambda: True  # D7 of $1000 clear, as MAME reads it (C6)
    if referee == "mednafen" and args.adopt_power_on:
        for i in range(512):  # [emu: Mednafen vce.cpp Reset] a checkerboard; the board's is zeros
            board.vce.palette[i] = 0 if (i ^ (i >> 3)) & 1 else 0x1FF
    gate = TimerGate(system.cpu, board) if args.adopt_timer_lag else None
    return system, watch, gate


class TimerGate:
    """Experiment (--adopt-timer-lag): the timer interrupt (TIQ) reaches the CPU only when the
    referee's trace shows it entering. Mednafen shows the timer's interrupt to the CPU later than
    the underflow (12 to ~300 ticks, variable); the board shows it at the underflow (pcetech 2.2).
    The lag from the board's assertion to the referee's entry is recorded."""

    def __init__(self, cpu, board: Board) -> None:
        self.board = board
        self.orig = cpu.set_irq_lines
        self.latest = (False, False, False)
        self.open = False
        self.rose = 0
        cpu.set_irq_lines = self.set

    def set(self, irq1: bool, irq2: bool, tiq: bool) -> None:
        if tiq and not self.latest[2]:
            self.rose = self.board.mclk
        self.latest = (irq1, irq2, tiq)
        self.orig(irq1, irq2, tiq and self.open)

    def let(self) -> int:
        self.open = True
        self.orig(*self.latest)
        return (self.board.mclk - self.rose) // 3

    def close(self) -> None:
        self.open = False
        self.orig(self.latest[0], self.latest[1], False)


def mednafen_start() -> tuple[int, int]:
    """Mednafen's VCE powers up in the vertical sync with 4095 + 30 clocks left (`vblank_counter`)
    and the horizontal sync begins at time zero (`hblank_counter = 237`); the first line (scanline
    0) starts 3 lines later, so the board's line 0 begins 4095 clocks after the first instruction,
    which is the end of the core's start sequence: time zero is 4095 + 84 clocks before line 0
    (a 262-line first frame: VCE bit 2 is clear at reset)."""
    before = 4095 + RESET_CLOCKS
    lines, rest = divmod(before, LINE_CLOCKS)
    return 262 - lines - (1 if rest else 0), (LINE_CLOCKS - rest) % LINE_CLOCKS


def ours(system) -> tuple[int, ...]:
    cpu = system.cpu
    return (cpu.pc, cpu.a, cpu.x, cpu.y, cpu.s, cpu.p & ~B_FLAG, *cpu.mpr[1:5])


def fmt(values) -> str:
    return " ".join(f"{v:02X}" if i else f"{v:04X}" for i, v in enumerate(values))


class IoWatch:
    """Notes whether the instruction in progress touched the VDC or the VCE (for --adopt-io-waits)."""

    def __init__(self, board: Board) -> None:
        self.touched = False
        self.reads: list[tuple[int, int]] = []  # (address, value) of this instruction's reads
        for name in ("read_byte", "write_byte"):
            original = getattr(board, name)
            is_read = name == "read_byte"

            def wrapped(address, *rest, _f=original, _read=is_read):
                result = _f(address, *rest)
                if address in ZERO_PAGE_VIDEO:
                    self.touched = True
                    if _read:
                        self.reads.append((address, result))
                return result

            setattr(board, name, wrapped)


def run(referee: str, trace: Path, card: str, args, tg16: bool) -> int:
    reader = READERS[referee]
    system, watch, gate = make_system(referee, card, tg16, args)
    board = system.board
    history: deque = deque(maxlen=args.context)
    rom = RomCard.from_path(card).data
    vectors = {rom[0x1FF6 + 2 * i] | rom[0x1FF7 + 2 * i] << 8 for i in range(3)}
    tiq_vector = rom[0x1FFA] | rom[0x1FFB] << 8
    if gate is not None and tiq_vector in {
        rom[0x1FF6] | rom[0x1FF7] << 8,
        rom[0x1FF8] | rom[0x1FF9] << 8,
    }:
        print("TIQ shares a vector with IRQ1/IRQ2: --adopt-timer-lag cannot tell them apart")
        gate = None
    lags: list[int] = []
    entries = adopted = adopted_clocks = late = read_diffs = 0
    waits: Counter = Counter()  # adopted wait states, by size in ticks
    late_at: Counter = Counter()  # instructions the board ran before an entry the referee took
    start_ticks = None
    start_mclk = board.mclk
    skew = 0  # ticks the board is ahead of the referee after a --resync-late (cumulative)
    step = system.step
    irq_changes: list[tuple[int, tuple[bool, bool, bool]]] = []  # for --probe: (mclk, lines)
    if args.probe:
        set_lines = system.cpu.set_irq_lines

        def logged_lines(irq1: bool, irq2: bool, tiq: bool) -> None:
            irq_changes.append((board.mclk, (irq1, irq2, tiq)))
            set_lines(irq1, irq2, tiq)

        system.cpu.set_irq_lines = logged_lines
    count = -1
    for count, line in enumerate(reader(trace)):
        if count >= args.max:
            break
        if start_ticks is None:
            start_ticks = line.ticks
        theirs = line.regs()
        mine = ours(system)
        if gate is not None and line.pc == tiq_vector and mine[0] != line.pc:
            lags.append(gate.let())
        if mine[0] != line.pc and line.pc in vectors:
            step()  # the interrupt entry is a step of its own in the core, a prefix in the logs
            entries += 1
            mine = ours(system)
            if gate is not None and gate.open:
                gate.close()
            if args.resync_late and mine[0] != line.pc:
                # the core did not see the interrupt in time: it ran one more instruction. One more
                # step enters; kept only if the registers then equal the referee's.
                ran = mine[0]
                step()
                if ours(system) == theirs:
                    late += 1
                    late_at[ran] += 1
                    skew = (board.mclk - start_mclk) // 3 - (line.ticks - start_ticks)
                    mine = ours(system)
        their_ticks = line.ticks - start_ticks
        raw = (board.mclk - start_mclk) // 3
        if skew and raw == their_ticks and mine == theirs:
            skew = 0  # the clocks agree again (a loop as long as the skew: the board is an
            # instruction ahead in the stream, and meets the referee's clock at the next entry)
        my_ticks = raw - skew
        if (
            watch is not None
            and watch.touched
            and mine == theirs
            and their_ticks > my_ticks
            and args.adopt_io_waits
        ):
            board.advance((their_ticks - my_ticks) * 3)
            adopted += 1
            if args.show_waits and their_ticks - my_ticks >= args.show_waits:
                print(
                    f"wait of {their_ticks - my_ticks} ticks adopted at #{count} pc {line.pc:04X}"
                )
            adopted_clocks += their_ticks - my_ticks
            waits[their_ticks - my_ticks] += 1
            my_ticks = their_ticks
        if mine != theirs or my_ticks != their_ticks:
            print("FIRST DIFFERENCE")
            for h in history:
                print(f"#{h[0]} {fmt(h[1])} t={h[2]}")
            beam = divmod(board.mclk - RESET_CLOCKS, LINE_CLOCKS)
            print(
                f"#{count} {referee} {fmt(theirs)} t={their_ticks} beam=({line.beamy},{line.beamx})"
                f"\n   ours {fmt(mine)} t={my_ticks} line+{beam[0]} x={beam[1]} (from start)"
            )
            print("differs in:", "registers" if mine != theirs else "clock")
            summary(count, entries, adopted, adopted_clocks, waits, late, late_at, skew, lags)
            return 1
        if args.context:
            history.append((count, theirs, their_ticks))
        if watch is not None:
            watch.touched = False
            watch.reads.clear()
        step()
        if args.check_reads and referee == "mednafen" and watch.reads != list(line.reads):
            read_diffs += 1
            if read_diffs <= 12:
                print(
                    f"READ DIFFERENCE at #{count} pc {line.pc:04X}: board "
                    f"{[(hex(a), hex(v)) for a, v in watch.reads]} {referee} "
                    f"{[(hex(a), hex(v)) for a, v in line.reads]}"
                )
        if args.probe and args.probe[0] <= count <= args.probe[1]:
            vdc = board.vdc
            sat_end = vdc.dma.sat_end
            print(
                f"probe #{count} next pc {fmt(ours(system))[:4]} t={(board.mclk - start_mclk) // 3} "
                f"sat_end={None if sat_end is None else (sat_end - start_mclk) // 3} "
                f"vdma={vdc.dma.running} bsy={vdc.bsy} {vdc.seq.vphase.name} "
                f"rcr={vdc.seq.rcr_count} status={vdc.status:02X} mclk={board.mclk - start_mclk} "
                f"irq={[(m - start_mclk, tuple(int(x) for x in v)) for m, v in irq_changes[-2:]]}"
            )
    n = count + 1
    print("no difference over the whole trace" if count < args.max else "stopped at --max")
    summary(n, entries, adopted, adopted_clocks, waits, late, late_at, skew, lags)
    return 0


def summary(n, entries, adopted, adopted_clocks, waits, late, late_at, skew, lags) -> None:
    print(
        f"{n:,} instructions equal, {entries:,} interrupt entries, {adopted:,} io-wait adoptions "
        f"({adopted_clocks:,} ticks), {late:,} late-visibility resyncs (skew {skew} ticks)"
    )
    if waits:
        print("adopted waits (ticks: count):", dict(sorted(waits.items())))
    if lags:
        s = sorted(lags)
        print(
            f"timer interrupts shown late by the referee: {len(s)}, lag in ticks "
            f"min {s[0]} median {s[len(s) // 2]} max {s[-1]}"
        )
    if late_at:
        print("instructions run before a late entry (pc: count):",
              {hex(k): v for k, v in sorted(late_at.items())})  # fmt: skip


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("referee", choices=sorted(READERS))
    ap.add_argument("trace", type=Path)
    ap.add_argument("card")
    ap.add_argument("--tg16", action="store_true", help="MAME ran the tg16 driver (US cards)")
    ap.add_argument("--max", type=int, default=10**9)
    ap.add_argument("--context", type=int, default=6)
    ap.add_argument(
        "--vblank-dots",
        type=lambda v: None if v == "mednafen" else int(v),
        default=-8,
        help="the board's vblank test position (default -8, U19); 'mednafen': the start of the "
        "display width, Mednafen's own",
    )
    ap.add_argument("--start-line", type=int)
    ap.add_argument("--start-offset", type=int)
    ap.add_argument("--raster-shift", type=int, default=0)
    ap.add_argument("--mame-csh", action="store_true")
    ap.add_argument("--mame-blocks", action="store_true")
    ap.add_argument("--mame-entry7", action="store_true")
    ap.add_argument("--mame-vertical", action="store_true")
    ap.add_argument("--adopt-reset-s", action="store_true")
    ap.add_argument("--adopt-io-waits", action="store_true")
    ap.add_argument("--adopt-power-on", action="store_true")
    ap.add_argument("--adopt-cd-sense", action="store_true")
    ap.add_argument("--adopt-timer-lag", action="store_true")
    ap.add_argument("--resync-late", action="store_true")
    ap.add_argument(
        "--show-waits",
        type=int,
        metavar="MIN",
        help="print each adopted wait state of MIN ticks or more, with its instruction index",
    )
    ap.add_argument(
        "--check-reads",
        action="store_true",
        help="also compare each instruction's VDC/VCE reads with the ones the Mednafen trace logs "
        "(the first 12 differences are printed, the run goes on)",
    )
    ap.add_argument(
        "--probe",
        type=int,
        nargs=2,
        metavar=("FROM", "TO"),
        help="print the board's VDC state (SAT transfer end, BSY, vertical phase, line counter) "
        "after each instruction with these indices",
    )
    args = ap.parse_args()
    return run(args.referee, args.trace, args.card, args, args.tg16)


if __name__ == "__main__":
    sys.exit(main())
