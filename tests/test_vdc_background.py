"""The background layer, burst mode and the two DMAs against pcetech section 5 (tier 2) and
Hudson's VDC manual (tier 3). Pictures are 9-bit palette values: the test palette maps each
background pixel value `palette << 4 | colour` to a distinct colour (its own index)."""

import pytest
from fake_devices import ScriptedCpu
from helpers import line_of, standard_display, vdc_reg

from pcengine_python.board import Board
from pcengine_python.machine import ACTIVE_LINES, LINE_CLOCKS, TOP_BLANK_LINES, Machine
from pcengine_python.vdc import regs as r

FIXED_263 = Machine("test machine, 263 lines", country_pc_engine=True, lines_follow_vce_bit2=False)
FIRST_DOT = 32  # 8 dots of sync tail + (HDS 2 + 1) * 8
FIRST_ROW = 25 - TOP_BLANK_LINES  # the display period starts at frame line 25


def make(cr=0x0080 | 0x0008):
    board = Board(FIXED_263)
    cpu = ScriptedCpu(board, high_speed=True)
    for index in range(512):  # colour value = its own index, set straight in the table
        board.vce.palette[index] = index
        board.capture._shadow[index] = index
    standard_display(cpu, cr=cr)
    return board, cpu


def put_tile(vdc, tile, rows):
    """`rows`: 8 lists of 8 pixel values (0-15)."""
    for y, row in enumerate(rows):
        w0 = w1 = 0
        for x, value in enumerate(row):
            bit = 7 - x
            w0 |= (value & 1) << bit | ((value >> 1) & 1) << (bit + 8)
            w1 |= ((value >> 2) & 1) << bit | ((value >> 3) & 1) << (bit + 8)
        vdc.vram[tile * 16 + y] = w0
        vdc.vram[tile * 16 + y + 8] = w1


def frame_after(board, frames=3):
    board.advance(LINE_CLOCKS * 263 * frames)
    return board.capture.last_frame


def picture_row(frame, line=0):
    row = frame.rows[FIRST_ROW + line]
    return row[FIRST_DOT : FIRST_DOT + 256]


def test_bat_entry_selects_tile_and_palette_and_pixels_decode_planar():
    board, _ = make()
    put_tile(board.vdc, 5, [[0, 1, 2, 3, 4, 5, 6, 7]] + [[15] * 8] * 7)
    board.vdc.vram[0] = 0x3005  # palette 3, name 5
    row = picture_row(frame_after(board))
    assert row[:8] == [0, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37]  # colour 0: see below
    assert board.vdc.vram[1] == 0


def test_pixel_zero_shows_the_backdrop_not_the_palette_colour_zero():
    """[hw: pcetech 6] colour 0 of the 15 other palettes cannot be displayed."""
    board, _ = make()
    board.vce.palette[0] = 0x1AB
    board.capture._shadow[0] = 0x1AB
    put_tile(board.vdc, 5, [[0] * 8] * 8)
    board.vdc.vram[0] = 0x3005
    assert set(picture_row(frame_after(board))[:8]) == {0x1AB}


def test_each_line_of_the_tile_uses_its_own_word():
    board, _ = make()
    put_tile(board.vdc, 1, [[y + 1] * 8 for y in range(8)])
    board.vdc.vram[0] = 0x0001
    frame = frame_after(board)
    assert [picture_row(frame, y)[0] for y in range(10)] == [1, 2, 3, 4, 5, 6, 7, 8, 0, 0]


def test_horizontal_scroll_shifts_by_pixels_including_the_partial_first_tile():
    board, cpu = make()
    put_tile(board.vdc, 1, [[0, 1, 2, 3, 4, 5, 6, 7]] * 8)
    board.vdc.vram[0] = 0x0001
    board.vdc.vram[1] = 0x0001
    vdc_reg(cpu, r.BXR, 3)
    row = picture_row(frame_after(board))
    assert row[:8] == [3, 4, 5, 6, 7, 0, 1, 2]  # 5 pixels of tile 0 from x = 3, then tile 1


def test_bat_wraps_at_its_width_and_the_screen_size_comes_from_mwr():
    board, cpu = make()
    put_tile(board.vdc, 1, [[9] * 8] * 8)
    board.vdc.vram[0] = 0x0001  # BAT column 0 of a 32-wide BAT
    # 32 wide: column 32 of the screen is column 0 again; the picture is 32 tiles = 256 wide,
    # so scroll 8 pixels and the last tile is column 0 once more
    vdc_reg(cpu, r.BXR, 8)
    row = picture_row(frame_after(board))
    assert row[248:256] == [9] * 8
    # 64 wide: column 32 is a different entry
    board2, cpu2 = make()
    put_tile(board2.vdc, 1, [[9] * 8] * 8)
    board2.vdc.vram[0] = 0x0001
    vdc_reg(cpu2, r.MWR, 0x0010)
    vdc_reg(cpu2, r.BXR, 8)
    assert picture_row(frame_after(board2))[248:256] != [9] * 8


def test_vertical_scroll_starts_at_byr_on_the_first_display_line_and_steps_per_line():
    board, cpu = make()
    put_tile(board.vdc, 1, [[y + 1] * 8 for y in range(8)])
    board.vdc.vram[0] = 0x0001
    vdc_reg(cpu, r.BYR, 3)
    frame = frame_after(board)
    assert [picture_row(frame, y)[0] for y in range(6)] == [4, 5, 6, 7, 8, 0]


def test_cg_mode_reads_one_bitplane_pair_and_zeroes_the_other():
    board, cpu = make()
    put_tile(board.vdc, 1, [[0b1111] * 8] * 8)
    board.vdc.vram[0] = 0x0001
    vdc_reg(cpu, r.MWR, 0x0003)  # CG mode on, planes 0/1
    assert picture_row(frame_after(board))[0] == 0b0011
    board2, cpu2 = make()
    put_tile(board2.vdc, 1, [[0b1111] * 8] * 8)
    board2.vdc.vram[0] = 0x0001
    vdc_reg(cpu2, r.MWR, 0x0083)  # planes 2/3
    assert picture_row(frame_after(board2))[0] == 0b1100


def test_background_off_with_sprites_on_shows_the_backdrop_everywhere_in_the_width():
    board, _ = make(cr=0x0040 | 0x0008)
    board.vdc.vram[0] = 0x0001
    put_tile(board.vdc, 1, [[7] * 8] * 8)
    row = picture_row(frame_after(board))
    assert set(row) == {0}  # backdrop, $000


def test_burst_mode_draws_the_overscan_colour_in_the_active_period():
    """[hw: pcetech 5.1 $05] both layers off when the frame starts: every active line is
    colour 0 of sprite palette 0."""
    board, _ = make(cr=0x0008)
    board.vce.palette[0x100] = 0x1F0
    board.capture._shadow[0x100] = 0x1F0
    frame = frame_after(board)
    assert {v for row in frame.rows for v in row} == {0x1F0}


# --- DMA ----------------------------------------------------------------------------------


def dma(cpu, source, destination, length, dcr=0x0000):
    vdc_reg(cpu, r.DCR, dcr)
    vdc_reg(cpu, r.SOUR, source)
    vdc_reg(cpu, r.DESR, destination)
    vdc_reg(cpu, r.LENR, length)  # the MSB write starts it


def test_vram_dma_copies_words_and_leaves_the_counters_where_the_manual_says():
    board, cpu = make(cr=0x0000)  # burst mode: the VRAM is free
    for i in range(16):
        board.vdc.vram[0x100 + i] = 0x1000 + i
    board.advance(LINE_CLOCKS * 263)
    board.vdc.regs.value[r.MAWR] = 0x4321
    dma(cpu, 0x100, 0x200, 15)
    board.advance(LINE_CLOCKS * 2)
    assert [board.vdc.vram[0x200 + i] for i in range(16)] == [0x1000 + i for i in range(16)]
    regs = board.vdc.regs.value
    assert regs[r.LENR] == 0xFFFF  # [hw: pcetech 5.4] ends at $FFFF, not zero
    assert regs[r.SOUR] == 0x110 and regs[r.DESR] == 0x210  # the registers count
    assert regs[r.MAWR] == 0x4321  # untouched
    assert not board.vdc.dma.running


def test_vram_dma_steps_down_with_dcr_bits_and_ignores_the_cr_increment():
    board, cpu = make(cr=0x0000 | (3 << 11))  # CR increment 128 must not matter
    for i in range(4):
        board.vdc.vram[0x100 + i] = 0x2000 + i
    board.advance(LINE_CLOCKS * 263)
    dma(cpu, 0x103, 0x303, 3, dcr=0x000C)
    board.advance(LINE_CLOCKS)
    assert [board.vdc.vram[0x300 + i] for i in range(4)] == [0x2000, 0x2001, 0x2002, 0x2003]


def test_vram_dma_raises_done_when_enabled_and_takes_two_dots_a_word():
    board, cpu = make(cr=0x0000)
    board.advance(LINE_CLOCKS * 263)
    dma(cpu, 0, 0x400, 99, dcr=0x0002)  # 100 words, done IRQ on
    started = board.mclk
    assert not board.vdc.status & r.DV
    board.advance(190 * 4)
    assert not board.vdc.status & r.DV
    board.advance(30 * 4)
    assert board.vdc.status & r.DV
    assert started


def test_dma_is_paused_by_the_display_and_resumes_after_it_c7():
    board, cpu = make(cr=0x0080)  # background on: a display period every frame
    for i in range(0x3000):
        board.vdc.vram[0x1000 + i] = i & 0xFFFF
    board.advance(LINE_CLOCKS * 263 + LINE_CLOCKS * 20)  # frame 1, line 20: before the display
    dma(cpu, 0x1000, 0x5000, 0x2FFF, dcr=0x0002)  # 12 288 words, about 72 lines at 5 MHz
    board.advance(LINE_CLOCKS * 14)  # into the display period (line 25 onward)
    assert board.vdc.dma.running
    partial = board.vdc.regs.value[r.LENR]
    assert 0x2FFF > partial > 0x2000
    board.advance(LINE_CLOCKS * 10)
    assert board.vdc.regs.value[r.LENR] == partial  # paused during the display
    board.advance(LINE_CLOCKS * 263 * 3)
    assert board.vdc.regs.value[r.LENR] == 0xFFFF and board.vdc.status & r.DV  # resumed, done
    assert [board.vdc.vram[0x5000 + i] for i in (0, 0x1000, 0x2FFF)] == [0, 0x1000, 0x2FFF]


def test_the_manuals_reading_cancels_the_remainder_without_a_done_interrupt():
    board = Board(FIXED_263, dma_resumes=False)
    cpu = ScriptedCpu(board, high_speed=True)
    standard_display(cpu, cr=0x0080)
    for i in range(0x3000):
        board.vdc.vram[0x1000 + i] = i
    board.advance(LINE_CLOCKS * 263 + LINE_CLOCKS * 20)
    dma(cpu, 0x1000, 0x5000, 0x2FFF, dcr=0x0002)
    board.advance(LINE_CLOCKS * 263)
    assert board.vdc.regs.value[r.LENR] not in (0xFFFF,) and not board.vdc.status & r.DV
    assert not board.vdc.dma.running


def _wait_on_a_dma_across_the_display_start(dma_resumes):
    """Issue 0004: 4 096 words started at line 20 (24 lines at 5 MHz, 170 words a line; the
    display period starts at line 25), then a VRAM read, which holds the CPU (/BUSY on RDY) until
    the VDC serves it. Returns the board and the (frame, line) at which the CPU got its byte."""
    board = Board(FIXED_263, dma_resumes=dma_resumes)
    cpu = ScriptedCpu(board, high_speed=True)
    standard_display(cpu, cr=0x0080)
    for i in range(0x1000):
        board.vdc.vram[0x1000 + i] = i
    board.advance(LINE_CLOCKS * 263 + LINE_CLOCKS * 20)
    dma(cpu, 0x1000, 0x5000, 0x0FFF, dcr=0x0002)
    vdc_reg(cpu, r.MARR, 0x0000)  # accepted behind the transfer (BSY)
    assert board.vdc.bsy
    cpu.read(0x1FE002)  # a data read while the word is pending: the CPU waits
    return board, line_of(board, board.mclk)


def test_a_cpu_waiting_on_a_dma_sees_the_manuals_cancel_at_the_display_start():
    """`dma_resumes=False` (Hudson's manual, Mednafen): the display period still starts during
    the CPU's wait, cancels the remainder (no done flag) and serves the access there. The wait
    used to run the VDC alone to the transfer's end, so the transfer completed instead."""
    board, (frame, line) = _wait_on_a_dma_across_the_display_start(dma_resumes=False)
    # released as the display period begins (the line counter step that starts it, 4 dots before
    # line 24's display width ends, falls in line 25's clocks), not ~25 lines on
    assert (frame, line) == (1, 25)
    assert board.vdc.regs.value[r.LENR] != 0xFFFF and not board.vdc.status & r.DV
    assert not board.vdc.dma.running and not board.vdc.bsy
    left = board.vdc.regs.value[r.LENR]
    board.advance(LINE_CLOCKS * 263)
    assert board.vdc.regs.value[r.LENR] == left  # cancelled, not resumed


def test_a_cpu_waiting_on_a_dma_is_held_through_the_display_while_it_is_paused_c7():
    """The default (C7, MacDonald): the transfer pauses for the display period and the CPU stays
    held until it ends after the display; the picture lines are drawn meanwhile."""
    board, (frame, line) = _wait_on_a_dma_across_the_display_start(dma_resumes=True)
    assert board.vdc.regs.value[r.LENR] == 0xFFFF and board.vdc.status & r.DV
    # about 5 lines' worth before the display, the other 19 lines' after it (line 249 on)
    assert (frame, line) == (2, 5)
    assert board.capture.last_frame is not None and board.timeline.frame == 2  # drawn meanwhile
    assert [board.vdc.vram[0x5000 + i] for i in (0, 0x800, 0xFFF)] == [0, 0x800, 0xFFF]


# --- sprite attribute table DMA ------------------------------------------------------------


def test_satb_dma_copies_256_words_when_the_display_ends_and_reports_done_late():
    board, cpu = make(cr=0x0080 | 0x0008)
    for i in range(256):
        board.vdc.vram[0x7F00 + i] = 0x4000 + i
    board.advance(LINE_CLOCKS * (263 + 100))  # frame 1, line 100, inside the display period
    vdc_reg(cpu, r.DCR, 0x0001)  # done IRQ on
    vdc_reg(cpu, r.SATB, 0x7F00)
    board.vdc.status = 0
    assert board.vdc.sat[0] == 0  # armed only
    board.advance(LINE_CLOCKS * 149 + 100)  # past line 249: the display period has ended
    assert [board.vdc.sat[i] for i in (0, 255)] == [0x4000, 0x40FF]
    assert not board.vdc.status & r.DS
    board.advance(LINE_CLOCKS * 4)  # pcetech 5.4: four lines after the last active line
    assert board.vdc.status & r.DS


def test_satb_dma_still_runs_when_the_sync_cuts_the_display_period_short():
    """Rastan Saga II programs VDS $18 and VDW $FF: the display period would run past the
    frame's end, the vertical sync starts the next frame first. Mednafen tests for the transfer
    whenever the phase is not VDW after the display began (C27); without it the sprite table
    stays empty and the title's sword is not drawn."""
    board, cpu = make(cr=0x0080 | 0x0008)
    vdc_reg(cpu, 0x0D, 0x00FF)  # VDW 256 lines: 25 + 256 lines is past the 263-line frame
    board.advance(LINE_CLOCKS * 263)  # the vertical sync caches the registers
    for i in range(256):
        board.vdc.vram[0x7F00 + i] = 0x4000 + i
    vdc_reg(cpu, r.SATB, 0x7F00)
    assert board.vdc.sat[0] == 0
    board.advance(LINE_CLOCKS * 263 * 2)
    assert [board.vdc.sat[i] for i in (0, 255)] == [0x4000, 0x40FF]


def test_both_layers_off_inside_the_display_period_show_the_backdrop_not_the_overscan():
    """Space Harrier switches the background and sprites off for the last 12 lines
    (CR $0C at line 245): Mednafen, Mesen2 and Beetle PCE show colour 0 of the background
    palette there (C30); pcetech 5.2 says overscan, which the board followed before."""
    board, cpu = make(cr=0x0080 | 0x0008)
    board.advance(LINE_CLOCKS * (263 + 100))  # frame 1, inside the display period
    vdc_reg(cpu, r.CR, 0x0008)  # both layers off, vblank interrupt on
    board.advance(LINE_CLOCKS * (263 - 100) + LINE_CLOCKS * 5)  # to the end of frame 1
    row = picture_row(board.capture.last_frame, 100)  # frame line 125, after the write
    assert set(row) == {0x000}


def test_satb_dma_repeats_every_frame_with_dcr_bit_4():
    board, cpu = make(cr=0x0080)
    vdc_reg(cpu, r.DCR, 0x0010)
    vdc_reg(cpu, r.SATB, 0x0100)
    board.advance(LINE_CLOCKS * 263 * 2)
    board.vdc.vram[0x0100] = 0x1234
    assert board.vdc.sat[0] == 0
    board.advance(LINE_CLOCKS * 263)
    assert board.vdc.sat[0] == 0x1234


def test_cpu_vram_access_waits_while_a_dma_runs():
    board, cpu = make(cr=0x0000)
    board.advance(LINE_CLOCKS * 263)
    dma(cpu, 0, 0x400, 99)
    cpu.write(0x1FE000, 0x00)  # MAWR
    cpu.write(0x1FE002, 0x00)
    cpu.write(0x1FE003, 0x08)
    cpu.write(0x1FE000, 0x02)
    cpu.write(0x1FE002, 0x34)
    cpu.write(0x1FE003, 0x12)  # accepted behind the DMA
    assert board.vdc.bsy
    cpu.write(0x1FE003, 0x13)  # a second data access holds the CPU until the DMA is done
    assert not board.vdc.dma.running
    assert board.vdc.vram[0x800] == 0x1234


def test_a_waiting_cpu_write_stays_busy_across_line_starts_until_the_satb_dma_ends():
    """Manual and pcetech: BSY is set while the VDC has not yet served the CPU's VRAM access.
    The board once committed the waiting word at the next line's display start although the
    sprite-table transfer still held the VRAM (Bonk's Adventure: Mednafen BSY set, board clear;
    Mednafen's CheckAndCommitPending commits nothing while a transfer runs)."""
    board, cpu = make(cr=0x0080)
    vdc_reg(cpu, r.DCR, 0x0010)
    vdc_reg(cpu, r.SATB, 0x0100)
    while board.vdc.dma.sat_end is None:
        board.advance(100)
    vdc_reg(cpu, r.MAWR, 0x0300)
    cpu.write(0x1FE000, 0x02)
    cpu.write(0x1FE002, 0x34)
    cpu.write(0x1FE003, 0x12)  # accepted behind the transfer
    assert board.vdc.bsy
    board.advance(LINE_CLOCKS * 2)  # two line starts inside the 1024 dots
    assert board.vdc.dma.sat_end is not None
    assert board.vdc.bsy
    assert cpu.read(0x1FE000) & r.BSY
    assert board.vdc.vram[0x300] == 0
    while board.vdc.dma.sat_end is not None:
        board.advance(100)
    assert not board.vdc.bsy
    assert board.vdc.vram[0x300] == 0x1234


def test_a_second_vram_write_holds_the_cpu_to_the_end_of_the_satb_dma():
    """U30: the first CPU word is accepted (BSY) and the second waits for the transfer's end,
    1024 dots after it began; Mednafen and Mesen2 both stall the CPU that way (the length is
    where they differ: Mednafen resumes at the first VDC event after the end)."""
    board, cpu = make(cr=0x0080)
    vdc_reg(cpu, r.DCR, 0x0010)
    vdc_reg(cpu, r.SATB, 0x0100)
    while board.vdc.dma.sat_end is None:
        board.advance(100)
    vdc_reg(cpu, r.MAWR, 0x0300)
    cpu.write(0x1FE000, 0x02)
    cpu.write(0x1FE002, 0x11)
    cpu.write(0x1FE003, 0x11)  # accepted
    end = board.vdc.dma.sat_end
    cpu.write(0x1FE002, 0x22)
    cpu.write(0x1FE003, 0x22)  # waits
    assert board.mclk >= end
    assert board.mclk - end < 100  # released at the end, not a line later
    assert board.vdc.vram[0x300] == 0x1111  # the first word was served when the transfer ended
    assert board.vdc.vram[0x301] == 0x2222 or board.vdc.bsy


def test_a_data_read_waits_for_the_word_a_pending_fetch_has_not_loaded_yet():
    """Hudson's read sequence (MARR, then VRR LSB and MSB) gives the word at MARR; in the display
    the fetch waits for a CPU slot, and a read before it must wait, not return the old buffer."""
    board, _ = make(cr=0x0080)
    vdc = board.vdc
    vdc.vram[0x10] = 0x1234
    vdc.vram[0x11] = 0x5678
    vdc.regs.read_buffer = 0xFFFF
    while not (
        vdc.seq.active_display
        and vdc.slot_time(board.mclk) > board.mclk + 3
        and vdc.slot_time(board.mclk + 4) > board.mclk + 4
    ):
        board.advance(1)
    now = board.mclk
    vdc.write(0, r.MARR, now)
    vdc.write(2, 0x10, now)
    vdc.write(3, 0x00, now)  # the fetch of word $10 waits for a slot
    assert vdc.bsy
    vdc.write(0, r.VRW, now)
    held_before = board._held
    assert vdc.read(2, now) == 0x34  # the new word, after the wait
    assert board._held > held_before
    assert vdc.read(3, now) == 0x12  # and the MSB read starts the fetch of $11
    assert vdc.bsy or vdc.regs.read_buffer == 0x5678


@pytest.mark.parametrize("lines", [ACTIVE_LINES])
def test_active_lines_constant(lines):
    assert lines == 242
