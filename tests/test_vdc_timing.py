"""The VDC's frame layout, vblank flag and raster compare on the board's timeline.

Judges: pcetech section 7 (the frame is 263 lines: 14 top blank, 242 active, 4 bottom blank,
3 sync; standard VDS $17 + VSW $02 puts the first graphics at line 25), section 5 (status bit 5
is set on the first line after the active display; RCR counts from $40 at the first active
line). The sub-line position of each event is provisional emulator tier 5 (U19): tests pin the
*line*, and check the sub-line offset only against the documented formula.
"""

import pytest
from fake_devices import ScriptedCpu
from helpers import standard_display, vdc_reg

from pcengine_python.board import Board
from pcengine_python.machine import LINE_CLOCKS, PC_ENGINE, Machine
from pcengine_python.vdc import regs as r

FIXED_263 = Machine("test machine, 263 lines", country_pc_engine=True, lines_follow_vce_bit2=False)


def step_until(board, predicate, limit=263 * 4 * LINE_CLOCKS, step=4):
    end = board.mclk + limit
    while board.mclk < end:
        board.advance(step)
        if predicate():
            return board.mclk
    raise AssertionError("condition never became true")


def make(machine=FIXED_263, *, cr=0x00C8 | 0x0004, **kw):
    board = Board(machine, **kw)
    cpu = ScriptedCpu(board, high_speed=True)
    standard_display(cpu, cr=cr)
    return board, cpu


def line_and_offset(board, mclk):
    absolute, offset = divmod(mclk, LINE_CLOCKS)
    return absolute % 263, offset


def test_frame_is_263_lines_when_fixed():
    board = Board(FIXED_263)
    board.advance(263 * LINE_CLOCKS * 3)
    assert board.timeline.frame == 3 and board.timeline.line == 0


def test_frame_follows_vce_bit_2_by_default_c3():
    board = Board(PC_ENGINE)
    board.advance(262 * LINE_CLOCKS)  # power-up VCE control is 0: 262 lines
    assert board.timeline.frame == 1
    board.vce.write(0, 0x04, board.mclk)
    board.advance(262 * LINE_CLOCKS)  # the frame that began before the write is still 262
    assert board.timeline.frame == 2
    board.advance(263 * LINE_CLOCKS)
    assert board.timeline.frame == 3 and board.timeline.line == 0


def test_vsync_is_the_last_three_lines_of_the_frame():
    board = Board(FIXED_263)
    seen = {}
    for _ in range(263 * 2):
        board.advance(LINE_CLOCKS)
        seen.setdefault(board.timeline.line, board.timeline.in_vsync)
    assert [line for line, v in sorted(seen.items()) if v] == [260, 261, 262]


def test_vblank_flag_rises_on_the_first_line_after_the_active_display():
    board, _ = make()
    # run into frame 1 so the vertical registers written above are cached by the vsync
    board.advance(LINE_CLOCKS * 263)
    board.vdc.status = 0
    when = step_until(board, lambda: board.vdc.status & r.VD)
    line, offset = line_and_offset(board, when)
    assert line == 25 + 0xDF + 1  # 249: first line after VDW + 1 = 224 lines from line 25
    # U19: the test happens as the sync ends (default 0 dots; Mednafen's is the display start)
    assert abs(offset - 237) <= 4


def test_mednafen_vblank_position_is_the_start_of_the_display_width():
    board = Board(FIXED_263, vblank_dots=None)
    cpu = ScriptedCpu(board, high_speed=True)
    standard_display(cpu, cr=0x00C8 | 0x0004)
    board.advance(LINE_CLOCKS * 263)
    board.vdc.status = 0
    when = step_until(board, lambda: board.vdc.status & r.VD)
    _, offset = line_and_offset(board, when)
    assert abs(offset - (237 + 8 * 4 + 3 * 8 * 4)) <= 4


def test_vblank_flag_needs_its_enable_bit():
    board, _cpu = make(cr=0x00C0 | 0x0004)  # raster IRQ enable only, no vblank enable
    board.advance(LINE_CLOCKS * 263 * 2)
    assert not board.vdc.status & r.VD


def test_vblank_irq_reaches_the_cpu_as_irq1_and_status_read_releases_it():
    board, cpu = make()
    step_until(board, lambda: cpu.lines[0])
    assert cpu.lines == (True, False, False)
    status = cpu.read(0x1FE000)
    assert status & r.VD
    assert cpu.lines == (False, False, False)


@pytest.mark.parametrize("offset", [0, 1, 10, 100])
def test_raster_compare_counts_from_40_at_the_first_active_line(offset):
    board, cpu = make(cr=0x00C0 | 0x0004)  # raster IRQ only
    vdc_reg(cpu, r.RCR, 0x40 + offset)
    board.advance(LINE_CLOCKS * 263)
    board.vdc.status = 0
    when = step_until(board, lambda: board.vdc.status & r.RR)
    line, at = line_and_offset(board, when)
    # [emu] the compare fires as the line counter steps, 4 dots before the width ends, which
    # for a 256-wide 5 MHz line is 8 master clocks into the next line: RCR $40 is "line 25"
    # [hw: pcetech 5.1] and arrives at the start of it.
    assert line == 25 + offset
    assert at < 237


def test_raster_out_of_range_never_fires():
    board, cpu = make(cr=0x00C0 | 0x0004)
    vdc_reg(cpu, r.RCR, 0x03F)
    board.advance(LINE_CLOCKS * 263 * 3)
    assert not board.vdc.status & r.RR


def test_raster_146_interrupts_at_line_24_of_the_next_frame():
    """[hw: pcetech 5.1] 'a value of $0146 (262) causes an interrupt at line 24 of the next
    frame' for VSW=$02, VDS=$17."""
    board, cpu = make(cr=0x00C0 | 0x0004)
    vdc_reg(cpu, r.RCR, 0x146)
    board.advance(LINE_CLOCKS * 263)
    board.vdc.status = 0
    when = step_until(board, lambda: board.vdc.status & r.RR)
    frame_line = divmod(when, LINE_CLOCKS)[0] - 263 * 2  # lines since the start of frame 2
    assert frame_line == 24 and divmod(when, LINE_CLOCKS)[1] < 237
