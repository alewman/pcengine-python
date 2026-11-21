#!/usr/bin/env python3
"""Summarise scripts/m5_sweep.py's JSON lines: one row per card, counts per class.

    python3 scripts/m5_summary.py RESULTS.jsonl [--table]

Class per card (worst of the two frames, 300 and 600), by the comparison with Mesen2 (sprites on):
IDENTICAL  every row equal to Mesen2 at both frames;
NEAR       at least 0.99 of the rows equal at both;
DIFFERENT  less; ERROR  the run failed. The Beetle share of equal rows is printed alongside.
"""

import argparse
import collections
import json
from pathlib import Path


def cls(rows: float) -> str:
    return "IDENTICAL" if rows >= 1.0 else "NEAR" if rows >= 0.99 else "DIFFERENT"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("results", type=Path)
    p.add_argument("--table", action="store_true")
    a = p.parse_args()
    cards: dict[str, list[dict]] = collections.defaultdict(list)
    for line in a.results.read_text().splitlines():
        if line:
            r = json.loads(line)
            cards[r["card"]].append(r)
    counts = collections.Counter()
    lines = []
    for name, rs in sorted(cards.items()):
        if any("error" in r for r in rs) or not rs:
            counts["ERROR"] += 1
            lines.append(f"{name}\tERROR\t{rs[0].get('error')}")
            continue
        m = [(r["mesen"] or {}).get("rows", 0.0) for r in rs]
        b = [(r["beetle"] or {}).get("rows", 0.0) for r in rs]
        k = cls(min(m))
        counts[k] += 1
        first = [(r["mesen"] or {}).get("first") for r in rs]
        lines.append(
            f"{name}\t{k}\tmesen rows {'/'.join(f'{x:.3f}' for x in m)}\t"
            f"beetle rows {'/'.join(f'{x:.3f}' for x in b)}\tfirst {first}\t{rs[0]['ours_seconds']} s"
        )
    if a.table:
        print("\n".join(lines))
    print(dict(counts), "of", len(cards))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
