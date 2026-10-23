#!/usr/bin/env python3
"""Run a PC Engine card or CD on a libretro core headless (ctypes) and save its last frame.

The cores are built from the pinned trees (docs/validation.md): Beetle PCE
(``reference/src/beetle-pce``, Mednafen's PCE core, ``make``) gives
``mednafen_pce_libretro.so``. This host is ~100 lines of ctypes against the
libretro ABI (``retro_*``); nothing of the core is copied.

    python -I scripts/libretro_run.py CORE.so ROM.pce --frames 600 --png out.png
    python -I scripts/libretro_run.py CORE.so GAME.chd --system DIR --frames 900 --png out.png

``--system DIR`` is the directory the core reads BIOS files from (for CD
games: ``syscard3.pce``, bring your own: Aubrey's copy is in his BIOS pack).
Frames are RGB565 or XRGB8888 as the core negotiates; the PNG is the last
frame as delivered (the core's own width and height: Beetle PCE draws 5 MHz
games at 256 wide, 7 MHz at 341, 10 MHz at 512, which is what Mednafen shows).
``--audio FILE.wav`` writes the core's audio. Needs Pillow for ``--png``.
"""

from __future__ import annotations

import argparse
import ctypes as C
import struct
import sys
import time
import wave
from pathlib import Path

ENV_SET_PIXEL_FORMAT = 10
ENV_GET_SYSTEM_DIRECTORY = 9
ENV_GET_SAVE_DIRECTORY = 31
ENV_GET_VARIABLE = 15
ENV_GET_LOG = 27
ENV_GET_CORE_OPTIONS_VERSION = 52
PF_0RGB1555, PF_XRGB8888, PF_RGB565 = 0, 1, 2


class GameInfo(C.Structure):
    _fields_ = [
        ("path", C.c_char_p),
        ("data", C.c_void_p),
        ("size", C.c_size_t),
        ("meta", C.c_char_p),
    ]


class SystemAV(C.Structure):
    class Geometry(C.Structure):
        _fields_ = [
            ("bw", C.c_uint),
            ("bh", C.c_uint),
            ("mw", C.c_uint),
            ("mh", C.c_uint),
            ("ar", C.c_float),
        ]

    class Timing(C.Structure):
        _fields_ = [("fps", C.c_double), ("rate", C.c_double)]

    _fields_ = [("geometry", Geometry), ("timing", Timing)]


class Variable(C.Structure):
    _fields_ = [("key", C.c_char_p), ("value", C.c_char_p)]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("core", type=Path)
    p.add_argument("content", type=Path)
    p.add_argument("--frames", type=int, default=300)
    p.add_argument("--png", type=Path)
    p.add_argument("--audio", type=Path)
    p.add_argument("--system", type=Path, default=Path("."))
    p.add_argument("--verbose", action="store_true", help="print the core's log format strings")
    p.add_argument("--option", action="append", default=[], metavar="KEY=VALUE", help="core option")
    a = p.parse_args()
    lib = C.CDLL(str(a.core.resolve()))
    system = str(a.system.resolve()).encode()
    options = dict(o.split("=", 1) for o in a.option)
    state = {"fmt": PF_0RGB1555, "frame": None, "audio": bytearray(), "frames": 0}
    keep = []

    ENV = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
    VIDEO = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
    SAMPLE = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
    BATCH = C.CFUNCTYPE(C.c_size_t, C.POINTER(C.c_int16), C.c_size_t)
    POLL = C.CFUNCTYPE(None)
    INPUT = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)

    LOG = C.CFUNCTYPE(None, C.c_int, C.c_char_p)  # variadic in C: only the format arrives

    def log(level: int, fmt: bytes) -> None:
        if a.verbose:
            print(f"[core {level}] {fmt.decode(errors='replace').rstrip()}", file=sys.stderr)

    log_cb = LOG(log)
    keep.append(log_cb)

    def env(cmd: int, data: int | None) -> bool:
        cmd &= 0xFFFF
        if cmd == ENV_GET_LOG:
            C.cast(data, C.POINTER(C.c_void_p))[0] = C.cast(log_cb, C.c_void_p)
            return True
        if cmd == ENV_SET_PIXEL_FORMAT:
            state["fmt"] = C.cast(data, C.POINTER(C.c_int)).contents.value
            return True
        if cmd in (ENV_GET_SYSTEM_DIRECTORY, ENV_GET_SAVE_DIRECTORY):
            C.cast(data, C.POINTER(C.c_char_p))[0] = system
            return True
        if cmd == ENV_GET_VARIABLE:
            var = C.cast(data, C.POINTER(Variable)).contents
            value = options.get(var.key.decode())
            if value is None:
                return False
            keep.append(value.encode())
            var.value = keep[-1]
            return True
        return False

    def video(data: int | None, w: int, h: int, pitch: int) -> None:
        state["frames"] += 1
        if data:
            state["frame"] = (C.string_at(data, pitch * h), w, h, pitch)

    def sample(left: int, right: int) -> None:
        state["audio"] += struct.pack("<hh", left, right)

    def batch(data, frames: int) -> int:
        state["audio"] += C.string_at(data, frames * 4)
        return frames

    callbacks = [
        ENV(env),
        VIDEO(video),
        SAMPLE(sample),
        BATCH(batch),
        POLL(lambda: None),
        INPUT(lambda *x: 0),
    ]
    keep.extend(callbacks)
    lib.retro_set_environment(callbacks[0])
    lib.retro_set_video_refresh(callbacks[1])
    lib.retro_set_audio_sample(callbacks[2])
    lib.retro_set_audio_sample_batch(callbacks[3])
    lib.retro_set_input_poll(callbacks[4])
    lib.retro_set_input_state(callbacks[5])
    lib.retro_init()
    info = GameInfo(str(a.content.resolve()).encode(), None, 0, None)
    if not lib.retro_load_game(C.byref(info)):
        print("retro_load_game failed")
        return 1
    av = SystemAV()
    lib.retro_get_system_av_info(C.byref(av))
    began = time.monotonic()
    for _ in range(a.frames):
        lib.retro_run()
    wall = time.monotonic() - began
    rate = int(av.timing.rate)
    print(
        f"{a.frames} frames in {wall:.1f} s; core {av.geometry.bw}x{av.geometry.bh} base, "
        f"{av.timing.fps:.4f} fps, {av.timing.rate:.0f} Hz audio"
    )
    if a.audio:
        with wave.open(str(a.audio), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(bytes(state["audio"]))
    if a.png and state["frame"]:
        from PIL import Image

        raw, w, h, pitch = state["frame"]
        if state["fmt"] == PF_XRGB8888:
            img = Image.frombuffer("RGBA", (w, h), raw, "raw", "BGRA", pitch, 1).convert("RGB")
        elif state["fmt"] == PF_RGB565:
            rows = []
            for y in range(h):
                for (v,) in struct.iter_unpack("<H", raw[y * pitch : y * pitch + 2 * w]):
                    rows.append(
                        ((v >> 11) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31)
                    )
            img = Image.new("RGB", (w, h))
            img.putdata(rows)
        else:
            raise SystemExit(f"pixel format {state['fmt']} not handled")
        img.save(a.png)
        print(f"{a.png} ({w}x{h}, format {state['fmt']})")
    lib.retro_unload_game()
    lib.retro_deinit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
