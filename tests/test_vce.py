"""The VCE against pcetech section 6 and the Hudson VCE manual."""

import random

from pcengine_python.vce import Vce


def write_entry(vce, address, value, mclk=0):
    vce.write(2, address & 0xFF, mclk)
    vce.write(3, address >> 8, mclk)
    vce.write(4, value & 0xFF, mclk)
    vce.write(5, value >> 8, mclk)


def test_write_then_read_back_with_msb_forced_ones():
    vce = Vce()
    write_entry(vce, 0x101, 0x1A5)
    vce.write(2, 0x01, 0)
    vce.write(3, 0x01, 0)
    assert vce.read(4, 0) == 0xA5
    assert vce.read(5, 0) == 0xFE | 1  # bits 7-1 set, D0 = the colour's bit 8
    assert vce.address == 0x102  # advanced after the MSB read


def test_address_advances_after_msb_write_and_wraps_at_1ff():
    vce = Vce()
    vce.write(2, 0xFF, 0)
    vce.write(3, 0x01, 0)
    vce.write(4, 0x07, 0)
    assert vce.address == 0x1FF  # an LSB write does not advance
    vce.write(5, 0x00, 0)
    assert vce.address == 0x000
    assert vce.palette[0x1FF] == 0x007


def test_msb_only_writes_change_only_the_msb():
    vce = Vce()
    write_entry(vce, 0x000, 0x0AB)
    vce.write(2, 0x00, 0)
    vce.write(5, 0x01, 0)  # "writing $0405 repeatedly changes only the MSB of each entry"
    assert vce.palette[0] == 0x1AB
    assert vce.address == 1


def test_either_half_of_the_address_updates_alone():
    vce = Vce()
    vce.write(2, 0x34, 0)
    vce.write(3, 0x01, 0)
    assert vce.address == 0x134
    vce.write(2, 0x56, 0)  # LSB alone keeps bit 8
    assert vce.address == 0x156
    vce.write(3, 0x00, 0)  # MSB alone keeps the low byte; the upper 7 bits are ignored
    assert vce.address == 0x056
    vce.write(3, 0xFE, 0)
    assert vce.address == 0x056


def test_unused_registers_read_ff_and_control_is_write_only():
    vce = Vce()
    vce.write(0, 0x87, 0)
    for offset in (0, 1, 2, 3, 6, 7):
        assert vce.read(offset, 0) == 0xFF
    vce.write(1, 0x12, 0)
    vce.write(6, 0x12, 0)  # writes to unused registers do nothing
    assert vce.control == 0x87


def test_register_mirror_is_every_eight_bytes():
    vce = Vce()
    vce.write(0x0A, 0x55, 0)
    assert vce.address == 0x55


def test_dot_clock_and_flags_from_control():
    vce = Vce()
    for control, divider in ((0, 4), (1, 3), (2, 2), (3, 2)):
        vce.write(0, control, 0)
        assert vce.dot_divider == divider
    vce.write(0, 0x84, 0)
    assert vce.monochrome and vce.bit2


def test_palette_changes_are_logged_with_their_time():
    vce = Vce()
    vce.write(2, 0x00, 5)
    vce.write(4, 0x07, 100)
    vce.write(5, 0x01, 110)
    assert vce.palette_log == [(100, 0, 0x007), (110, 0, 0x107)]


def test_power_up_zero_by_default_random_on_request_and_reproducible():
    zero = Vce()
    assert zero.palette == [0] * 512
    a, b = Vce(power_on=random.Random(7)), Vce(power_on=random.Random(7))
    assert a.palette == b.palette
    assert a.palette != zero.palette
    assert all(0 <= v < 512 for v in a.palette)


def test_rgb_table_is_replaceable():
    vce = Vce()
    vce.palette[3] = 0b111_000_000  # green
    assert vce.rgb(3) == (0, 255, 0)
    vce.rgb_table = [(1, 2, 3)] * 512
    assert vce.rgb(3) == (1, 2, 3)
