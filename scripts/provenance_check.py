#!/usr/bin/env python3
"""Provenance check: is anything in a repository copied or transcribed from a reference tree?

    python3 -I scripts/provenance_check.py --repo . [--repo ../other ...] --reference reference/src
        [--reference ../core/reference/src ...] [--report out.md] [--licences scripts/pinned_repos.json ...]

The family reads GPL and LGPL emulators (Mednafen, Mesen2, Geargrafx, parts of MAME, MiSTer cores) as
*detectors* and cites them; it must never contain their code, copied or transcribed into another
language. This script looks for the traces a copy or a transcription leaves, between every tracked
text file of each `--repo` and every source file under each `--reference`:

1. **prose**: eight consecutive words of a reference file's comments or strings in one of our
   files (a transcription usually carries its comments along);
2. **code**: a run of fourteen tokens with the same shape, across languages: numbers are compared
   by value, punctuation that only one language has (`;`, braces, `self.`, type names) is dropped,
   and the run must hold at least two numbers, three arithmetic or comparison operators and two
   names spelled the same on both sides (one, with four numbers). So a run of `name = 0`
   initialisers is not a hit and `tmp = (A & 0x0F) + (x & 0x0F) + (P & 1)` is. This is the test
   that found the one transcription the family had (huc6280-python's decimal `ADC`, 2026-11-12);
3. **tables**: eight consecutive numeric literals with the same values (six distinct, not a count
   or a row of bit masks);
4. **quotes**: a reference source line (30 characters or more of code) reproduced in our
   documentation, which is where a quoted excerpt lives.

A hit is a place to **read**, not a verdict: a table of what a chip does (an ADPCM step table from
a datasheet) is the same numbers in every implementation, and a short quoted excerpt with its
source named is a citation. What the script cannot see is a transcription that was also
restructured and renamed throughout; the review of the files that say they follow an emulator
(`grep -n "Mednafen\\|Mesen\\|MAME"`) stays a reading job. Exit status 0 always; the report is the
result.
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

OURS = {".py", ".md", ".vhd", ".vhdl", ".c", ".cpp", ".h", ".hpp", ".lua", ".patch", ".diff", ".toml", ".sh", ".txt"}  # fmt: skip
THEIRS = {".c", ".cpp", ".cc", ".h", ".hpp", ".inc", ".hxx", ".cs", ".vhd", ".vhdl", ".v", ".sv", ".py", ".lua", ".asm", ".s", ".lst", ".hh", ".ipp", ".inl"}  # fmt: skip
MAX_BYTES = 3_000_000
PROSE_N, CODE_N, TABLE_N = 8, 14, 8

TOKEN = re.compile(
    r"0[xX][0-9a-fA-F]+|\$[0-9a-fA-F]+|\d+|[A-Za-z_][A-Za-z_0-9]*|[-+*/%&|^~<>=!]+|[()\[\],?:]"
)
WORD = re.compile(r"[A-Za-z][A-Za-z']+")
# Words of one language only: dropped, so the same expression has the same shape in both.
NOISE = {
    "self", "this", "const", "static", "inline", "unsigned", "signed", "int", "uint8", "uint16",
    "uint32", "uint8_t", "uint16_t", "uint32_t", "int8_t", "int16_t", "int32_t", "uint64_t", "int64_t",
    "bool", "void", "auto", "char", "short", "long", "float", "double", "def", "var", "let", "u8", "u16",
    "u32", "s8", "s16", "s32", "n8", "n16", "n32", "std", "signal", "variable", "then", "begin", "end",
}  # fmt: skip
# Spelled the same everywhere: sharing one of these says nothing.
TRIVIAL = {"true", "false", "none", "null", "nullptr", "i", "n", "x", "y", "value", "data", "result", "address"}  # fmt: skip
ARITHMETIC = set("&|^+-*/%") | {
    "<<",
    ">>",
    ">=",
    "<=",
    "==",
    "!=",
    "<",
    ">",
    "+=",
    "-=",
    "|=",
    "&=",
}
KEYWORDS = {"if", "else", "elif", "for", "while", "return", "and", "or", "not", "in", "case", "switch", "break", "do"}  # fmt: skip


def number(text: str) -> int | None:
    try:
        if text[0] == "$":
            return int(text[1:], 16)
        return int(text, 0) if text[:2].lower() == "0x" else int(text)
    except ValueError:
        return None


def code_tokens(line: str) -> list[tuple[str, str]]:
    """(shape, spelling) per token: shape is `#value`, `I`, a keyword or the operator itself."""
    out = []
    for text in TOKEN.findall(line):
        if text[0].isdigit() or text[0] == "$":
            value = number(text)
            if value is not None:
                out.append((f"#{value}", f"#{value}"))
        elif text[0].isalpha() or text[0] == "_":
            low = text.lower()
            if low in NOISE:
                continue
            if low in KEYWORDS:
                out.append((low, low))
            else:
                out.append(("I", low))
        elif text in ("->", "::", "."):
            continue
        else:
            out.append((text, text))
    return out


def strip_comment(line: str, suffix: str) -> tuple[str, str]:
    """(code, comment) of a line, roughly: enough to separate prose from code."""
    marks = ("#",) if suffix in (".py", ".toml", ".sh") else ("--",) if suffix in (".vhd", ".vhdl", ".lua") else ("//", "/*", "*")  # fmt: skip
    if suffix in (".asm", ".s", ".lst"):
        marks = (";",)
    for mark in marks:
        at = line.find(mark)
        if at >= 0 and (mark != "*" or line.lstrip().startswith("*")):
            return line[:at], line[at + len(mark) :]
    return line, ""


class Side:
    """One file's fingerprints: where each prose, code and table window starts."""

    def __init__(self, path: Path, text: str) -> None:
        self.path = path
        suffix = path.suffix.lower()
        self.prose: dict[tuple, int] = {}
        self.code: dict[tuple, tuple[int, tuple]] = {}
        self.tables: dict[tuple, int] = {}
        self.lines: dict[str, int] = {}
        words: list[tuple[str, int]] = []
        tokens: list[tuple[str, str, int]] = []
        numbers: list[tuple[int, int]] = []
        doc = suffix in (".md", ".txt")
        for n, line in enumerate(text.splitlines(), 1):
            code, comment = ("", line) if doc else strip_comment(line, suffix)
            prose_part = line if doc else comment + " " + " ".join(re.findall(r'"([^"]*)"', code))
            words += [(w.lower(), n) for w in WORD.findall(prose_part)]
            source = line if doc else code
            for shape, spelling in code_tokens(source):
                tokens.append((shape, spelling, n))
                if shape[0] == "#":
                    numbers.append((int(shape[1:]), n))
            squeezed = re.sub(r"\s+", "", source)
            if len(squeezed) >= 30 and re.search(r"[=(;]", squeezed):
                self.lines.setdefault(squeezed, n)
        for i in range(len(words) - PROSE_N + 1):
            window = tuple(w for w, _ in words[i : i + PROSE_N])
            if len(set(window)) >= 6:
                self.prose.setdefault(window, words[i][1])
        for i in range(len(tokens) - CODE_N + 1):
            window = tokens[i : i + CODE_N]
            shapes = tuple(t[0] for t in window)
            # An expression, not a run of `name = 0` initialisers: numbers and real operators.
            if (
                sum(1 for s in shapes if s[0] == "#") >= 2
                and sum(1 for s in shapes if s in ARITHMETIC) >= 3
            ):
                self.code.setdefault(shapes, (window[0][2], tuple(t[1] for t in window)))
        for i in range(len(numbers) - TABLE_N + 1):
            window = tuple(v for v, _ in numbers[i : i + TABLE_N])
            steps = {b - a for a, b in itertools.pairwise(window)}
            powers = sum(1 for v in window if v and v & (v - 1) == 0)
            # A table, not a count (0 1 2 3 ...), a row of bit masks, or a handful of small values.
            if (
                len(set(window)) >= 6
                and len(steps) > 2
                and powers < TABLE_N - 2
                and max(window) > 16
            ):
                self.tables.setdefault(window, numbers[i][1])


def tracked(repo: Path) -> list[Path]:
    out = subprocess.run(["git", "-C", str(repo), "ls-files"], capture_output=True, text=True, check=True)  # fmt: skip
    return [repo / name for name in out.stdout.splitlines() if Path(name).suffix.lower() in OURS]


def read(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        return path.read_text(errors="replace")
    except OSError:
        return None


def licence_of(path: Path, table: dict[str, str]) -> str:
    for part in path.parts:
        if part in table:
            return table[part]
    return "?"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo", type=Path, action="append", required=True)
    p.add_argument("--reference", type=Path, action="append", required=True)
    p.add_argument("--licences", type=Path, action="append", default=[], help="pinned_repos.json")
    p.add_argument("--report", type=Path)
    p.add_argument("--min-shared-names", type=int, default=2)
    a = p.parse_args()

    licences: dict[str, str] = {}
    for file in a.licences:
        data = json.loads(file.read_text())
        rows = data.get("repos", data) if isinstance(data, dict) else data
        for row in rows.values() if isinstance(rows, dict) else rows:
            if isinstance(row, dict):
                for key in ("dir", "path", "name", "dest"):
                    if row.get(key):
                        licences[Path(str(row[key])).name] = str(row.get("license") or row.get("licence") or "?")  # fmt: skip

    ours: list[Side] = []
    for repo in a.repo:
        for path in tracked(repo.resolve()):
            if path.name == "provenance_check.py":
                continue
            text = read(path)
            if text is not None:
                ours.append(Side(path, text))
    prose = defaultdict(list)
    code = defaultdict(list)
    tables = defaultdict(list)
    lines = defaultdict(list)
    for side in ours:
        for key, n in side.prose.items():
            prose[key].append((side, n))
        for key, (n, spell) in side.code.items():
            code[key].append((side, n, spell))
        for key, n in side.tables.items():
            tables[key].append((side, n))
        if side.path.suffix.lower() in (".md", ".txt"):
            for key, n in side.lines.items():
                lines[key].append((side, n))

    hits: dict[tuple, dict] = defaultdict(
        lambda: {"prose": [], "code": [], "tables": [], "quotes": []}
    )
    scanned = 0
    for root in a.reference:
        for path in sorted(root.resolve().rglob("*")):
            if not path.is_file() or path.suffix.lower() not in THEIRS:
                continue
            text = read(path)
            if text is None:
                continue
            scanned += 1
            theirs = Side(path, text)
            for key, n in theirs.prose.items():
                for side, m in prose.get(key, ()):
                    hits[(side.path, path)]["prose"].append((m, n, " ".join(key)))
            for key, (n, spell) in theirs.code.items():
                for side, m, mine in code.get(key, ()):
                    shared = len(
                        {
                            x
                            for x, y, s in zip(mine, spell, key, strict=True)
                            if s == "I" and x == y and x not in TRIVIAL
                        }
                    )
                    numbers = sum(1 for s in key if s[0] == "#")
                    if shared >= a.min_shared_names or (numbers >= 4 and shared >= 1):
                        hits[(side.path, path)]["code"].append((m, n, " ".join(mine)))
            for key, n in theirs.tables.items():
                for side, m in tables.get(key, ()):
                    hits[(side.path, path)]["tables"].append((m, n, " ".join(map(str, key))))
            for key, n in theirs.lines.items():
                for side, m in lines.get(key, ()):
                    hits[(side.path, path)]["quotes"].append((m, n, key[:100]))

    out = [f"# Provenance check: {len(ours)} of our files against {scanned} reference files", ""]
    order = sorted(hits.items(), key=lambda kv: -sum(len(v) for v in kv[1].values()))
    for (mine, theirs), kinds in order:
        total = {k: len(v) for k, v in kinds.items() if v}
        out.append(f"## {mine} <- {theirs}  [{licence_of(theirs, licences)}]  {total}")
        for kind, rows in kinds.items():
            seen_lines: set[int] = set()
            shown = 0
            for m, n, what in sorted(rows):
                if m in seen_lines:
                    continue
                seen_lines.add(m)
                if shown < 6:
                    out.append(f"- {kind} ours:{m} theirs:{n}  `{what[:140]}`")
                shown += 1
            if shown > 6:
                out.append(f"- {kind}: {shown - 6} more of our lines")
        out.append("")
    if not hits:
        out.append("No hits.")
    text = "\n".join(out)
    if a.report:
        a.report.write_text(text + "\n")
        print(f"{len(hits)} file pairs with hits; report in {a.report}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
