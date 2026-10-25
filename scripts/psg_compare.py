#!/usr/bin/env python3
"""Replay a recorded PSG register log into this model and into MAME's c6280 and Mednafen's PCE_PSG,
and compare the step streams (M4). Every result is tier 5: there is no hardware audio reference.

    python scripts/psg_compare.py LOG.psglog [--start S] [--steps N] [--set name=value ...]
                                  [--bin DIR] [--revision 0|1]

LOG is `scripts/psg_record.py`'s file (master clock, register, value). The referees are the
pinned sources compiled unchanged against small shims (scripts/psg_referees/, built by build_*.py
into DIR); they run from power-on over the whole log up to step S+N and give one (left, right)
integer per PSG step (3.58 MHz) from S on. This model's per-channel digital state (sample 0-31 or
off, attenuation in 1.5 dB units a side) is put through each referee's own numeric curve (MAME's
volume table and sample - 16; Mednafen's dbtable, HuC6280 or 6280A centring), so that equal digital
state means equal integers: a difference is a difference of *behaviour* (the sample, the timing,
the attenuation), not of scale. Writes apply at the step their master clock falls in (clock // 6)
for all three. Needs numpy.
"""

from __future__ import annotations

import argparse
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from pcengine_python.psg import VARIANTS, Psg

ROOT = Path(__file__).resolve().parents[1]


def read_log(path: Path) -> list[tuple[int, int, int]]:
    data = path.read_bytes()
    return [struct.unpack_from("<IBB", data, i) for i in range(0, len(data) - 5, 6)]


def only_channel(records, keep: int):
    """The same log with every other channel switched off (R4's ON bit cleared), so that one
    channel's behaviour can be compared alone; R0 is tracked to know whose R4 a write is."""
    out, select = [], 0
    for mclk, reg, value in records:
        if reg == 0:
            select = value & 7
        if reg == 4 and select != keep:
            value &= 0x7F
        out.append((mclk, reg, value))
    return out


def referee_log(records, stop: int) -> bytes:
    return b"".join(
        struct.pack("<IBB", mclk // 6, reg, value)
        for mclk, reg, value in records
        if mclk // 6 < stop
    )


def run_referee(binary: Path, log: Path, steps: int, start: int, *extra: str) -> np.ndarray:
    with tempfile.NamedTemporaryFile(suffix=".out", delete=False) as out:
        name = out.name
    subprocess.run([str(binary), str(log), name, str(steps), *extra, str(start)], check=True)
    data = np.fromfile(name, dtype="<i4").reshape(-1, 2)
    Path(name).unlink()
    return data


def our_states(records, start: int, steps: int, flags: dict[str, object]):
    """Arrays (6, n) of sample (-1 off), units left, units right for steps start..start+steps."""
    psg = Psg()
    psg.render_audio = False
    for name, value in flags.items():
        setattr(psg, name, value)
    n = steps
    sample = np.full((6, n), -1, dtype=np.int16)
    ul = np.zeros((6, n), dtype=np.int16)
    ur = np.zeros((6, n), dtype=np.int16)

    def listener(length: int, state) -> None:
        a = max(psg.step, start)
        b = min(psg.step + length, start + n)
        if b <= a:
            return
        for ch, (s, left, right) in enumerate(state):
            sample[ch, a - start : b - start] = s
            ul[ch, a - start : b - start] = left
            ur[ch, a - start : b - start] = right

    psg.listeners.append(listener)
    for mclk, reg, value in records:
        if mclk // 6 >= start + n:
            break
        psg.write(reg, value, mclk)
    psg.advance_to(start + n)
    return sample, ul, ur


def mame_profile(sample, ul, ur, silent=30):
    """MAME c6280: u16-truncated 1.5 dB table, sum of table[units] * (sample - 16)."""
    level = 65535.0 / 6.0 / 32.0
    table = np.zeros(32, dtype=np.int64)
    for i in range(31):
        table[i] = np.int16(int(level))
        level /= 10 ** (1.5 / 20)
    out = []
    for units in (ul, ur):
        index = np.where(units >= silent, 31, units)  # C14: where the channel goes silent
        out.append(
            (np.where(sample >= 0, table[index] * (sample.astype(np.int64) - 16), 0)).sum(axis=0)
        )
    return np.stack(out, axis=1)


def mednafen_profile(sample, ul, ur, revision: int, silent=30):
    table = np.zeros((32, 32), dtype=np.int64)
    for vl in range(32):
        flub = 1.0 * 8 / 6
        if vl:
            flub /= 2 ** (vl / 4)
        if vl == 0x1F:
            flub = 0
        for s in range(32):
            eff = s * 2 if revision == 0 else s * 2 - 0x1F
            table[vl, s] = int(flub * eff * 128)
    out = []
    for units in (ul, ur):
        index = np.where(units >= silent, 31, units)  # C14: where the channel goes silent
        out.append(np.where(sample >= 0, table[index, np.maximum(sample, 0)], 0).sum(axis=0))
    return np.stack(out, axis=1)


def settle_mask(records, start: int, steps: int, settle: int) -> np.ndarray:
    """True for steps within `settle` steps after a write to R1, R4 or R5 (the registers that set
    the volume): Mednafen applies those through a rotating latch that takes up to ~3,000 steps
    (its Update(): vol_update_which), which this model does not have (C21); those steps are left out
    of the Mednafen comparison and counted."""
    mask = np.zeros(steps, dtype=bool)
    for mclk, reg, _ in records:
        step = mclk // 6
        if reg in (1, 4, 5) and step < start + steps:
            mask[max(step - start, 0) : max(step + settle - start, 0)] = True
    return mask


def report(name: str, ours: np.ndarray, theirs: np.ndarray, start: int, state, ignore=None) -> None:
    n = len(ours)
    bad = (ours != theirs).any(axis=1)
    if ignore is not None:
        print(f"{name}: {int(ignore.sum())} of {n} steps excluded (volume settling)")
        bad = bad & ~ignore
    differ = np.flatnonzero(bad)
    if not len(differ):
        print(f"{name}: 0 differences in {n} steps")
        return
    first = int(differ[0])
    print(
        f"{name}: {len(differ)} of {n} steps differ ({100 * len(differ) / n:.2f} %); first at step "
        f"{start + first} ({(start + first) / 3_579_545:.4f} s): ours {ours[first].tolist()} "
        f"theirs {theirs[first].tolist()}"
    )
    sample, ul, ur = state
    print(
        "   our state there (sample, units L/R): "
        + ", ".join(f"ch{c + 1} {sample[c, first]},{ul[c, first]}/{ur[c, first]}" for c in range(6))
    )
    # the run of consecutive differing steps that starts at the first
    run = 1
    while first + run < n and (ours[first + run] != theirs[first + run]).any():
        run += 1
    print(f"   that stretch lasts {run} step(s); differing steps in 10k-step blocks: "
          f"{len(set(int(d) // 10000 for d in differ))} of {n // 10000 + 1}")  # fmt: skip


def between_referees(records, start: int, steps: int) -> None:
    """MAME and Mednafen against each other. Their integers are on different scales, so the two
    variants of this model (which reproduce each exactly) are compared on the digital state:
    the first step where they differ, and how many steps differ when each disputed switch alone is
    flipped from Mednafen's value to MAME's."""
    mame, medn = dict(VARIANTS["mame"]), dict(VARIANTS["mednafen"])
    a = our_states(records, start, steps, medn)
    b = our_states(records, start, steps, mame)
    differ = [(x != y).any(axis=0) for x, y in zip(a, b, strict=True)]
    bad = np.logical_or.reduce(differ)
    if not bad.any():
        print("MAME vs Mednafen: the two variants agree on every step")
        return
    first = int(np.flatnonzero(bad)[0])
    channel = next(
        c for c in range(6) if any(d[first] for d in [(a[0][c] != b[0][c]), (a[1][c] != b[1][c])])
    )
    print(
        f"MAME vs Mednafen: {int(bad.sum())} of {steps} steps differ; first at step {start + first} "
        f"(channel {channel + 1}: sample {a[0][channel][first]} against {b[0][channel][first]}, units "
        f"{a[1][channel][first]} against {b[1][channel][first]})"
    )
    for name in sorted(k for k in medn if medn.get(k) != mame.get(k, getattr(Psg, k))):
        flipped = dict(medn)
        flipped[name] = mame.get(name, getattr(Psg, name))
        c = our_states(records, start, steps, flipped)
        n = int(
            np.logical_or.reduce([(x != y).any(axis=0) for x, y in zip(c, b, strict=True)]).sum()
        )
        print(f"   with only {name} = {flipped[name]!r} (MAME's) {n} steps still differ")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("log", type=Path)
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--steps", type=int, default=1_000_000)
    p.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
    p.add_argument(
        "--bin",
        type=Path,
        required=True,
        help="where build_mame.py/build_mednafen.py put the harnesses",
    )
    p.add_argument("--revision", type=int, default=0)
    p.add_argument(
        "--drop",
        action="append",
        default=[],
        help="revert this switch of the referee's variant to the manual's default",
    )
    p.add_argument("--variant-only", action="store_true", help="skip the manual-defaults runs")
    p.add_argument("--referee", choices=("mame", "mednafen"), help="one referee only")
    p.add_argument(
        "--between", action="store_true", help="MAME against Mednafen (the two variants)"
    )
    p.add_argument("--only", type=int, help="channel 1-6 alone (the others' ON bits cleared)")
    p.add_argument(
        "--settle",
        type=int,
        default=0,
        help="exclude this many steps after a volume write (Mednafen)",
    )
    a = p.parse_args()
    records = read_log(a.log)
    if a.only:
        records = only_channel(records, a.only - 1)
    stop = a.start + a.steps
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
        f.write(referee_log(records, stop))
        log = Path(f.name)
    try:
        mame = run_referee(a.bin / "mame_c6280", log, stop, a.start)
        medn = run_referee(a.bin / "mednafen_psg", log, stop, a.start, str(a.revision))
    finally:
        log.unlink()
    print(f"{a.log.name}: steps {a.start}..{stop} of {len(records)} writes")
    if a.between:
        between_referees(records, a.start, a.steps)
        return 0
    ignore = settle_mask(records, a.start, a.steps, a.settle) if a.settle else None
    for referee, theirs in (("mame", mame), ("mednafen", medn)):
        if a.referee and a.referee != referee:
            continue
        for label in ("manual", referee):
            if a.variant_only and label == "manual":
                continue
            flags = dict(VARIANTS[label])
            for name in a.drop:
                flags.pop(name, None)
            flags.update({k: type_of(v) for k, v in (s.split("=", 1) for s in a.set)})
            state = our_states(records, a.start, a.steps, flags)
            if referee == "mame":
                ours = mame_profile(*state, flags.get("silent_units", 30))
            else:
                ours = mednafen_profile(*state, a.revision, flags.get("silent_units", 30))
            report(
                f"ours[{label}] vs {referee}", ours, theirs, a.start, state,
                ignore if referee == "mednafen" else None,
            )  # fmt: skip
    return 0


def type_of(text: str):
    if text in ("True", "False"):
        return text == "True"
    return int(text)


if __name__ == "__main__":
    sys.exit(main())
