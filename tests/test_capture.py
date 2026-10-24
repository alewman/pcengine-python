"""The picture capture: 9-bit palette values per dot, with CPU palette writes landing on the
dot they were made on (the mechanism of Covell's CPU test: tier 1 judges the *positions*, this
checks the mechanism)."""

from fake_devices import ScriptedCpu
from helpers import standard_display

from pcengine_python.board import Board
from pcengine_python.machine import (
    ACTIVE_LINES,
    HARDWARE_BASE,
    LINE_CLOCKS,
    TOP_BLANK_LINES,
    Machine,
)

FIXED_263 = Machine("test machine, 263 lines", country_pc_engine=True, lines_follow_vce_bit2=False)


def set_entry(vce, address, value, mclk):
    vce.write(2, address & 0xFF, mclk)
    vce.write(3, address >> 8, mclk)
    vce.write(4, value & 0xFF, mclk)
    vce.write(5, value >> 8, mclk)


def run_frames(board, frames):
    board.advance(LINE_CLOCKS * 263 * frames)


def test_a_frame_is_the_242_active_lines_of_the_dot_clock_width():
    board = Board(FIXED_263)
    run_frames(board, 2)
    frame = board.capture.last_frame
    assert frame is not None
    assert len(frame.rows) == ACTIVE_LINES == 242
    assert {len(row) for row in frame.rows} == {1365 // 4}
    assert set(frame.dividers) == {4}


def test_dot_clock_changes_the_row_width():
    board = Board(FIXED_263)
    board.vce.write(0, 0x01, 0)
    run_frames(board, 2)
    assert {len(row) for row in board.capture.last_frame.rows} == {1365 // 3}
    board.vce.write(0, 0x02, board.mclk)
    run_frames(board, 1)
    assert {len(row) for row in board.capture.last_frame.rows} == {1365 // 2}


def test_blank_display_shows_the_overscan_colour_everywhere():
    board = Board(FIXED_263)
    set_entry(board.vce, 0x100, 0x1C0, 0)  # sprite palette 0 colour 0
    set_entry(board.vce, 0x000, 0x007, 0)  # background palette 0 colour 0
    run_frames(board, 2)
    values = {v for row in board.capture.last_frame.rows for v in row}
    assert values == {0x1C0}


def test_backdrop_inside_the_display_overscan_outside_when_a_layer_is_on():
    board = Board(FIXED_263)
    cpu = ScriptedCpu(board, high_speed=True)
    set_entry(board.vce, 0x100, 0x1C0, 0)
    set_entry(board.vce, 0x000, 0x007, 0)
    standard_display(cpu, cr=0x0080)  # background on
    run_frames(board, 3)
    frame = board.capture.last_frame
    # display period: frame lines 25-248 -> rows 11..234 of the 242 captured (from line 14)
    inside = frame.rows[100]
    assert {0x007, 0x1C0} == set(inside)
    assert inside.count(0x007) == 256  # HDW $1F = 32 characters = 256 dots
    assert set(frame.rows[2]) == {0x1C0}  # line 16: before the display period
    assert set(frame.rows[240]) == {0x1C0}  # line 254: after it


def test_the_colour_zero_of_other_palettes_shows_the_backdrop_entry():
    board = Board(FIXED_263)

    class Pixels:
        def mix(self, timing, rows):
            return [0x120] * len(rows[0])  # palette 2, colour 0 of the sprite half

    board.capture.path = Pixels()
    set_entry(board.vce, 0x100, 0x055, 0)
    set_entry(board.vce, 0x120, 0x1FF, 0)
    run_frames(board, 2)
    assert {v for row in board.capture.last_frame.rows for v in row} == {0x055}


def test_split_position_in_a_captured_frame():
    board = Board(FIXED_263)
    cpu = ScriptedCpu(board, high_speed=True)
    frames = {}
    board.capture._on_frame = lambda frame: frames.setdefault(frame.number, frame)
    set_entry(board.vce, 0x100, 0x007, 0)
    target = (263 + 100) * LINE_CLOCKS + 400
    board.advance(target - board.mclk)
    for address, value in ((0x0402, 0x00), (0x0403, 0x01), (0x0404, 0x38)):
        cpu.write(HARDWARE_BASE + address, value)
    write_time = board.mclk - 3  # the LSB data write; the stretch cycle follows it
    board.advance(LINE_CLOCKS * 263 * 2 - board.mclk)
    row = frames[1].rows[100 - TOP_BLANK_LINES]
    first_changed = next(x for x, v in enumerate(row) if v != 0x007)
    row_start = (263 + 100) * LINE_CLOCKS + 237  # dot 0 is the first dot after the line's sync
    assert row[first_changed] == 0x038  # the LSB write alone changes only the low byte
    assert first_changed == -(-(write_time - row_start) // 4)  # the first dot at or after it
    assert all(v == 0x038 for v in row[first_changed:])
    assert all(v == 0x007 for v in row[:first_changed])
    assert frames[1].rows[101 - TOP_BLANK_LINES][0] == 0x038  # and it persists on the next line
