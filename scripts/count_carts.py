#!/usr/bin/env python3
"""Census of a local PC Engine / TurboGrafx-16 / SuperGrafx / CD library, read in place.

HuCards (``.7z``/``.zip`` holding one ``.pce``/``.sgx`` image): each image is
extracted to a temporary directory (never into the repository), a 512-byte
copier header is stripped when the size says so, and the CRC-32 is looked up in
MAME 0.285's software lists (``reference/src/mame/hash/pce.xml``, ``tg16.xml``,
``sgx.xml``; fetch with ``scripts/fetch_references.py``). The lists carry the
board each card needs (``<feature name="slot">``: ``sf2``, ``populous``,
``tennokoe``), so the count of cards by mapper is the lists' (emulator-derived
and curated by the MAME team), not a header decode: **a HuCard has no header**.
Images the lists do not know are counted as "unlisted" with their size class.

CD discs (``.chd``): the CHD v5 header's raw-data SHA-1 is looked up in
``pcecd.xml``, which names the System Card each disc needs (``<info
name="usage">``): CD-ROM System, Super System, Arcade System, Games Express.
A repacked disc rarely matches MAME's hash (9 of 80 here), so the fallback is
the title (regions and flags dropped), marked "by title": approximate.

    python -I scripts/count_carts.py /data/emu/roms-retrobat/pcengine
    python -I scripts/count_carts.py /data/emu/roms-retrobat/pcenginecd --cd
    python -I scripts/count_carts.py DIR --list sf2        # titles in one class

Only top-level files are read: the ``By Genre``/``Best Games`` subdirectories
of Aubrey's tree are hard links of the same files. Nothing is written.
"""

from __future__ import annotations

import argparse
import collections
import re
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HASH = ROOT / "reference" / "src" / "mame" / "hash"
IMAGE = {".pce", ".sgx", ".bin", ".rom"}
UNLICENSED = re.compile(r"\((Beta|Proto|Pirate|Unl|Sample|Demo|Aftermarket|Homebrew)[^)]*\)")


def load_cards() -> dict[int, tuple[str, str, str]]:
    """CRC-32 -> (list name, slot feature or '', title) over pce, tg16 and sgx."""
    cards: dict[int, tuple[str, str, str]] = {}
    for name in ("pce", "tg16", "sgx"):
        for sw in ET.parse(HASH / f"{name}.xml").getroot().iter("software"):
            slot = ""
            for feature in sw.iter("feature"):
                if feature.get("name") == "slot":
                    slot = feature.get("value", "")
            title = sw.findtext("description", "")
            for rom in sw.iter("rom"):
                if rom.get("crc"):
                    cards.setdefault(int(rom.get("crc"), 16), (name, slot, title))
    return cards


def base_title(name: str) -> str:
    """A title reduced to lower-case letters and digits, regions and flags dropped."""
    name = re.sub(r"\(.*", "", name).strip()
    name = re.sub(r"^(the|a) |, (the|a)$", "", name.lower())
    return re.sub(r"[^a-z0-9]", "", name)


def load_discs() -> tuple[dict[str, tuple[str, str]], dict[str, set[str]]]:
    """(CHD SHA-1 -> (usage, title), base title -> usages) from pcecd.xml."""
    discs: dict[str, tuple[str, str]] = {}
    titles: dict[str, set[str]] = {}
    for sw in ET.parse(HASH / "pcecd.xml").getroot().iter("software"):
        usage = ""
        for info in sw.iter("info"):
            if info.get("name") == "usage":
                usage = info.get("value", "")
        titles.setdefault(base_title(sw.findtext("description", "")), set()).add(usage)
        for disk in sw.iter("disk"):
            if disk.get("sha1"):
                discs[disk.get("sha1")] = (usage, sw.findtext("description", ""))
    return discs, titles


def extract_image(archive: Path, work: Path) -> bytes | None:
    subprocess.run(
        ["7z", "e", "-y", f"-o{work}", str(archive)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    images = sorted(p for p in work.iterdir() if p.suffix.lower() in IMAGE)
    return images[0].read_bytes() if images else None


def size_class(n: int) -> str:
    k = n // 1024
    return f"{k} KiB" if k < 1024 else f"{n / 1048576:g} MiB"


def chd_hashes(path: Path) -> tuple[str, str, int]:
    """(raw SHA-1, combined SHA-1, logical bytes) from a CHD v5 header."""
    with path.open("rb") as f:
        head = f.read(124)
    if head[:8] != b"MComprHD" or struct.unpack(">I", head[12:16])[0] != 5:
        return "", "", 0
    logical = struct.unpack(">Q", head[32:40])[0]
    return head[64:84].hex(), head[84:104].hex(), logical


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("directory", type=Path)
    p.add_argument("--cd", action="store_true", help="count .chd discs instead of HuCards")
    p.add_argument("--licensed", action="store_true", help="skip Beta/Proto/Unl/Aftermarket names")
    p.add_argument("--list", metavar="CLASS", help="print titles whose mapper/usage contains CLASS")
    a = p.parse_args()
    classes: collections.Counter[str] = collections.Counter()
    sizes: collections.Counter[str] = collections.Counter()
    unlisted: list[str] = []
    total = 0
    if a.cd:
        discs, titles = load_discs()
        for path in sorted(a.directory.glob("*.chd")):
            if a.licensed and UNLICENSED.search(path.name):
                continue
            raw, combined, logical = chd_hashes(path)
            hit = discs.get(raw) or discs.get(combined)
            total += 1
            if hit:
                key = hit[0].split(" required")[0] if hit[0] else "listed, no usage"
            else:
                usages = titles.get(base_title(path.stem), set())
                key = (
                    "by title: " + " / ".join(sorted(u.split(" required")[0] for u in usages))
                    if usages
                    else "unlisted"
                )
            classes[key] += 1
            sizes[
                f"{logical // 1048576 // 100 * 100}-{logical // 1048576 // 100 * 100 + 99} MiB"
            ] += 1
            if key == "unlisted":
                unlisted.append(path.stem)
            if a.list and a.list.lower() in key.lower():
                print(path.stem)
        print(f"{total} discs in {a.directory.name}")
    else:
        cards = load_cards()
        paths = [x for x in sorted(a.directory.iterdir()) if x.suffix in {".7z", ".zip"}]
        for path in paths:
            if a.licensed and UNLICENSED.search(path.name):
                continue
            with tempfile.TemporaryDirectory() as tmp:
                rom = extract_image(path, Path(tmp))
            if rom is None:
                classes["no image"] += 1
                continue
            if len(rom) % 8192 == 512:
                rom = rom[512:]
            total += 1
            sizes[size_class(len(rom))] += 1
            hit = cards.get(zlib.crc32(rom))
            if hit:
                key = f"{hit[0]}: {hit[1] or 'plain HuCard'}"
            else:
                key = "unlisted" + (" (2.5 MiB: SF2-like)" if len(rom) == 0x280000 else "")
                unlisted.append(path.stem)
            classes[key] += 1
            if a.list and a.list.lower() in key.lower():
                print(path.stem)
        print(f"{total} images in {a.directory.name}")
    for name, count in classes.most_common():
        print(f"  {count:5d} {100 * count / max(total, 1):5.1f} %  {name}")
    print("  sizes:")
    for name, count in sorted(sizes.items(), key=lambda kv: (len(kv[0]), kv[0])):
        print(f"  {count:5d}  {name}")
    if unlisted and not a.list:
        print(
            f"  unlisted ({len(unlisted)}): "
            + "; ".join(unlisted[:40])
            + (" ..." if len(unlisted) > 40 else "")
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
