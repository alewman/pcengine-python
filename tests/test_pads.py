"""Pads against pcetech section 4 (2-button, Turbo Tap) and pce-devel's PCE_Controller_Info
(6-button scans, multitap port table)."""

from pcengine_python import pads
from pcengine_python.pads import MultiTap, Pad2, Pad6

DIRS = pads.UP | pads.RIGHT | pads.DOWN | pads.LEFT


def test_two_button_sel_high_reads_directions_active_low():
    pad = Pad2()
    assert pad.read(True, False) == 0x0F  # nothing pressed: all open = 1
    pad.pressed = pads.UP
    assert pad.read(True, False) == 0x0E
    pad.pressed = pads.LEFT | pads.RIGHT
    assert pad.read(True, False) == 0b0101
    pad.pressed = pads.DOWN
    assert pad.read(True, False) == 0b1011


def test_two_button_sel_low_reads_buttons():
    pad = Pad2()
    pad.pressed = pads.I
    assert pad.read(False, False) == 0b1110  # D0 = button I
    pad.pressed = pads.II | pads.SELECT
    assert pad.read(False, False) == 0b1001  # D1 = II, D2 = Select
    pad.pressed = pads.RUN
    assert pad.read(False, False) == 0b0111  # D3 = Run
    pad.pressed = pads.UP | pads.RUN  # the other group does not leak in
    assert pad.read(False, False) == 0b0111


def test_two_button_clr_high_returns_zeros():
    pad = Pad2()
    pad.pressed = DIRS
    assert pad.read(True, True) == 0
    assert pad.read(False, True) == 0


def test_six_button_alternates_scans_on_clr_pulses():
    pad = Pad6()
    pad.pressed = pads.UP | pads.I | pads.III | pads.VI
    first = pad.read(True, False), pad.read(False, False)
    assert first == (0b1110, 0b1110)  # directions; I
    pad.write(True, True)  # CLR 0 -> 1
    pad.write(True, False)
    second = pad.read(True, False), pad.read(False, False)
    assert second == (0b0000, 0b0110)  # SEL high shows 0000; SEL low III (D0) and VI (D3)
    pad.write(True, True)
    pad.write(True, False)
    assert (pad.read(True, False), pad.read(False, False)) == first


def test_six_button_ignores_repeated_clr_high():
    pad = Pad6()
    pad.write(True, True)
    pad.write(True, True)
    pad.write(True, False)
    assert pad.second_scan


def make_tap(*, connected=(0, 1, 2, 3, 4), **kw):
    ports = []
    for i in range(5):
        if i in connected:
            pad = Pad2()
            pad.pressed = 1 << i  # port i holds a distinct key down
            ports.append(pad)
        else:
            ports.append(None)
    return MultiTap(ports, **kw), ports


def reset_sequence(tap):
    """The game's sequence from PCE_Controller_Info: $01, $03, $01."""
    tap.write(True, False)
    tap.write(True, True)
    tap.write(True, False)


def test_multitap_reads_five_pads_in_order_then_zeros():
    tap, _ = make_tap()
    reset_sequence(tap)
    for i in range(5):
        # port i holds key bit i down: UP, RIGHT, DOWN, LEFT on SEL high, then button I
        direction = tap.read(True, False)
        assert direction == (~(1 << i) & 0x0F if i < 4 else 0x0F)
        tap.write(False, False)
        assert tap.read(False, False) == (0x0F if i < 4 else 0b1110)
        tap.write(True, False)  # SEL 0 -> 1 with CLR low: next port
    assert tap.counter == 5
    assert tap.read(True, False) == 0  # "returns $00 until the counter is reset"
    assert tap.read(False, False) == 0


def test_multitap_unconnected_port_returns_0f():
    tap, _ = make_tap(connected=(0,))
    reset_sequence(tap)
    tap.write(False, False)
    tap.write(True, False)
    assert tap.read(True, False) == 0x0F
    assert tap.read(False, False) == 0x0F


def test_multitap_first_01_write_returns_zeros_when_counter_is_spent():
    """[hw: pcetech 4] 'When $01 is written to $1000, D3-D0 are returned as zero'."""
    tap, _ = make_tap()
    tap.write(False, False)
    tap.write(True, False)
    assert tap.read(True, False) == 0


def test_multitap_clr_high_after_reset_shows_pad_one_per_pcetech():
    tap, ports = make_tap()
    tap.write(True, False)
    tap.write(True, True)  # $03
    assert tap.read(True, True) == ports[0].read(True, False)  # C12: pcetech's reading


def test_multitap_c12_alternative_reads_zero_with_clr_high():
    tap, _ = make_tap(clr_high_reads_pad=False)
    tap.write(True, False)
    tap.write(True, True)
    assert tap.read(True, True) == 0


def test_multitap_reset_needs_sel_high():
    tap, _ = make_tap()
    reset_sequence(tap)
    tap.write(False, False)
    tap.write(True, False)  # port 2
    assert tap.counter == 1
    tap.write(False, False)  # SEL low: a CLR rise now must NOT reset
    tap.write(False, True)
    assert tap.counter == 1
    tap.write(True, True)  # SEL rises with CLR already high: no increment
    assert tap.counter == 1
