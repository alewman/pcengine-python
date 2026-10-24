"""The machine table and the clock constants every module shares.

One board, a table of rows: the PC Engine and the TurboGrafx-16 differ by a pin
(docs/start-here.md). Add-ons (SuperGrafx, CD) add rows or pin this board; they do not fork it.
"""

from __future__ import annotations

from dataclasses import dataclass

# [hw: pcetech 2.4] 21.47727 MHz master clock (6 x NTSC colour burst).
MASTER_HZ = 21_477_272

# [doc: wiki "Timing"; emu: Mednafen vce.cpp] a line is 1365 master clocks whatever the dot clock
# (C5: "roughly 342 dots" at 5 MHz is 1365 / 4 = 341.25).
LINE_CLOCKS = 1365

# [emu: Mednafen vce.cpp l.561 `hblank_counter = hblank ? 237 : 1128`] the VCE's horizontal sync
# is 237 master clocks at the start of a line. Tier 5; the real width is not published (U19).
HSYNC_CLOCKS = 237

# [emu: Mednafen vce.cpp `vblank_counter = vblank ? 4095 : ...`] the vertical sync is the last
# three lines of a frame (4095 = 3 x 1365). [hw: pcetech 7] "3 lines for the sync area".
VSYNC_LINES = 3

# [hw: pcetech 2.4] CPU clock is master/3 (high) or master/12 (low); power-up is low.
CPU_CLOCKS_HIGH = 3
CPU_CLOCKS_LOW = 12

# [hw: pcetech 2.2] the timer counts once per 1024 high-speed CPU cycles, whatever the CPU speed.
TIMER_TICK_CLOCKS = 1024 * 3

# [hw: pcetech 7] the frame layout: 14 top blank, 242 active, 4 bottom blank, 3 sync.
TOP_BLANK_LINES = 14
ACTIVE_LINES = 242

# [hw: pcetech 7; doc: wiki] 263-line frame; the 262-line form follows VCE bit 2 (C3).
FRAME_LINES_LONG = 263
FRAME_LINES_SHORT = 262

# A page of the page table is 256 bytes over the 21-bit space: 8192 pages (docs/sockets.md).
PAGE_BITS = 8
PAGE_COUNT = 1 << 13
ADDRESS_MASK = (1 << 21) - 1

# The hardware page, bank $FF: physical $1FE000-$1FFFFF (pages 0x1FE0-0x1FFF).
HARDWARE_BASE = 0x1FE000
HARDWARE_FIRST_PAGE = HARDWARE_BASE >> PAGE_BITS


@dataclass(frozen=True)
class Machine:
    """One row of the machine table."""

    name: str
    # [hw: pcetech 4] I/O port D6: 1 = PC Engine, 0 = TurboGrafx-16 (US games check it).
    country_pc_engine: bool
    # 8 KiB of work RAM, mirrored through banks $F8-$FB; the SuperGrafx add-on has 32 KiB.
    work_ram_bytes: int = 8 * 1024
    vdc_count: int = 1
    # C3: MacDonald calls VCE bit 2 "blur"; Mednafen, ares and Mesen2 take it as 263 lines when
    # set and 262 when clear; MAME ignores it. True follows the three emulators (tier 5).
    lines_follow_vce_bit2: bool = True


PC_ENGINE = Machine("PC Engine", country_pc_engine=True)
TURBOGRAFX_16 = Machine("TurboGrafx-16", country_pc_engine=False)
