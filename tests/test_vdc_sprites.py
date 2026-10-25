"""Sprites against pcetech 5.3 (tier 2) and Hudson's VDC manual (tier 3): placement, flips,
sizes, priority, the 16-entry limit and the overflow flag, sprite 0's collision flag, the
two-plane mode. The palette of `make()` maps each 9-bit value to itself, so a picture value says
which pixel won: sprite pixels are `$100 | palette << 4 | colour`, background
`palette << 4 | colour`."""

from helpers import vdc_reg
from test_vdc_background import FIRST_DOT, FIRST_ROW, frame_after, make, put_tile

from pcengine_python.vdc import regs as r
from pcengine_python.vdc import sprites

SPRITES_ON = 0x0040 | 0x0008


def put_sprite_pattern(vdc, pattern, rows, planes=4):
    """`rows`: 16 lists of 16 colour values; stored as 4 planes of 16 words."""
    for y, row in enumerate(rows):
        words = [0, 0, 0, 0]
        for x, value in enumerate(row):
            bit = 15 - x
            for plane in range(4):
                words[plane] |= (value >> plane & 1) << bit
        for plane in range(planes):
            vdc.vram[pattern * 64 + plane * 16 + y] = words[plane]


def put_entry(vdc, index, x, y, pattern, flags=0, cg=0):
    words = [(y + 64) & 0x3FF, (x + 32) & 0x3FF, (pattern << 1 | cg) & 0x7FF, flags]
    for k, word in enumerate(words):
        vdc.sat[4 * index + k] = word


def row_at(frame, line, x=0, n=16):
    row = frame.rows[FIRST_ROW + line]
    return row[FIRST_DOT + x : FIRST_DOT + x + n]


def solid(value):
    return [[value] * 16 for _ in range(16)]


def test_a_sprite_appears_at_its_x_and_y_with_its_palette():
    board, _ = make(cr=SPRITES_ON)
    put_sprite_pattern(board.vdc, 4, solid(5))
    put_entry(board.vdc, 0, x=10, y=3, pattern=4, flags=0x0002)  # palette 2
    frame = frame_after(board)
    assert row_at(frame, 3, 10) == [0x100 | 0x20 | 5] * 16
    assert row_at(frame, 3, 9, 1) == [0] and row_at(frame, 3, 26, 1) == [0]
    assert row_at(frame, 2, 10, 1) == [0] and row_at(frame, 18, 10, 1) == [0x125]
    assert row_at(frame, 19, 10, 1) == [0]


def test_pattern_pixels_decode_left_to_right_and_flip_x_reverses_them():
    board, _ = make(cr=SPRITES_ON)
    put_sprite_pattern(board.vdc, 4, [[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 1]] * 16)
    put_entry(board.vdc, 0, x=0, y=0, pattern=4)
    put_entry(board.vdc, 1, x=32, y=0, pattern=4, flags=0x0800)
    frame = frame_after(board)
    forward = [0x100 | v for v in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 1]]
    assert row_at(frame, 0, 0) == forward
    assert row_at(frame, 0, 32) == forward[::-1]


def test_flip_y_reverses_the_rows():
    board, _ = make(cr=SPRITES_ON)
    put_sprite_pattern(board.vdc, 4, [[y % 15 + 1] * 16 for y in range(16)])
    put_entry(board.vdc, 0, x=0, y=0, pattern=4, flags=0x8000)
    frame = frame_after(board)
    assert [row_at(frame, y, 0, 1)[0] for y in range(3)] == [0x101, 0x10F, 0x10E]


def test_a_32_wide_sprite_is_two_patterns_and_flip_x_swaps_them():
    board, _ = make(cr=SPRITES_ON)
    put_sprite_pattern(board.vdc, 4, solid(3))
    put_sprite_pattern(board.vdc, 5, solid(6))
    put_entry(board.vdc, 0, x=0, y=0, pattern=5, flags=0x0100)  # odd pattern: bit 0 forced to 0
    put_entry(board.vdc, 1, x=40, y=0, pattern=4, flags=0x0100 | 0x0800)
    frame = frame_after(board)
    assert row_at(frame, 0, 0, 32) == [0x103] * 16 + [0x106] * 16
    assert row_at(frame, 0, 40, 32) == [0x106] * 16 + [0x103] * 16


def test_tall_sprites_take_the_next_patterns_down_and_mask_the_low_pattern_bits():
    board, _ = make(cr=SPRITES_ON)
    for k in range(4):
        put_sprite_pattern(board.vdc, 9 + 2 * k, solid(k + 1))  # 9, 11, 13, 15: cells 0-3
    put_entry(board.vdc, 0, x=0, y=0, pattern=15, flags=0x3000)  # 64 tall: bits 2, 1 cleared -> 9
    frame = frame_after(board)
    assert [row_at(frame, y, 0, 1)[0] for y in (0, 15, 16, 31, 32, 48, 63)] == [
        0x101,
        0x101,
        0x102,
        0x102,
        0x103,
        0x104,
        0x104,
    ]
    board2, _ = make(cr=SPRITES_ON)
    for k in range(2):
        put_sprite_pattern(board2.vdc, 8 + 2 * k, solid(k + 1))
    put_entry(board2.vdc, 0, x=0, y=0, pattern=10, flags=0x8000 | 0x1000)  # 32 tall: -> 8, flipped
    frame2 = frame_after(board2)
    assert [row_at(frame2, y, 0, 1)[0] for y in (0, 15, 16, 31)] == [0x102, 0x102, 0x101, 0x101]


def test_priority_bit_decides_against_an_opaque_background_pixel():
    board, _ = make(cr=SPRITES_ON | 0x0080)
    put_tile(board.vdc, 1, [[7] * 8] * 8)
    board.vdc.vram[0] = 0x0001
    board.vdc.vram[1] = 0x0001
    put_sprite_pattern(board.vdc, 4, solid(5))
    put_entry(board.vdc, 0, x=0, y=0, pattern=4)  # behind the opaque background
    put_entry(board.vdc, 1, x=16, y=0, pattern=4, flags=0x0080)  # in front
    frame = frame_after(board)
    assert row_at(frame, 0, 0) == [7] * 16
    assert row_at(frame, 0, 16) == [0x105] * 16
    # over transparent background pixels a low-priority sprite shows
    put_tile(board.vdc, 1, [[0] * 8] * 8)
    assert row_at(frame_after(board), 0, 0) == [0x105] * 16


def test_the_first_sprite_of_the_table_wins_where_two_overlap():
    board, _ = make(cr=SPRITES_ON)
    put_sprite_pattern(board.vdc, 4, solid(5))
    put_sprite_pattern(board.vdc, 5, solid(9))
    put_entry(board.vdc, 0, x=0, y=0, pattern=4)
    put_entry(board.vdc, 1, x=8, y=0, pattern=5, flags=0x0080)  # priority does not reorder sprites
    frame = frame_after(board)
    assert row_at(frame, 0, 0, 24) == [0x105] * 16 + [0x109] * 8


def test_sprites_are_clipped_by_the_display_and_hidden_when_disabled():
    board, _ = make(cr=SPRITES_ON)
    put_sprite_pattern(board.vdc, 4, solid(5))
    put_entry(board.vdc, 0, x=-8, y=0, pattern=4)
    put_entry(board.vdc, 1, x=250, y=0, pattern=4)
    frame = frame_after(board)
    assert row_at(frame, 0, 0, 8) == [0x105] * 8 and row_at(frame, 0, 8, 1) == [0]
    assert row_at(frame, 0, 250, 6) == [0x105] * 6
    board2, _ = make(cr=0x0008 | 0x0080)  # sprites off
    put_sprite_pattern(board2.vdc, 4, solid(5))
    put_entry(board2.vdc, 0, x=0, y=0, pattern=4)
    assert row_at(frame_after(board2), 0, 0, 4) == [0, 0, 0, 0]


def test_seventeen_entries_set_overflow_and_only_sixteen_are_drawn():
    """[mfr] 'an attempt to display 17 sprites on a scanning line' sets OR; a 32-wide sprite counts
    twice, and with one place left only its left half is shown."""
    board, _ = make(cr=SPRITES_ON | 0x0002)
    put_sprite_pattern(board.vdc, 4, solid(5))
    for i in range(15):
        put_entry(board.vdc, i, x=16 * (i % 12), y=0, pattern=4)  # 15 entries (overlapping ok)
    put_sprite_pattern(board.vdc, 6, solid(2))
    put_sprite_pattern(board.vdc, 7, solid(3))
    put_entry(board.vdc, 15, x=200, y=0, pattern=6, flags=0x0100)  # entries 16 and 17
    frame = frame_after(board)
    assert board.vdc.status & r.OR
    assert row_at(frame, 0, 200, 16) == [0x102] * 16  # the left half
    assert row_at(frame, 0, 216, 16) == [0] * 16  # the right half was the 17th entry


def test_sixteen_entries_do_not_overflow_and_the_flag_needs_its_enable_bit():
    board, _ = make(cr=SPRITES_ON | 0x0002)
    put_sprite_pattern(board.vdc, 4, solid(5))
    for i in range(16):
        put_entry(board.vdc, i, x=16 * i % 240, y=0, pattern=4)
    frame_after(board)
    assert not board.vdc.status & r.OR
    board2, _ = make(cr=SPRITES_ON)  # overflow IRQ not enabled
    put_sprite_pattern(board2.vdc, 4, solid(5))
    for i in range(20):
        put_entry(board2.vdc, i, x=0, y=0, pattern=4)
    frame_after(board2)
    assert not board2.vdc.status & r.OR


def test_sprite_zero_collision_sets_the_flag_when_enabled():
    board, _ = make(cr=SPRITES_ON | 0x0001)
    put_sprite_pattern(board.vdc, 4, solid(5))
    put_entry(board.vdc, 0, x=0, y=0, pattern=4)
    put_entry(board.vdc, 1, x=8, y=4, pattern=4)  # overlaps sprite 0
    frame_after(board)
    assert board.vdc.status & r.CR_FLAG
    board2, _ = make(cr=SPRITES_ON)  # collision IRQ not enabled
    put_sprite_pattern(board2.vdc, 4, solid(5))
    put_entry(board2.vdc, 0, x=0, y=0, pattern=4)
    put_entry(board2.vdc, 1, x=8, y=4, pattern=4)
    frame_after(board2)
    assert not board2.vdc.status & r.CR_FLAG


def test_collision_needs_opaque_pixels_and_sprite_zero_itself():
    board, _ = make(cr=SPRITES_ON | 0x0001)
    put_sprite_pattern(board.vdc, 4, [[0, 5] * 8] * 16)  # every other pixel transparent
    put_sprite_pattern(board.vdc, 5, [[5, 0] * 8] * 16)
    put_entry(board.vdc, 0, x=0, y=0, pattern=4)
    put_entry(board.vdc, 1, x=0, y=0, pattern=5)  # interleaved: no shared opaque pixel
    put_entry(board.vdc, 2, x=0, y=0, pattern=5)  # two sprites that are not sprite 0 may overlap
    frame_after(board)
    assert not board.vdc.status & r.CR_FLAG


def test_collision_flag_rises_when_the_beam_reaches_the_pixel():
    board, _ = make(cr=SPRITES_ON | 0x0001)
    put_sprite_pattern(board.vdc, 4, solid(5))
    put_entry(board.vdc, 0, x=100, y=0, pattern=4)
    put_entry(board.vdc, 1, x=100, y=0, pattern=4)
    board.advance(263 * 1365 + (25 + 0) * 1365 - 1000)  # frame 1, just before the display
    board.vdc.status = 0
    seen = None
    while board.mclk < 263 * 1365 + 27 * 1365 and seen is None:
        board.advance(4)
        if board.vdc.status & r.CR_FLAG:
            seen = board.mclk
    assert seen is not None
    line_start = (263 + 25) * 1365 + 237
    expected = line_start + (FIRST_DOT + 100) * 4
    assert abs(seen - expected) <= 8


def test_two_plane_sprites_pick_planes_by_the_cg_bit():
    """[mfr: SM = 1] the pattern's low bit selects bitplanes 0/1 or 2/3, shown as a 2-bit colour;
    [emu: Mednafen, Mesen2] the pair read from words 32 and 48 becomes colour bits 0 and 1."""
    board, cpu = make(cr=SPRITES_ON)
    vdc_reg(cpu, r.MWR, 0x0004)
    put_sprite_pattern(board.vdc, 4, solid(0b1001))  # plane 0 and plane 3 set
    put_entry(board.vdc, 0, x=0, y=0, pattern=4, cg=0)
    put_entry(board.vdc, 1, x=32, y=0, pattern=4, cg=1)
    frame = frame_after(board)
    assert row_at(frame, 0, 0, 1) == [0x100 | 0b01]  # planes 0 and 1: colour 1
    assert row_at(frame, 0, 32, 1) == [0x100 | 0b10]  # planes 2 and 3: colour 2


def test_scan_is_a_pure_function_of_the_table():
    sat = [0] * 256
    sat[0:4] = [64 + 5, 32, 8 << 1, 0]
    entries, overflow = sprites.scan([0] * 0x8000, 0x8000, sat, 5, 0)
    assert len(entries) == 1 and not overflow and entries[0].sprite0
