#!/usr/bin/env python3
"""Run a PC Engine/TurboGrafx-16/SuperGrafx ROM on a locally built Mesen2 core (MesenCore.so) headless and save its frame.

A detector (docs/validation.md "Mesen2"), driven through ``ctypes`` the way
Mesen2's own ``UI/Utilities/TestRunner.cs`` drives it; our code calls the
GPL library at run time, nothing of it is copied. The library is the one
famicom-python built from Mesen2 ``b9fa69d`` (2.1.1, the same commit pinned
here); build it the same way into ``reference/build-mesen2/`` or pass
``--lib``. Cartridge games need no BIOS; CD games need the System Card (bring your own).

    python -I scripts/mesen_run.py tests/test_roms/CPU_Test/CPU_Test_10.pce \
        --frames 300 --png out.png

A Lua script counts frames and, at the last one, logs the frame buffer as hex
(``emu.getScreenBuffer``); this script turns that into a PNG (needs Pillow).
Frame size: see docs/validation.md (measured here, 2026-10-23).
"""

from __future__ import annotations

import argparse
import ctypes
import os
import struct
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBS = (
    ROOT / "reference/build-mesen2/Mesen2/InteropDLL/obj.linux-x64/MesenCore.so",
    Path(
        "/data/emu/famicom-python/reference/build-mesen2/Mesen2/InteropDLL/obj.linux-x64/MesenCore.so"
    ),
)
MAXIMUM_SPEED, CONSOLE_MODE = 0x04, 0x10
DONE = "MESEN-DONE"

LUA = """\
local frames = 0
emu.addEventCallback(function()
  frames = frames + 1
  if frames == {frames} then
    local buf = emu.getScreenBuffer()
    local parts = {{}}
    for i = 1, #buf do parts[i] = string.format("%06x", buf[i]) end
    emu.log("PIXELS " .. #buf .. " " .. table.concat(parts))
    emu.log("{done}")
  end
end, emu.eventType.endFrame)
"""


class PceConfig(ctypes.Structure):
    """Mesen2's ``PcEngineConfig`` by value: 8,080 bytes of opaque storage.

    Its layout was measured by compiling ``offsetof`` against the pinned header
    (Core/Shared/SettingTypes.h at b9fa69dd) with g++ on 2026-10-23. The DLL
    has no default palette (the UI sets ``Palette[512]``, an RGB333 -> RGB
    table), so without this call every PC Engine frame is black; and at
    maximum speed the core skips rendering frames unless ``DisableFrameSkipping``
    (PceVpc::ProcessStartFrame).
    """

    _fields_ = [("raw", ctypes.c_ubyte * 8080)]


def pce_config() -> PceConfig:
    raw = bytearray(8080)
    struct.pack_into("<I", raw, 5960, 2)  # CdRomType = Arcade (the header's default)
    struct.pack_into("<I", raw, 5968, 1)  # RamPowerOnState = AllZeros: deterministic
    for i in range(8):  # ChannelVol[6], CdAudioVolume, AdpcmVolume
        struct.pack_into("<I", raw, 5976 + 4 * i, 100)
    raw[6008] = 1  # UseHuC6280aAudio
    raw[6014] = 1  # DisableFrameSkipping
    for i in range(512):  # index = the VCE's 9-bit GGGRRRBBB (assumed; checked against MAME)
        g, r, b = (i >> 6) & 7, (i >> 3) & 7, i & 7
        rgb = (r * 255 // 7) << 16 | (g * 255 // 7) << 8 | (b * 255 // 7)
        struct.pack_into("<I", raw, 6032 + 4 * i, rgb)
    return PceConfig.from_buffer_copy(bytes(raw))


def run(lib: Path, rom: Path, frames: int, home: Path, timeout: float) -> tuple[str, float]:
    m = ctypes.CDLL(str(lib))
    m.InitializeEmu.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p] + [
        ctypes.c_bool
    ] * 4
    m.LoadRom.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    m.LoadRom.restype = ctypes.c_bool
    m.SetEmulationFlag.argtypes = [ctypes.c_uint32, ctypes.c_bool]
    m.LoadScript.argtypes = [ctypes.c_char_p] * 3 + [ctypes.c_int32]
    m.LoadScript.restype = ctypes.c_int32
    m.GetScriptLog.argtypes = [ctypes.c_int32, ctypes.c_char_p, ctypes.c_uint32]
    home.mkdir(parents=True, exist_ok=True)
    m.InitDll()
    m.InitializeEmu(str(home.resolve()).encode(), None, None, True, True, True, True)
    m.SetPcEngineConfig.argtypes = [PceConfig]
    m.SetPcEngineConfig(pce_config())
    m.Pause()
    m.SetEmulationFlag(CONSOLE_MODE, True)
    if not m.LoadRom(str(rom.resolve()).encode(), b""):
        raise SystemExit("LoadRom failed")
    m.InitializeDebugger()
    lua = LUA.format(frames=frames, done=DONE).encode()
    script = m.LoadScript(b"frame.lua", str(home.resolve()).encode(), lua, -1)
    m.SetEmulationFlag(MAXIMUM_SPEED, True)
    began = time.monotonic()
    m.Resume()
    buf = ctypes.create_string_buffer(1 << 24)
    log = ""
    while time.monotonic() - began < timeout:
        time.sleep(0.05)
        m.GetScriptLog(script, buf, len(buf))
        log = buf.value.decode(errors="replace")
        if DONE in log:
            break
    m.Stop()
    m.Release()
    return log, time.monotonic() - began


def save_png(log: str, path: Path, width: int = 0) -> tuple[int, int]:
    from PIL import Image

    line = next(x for x in log.splitlines() if x.startswith("PIXELS "))
    _, count, hexes = line.split(" ", 2)
    n = int(count)
    # The frame is as wide as the VCE's dot clock makes it (measured: 70,664
    # pixels = 292 x 242 for the CPU test); take the widest width with a
    # plausible height, or force it with --width.
    fits = [w for w in range(200, 1400) if n % w == 0 and 200 <= n // w <= 300]
    width = width or (fits[-1] if fits else 0)  # the widest: 70,664 = 292 x 242 or 242 x 292
    if not width:
        raise SystemExit(f"{n} pixels fit widths {fits}: pass --width")
    height = n // width
    data = bytes.fromhex(hexes)
    Image.frombytes("RGB", (width, height), data).save(path)
    return width, height


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("rom", type=Path)
    p.add_argument("--frames", type=int, default=300)
    p.add_argument("--png", type=Path, required=True)
    p.add_argument("--home", type=Path, default=ROOT / "tests/runs/mesen-home")
    p.add_argument("--width", type=int, default=0, help="frame width when it is ambiguous")
    p.add_argument("--timeout", type=float, default=120.0, help="wall-clock seconds")
    p.add_argument(
        "--lib",
        type=Path,
        default=Path(os.environ["MESEN_CORE"]) if "MESEN_CORE" in os.environ else None,
    )
    a = p.parse_args()
    lib = a.lib or next((x for x in LIBS if x.exists()), None)
    if lib is None:
        raise SystemExit("no MesenCore.so: build it (docs/validation.md) or pass --lib")
    log, wall = run(lib, a.rom, a.frames, a.home, a.timeout)
    if DONE not in log:
        print(f"timed out after {wall:.1f} s")
        return 1
    width, height = save_png(log, a.png, a.width)
    print(f"{a.frames} frames in {wall:.1f} s: {a.png} ({width}x{height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
