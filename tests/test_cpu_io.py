"""The timer, interrupt controller, I/O port and I/O buffer against MacDonald's pcetech
(tier 2, tested on a console): the worked example of section 3 note 1, and the register rules of
sections 2.1, 2.2 and 4."""

import pytest
from fake_devices import FakeController

from pcengine_python.cpu_io import CpuIo
from pcengine_python.cpu_io.timer import TICK_CLOCKS


class RecordingPsg:
    def __init__(self):
        self.writes = []

    def write(self, offset, value, mclk):
        self.writes.append((offset, value))


def make_io(**kw):
    psg = RecordingPsg()
    return CpuIo(psg, country_pc_engine=kw.pop("country_pc_engine", True), **kw), psg


def test_pcetech_io_buffer_worked_example():
    io, _ = make_io()
    # stz $0C01 ; Buffer = $00       stz $0C00 ; Buffer = $00
    io.write(0x0C01, 0x00, 0)
    assert io.buffer.value == 0x00
    io.write(0x0C00, 0x00, 0)
    assert io.buffer.value == 0x00
    # lda #$05 ; sta $1402 ; Buffer = $05
    io.write(0x1402, 0x05, 0)
    assert io.buffer.value == 0x05
    # lda #$FF ; sta $080F ; Buffer = $FF
    io.write(0x080F, 0xFF, 0)
    assert io.buffer.value == 0xFF
    # lda $1400 ; Read $FF, Buffer = $FF
    assert io.read(0x1400, 0) == 0xFF
    assert io.buffer.value == 0xFF
    # lda $1402 ; Read $FD, Buffer = $FD
    assert io.read(0x1402, 0) == 0xFD
    assert io.buffer.value == 0xFD
    # sta $1000 ; Buffer = $FD
    io.write(0x1000, 0xFD, 0)
    assert io.buffer.value == 0xFD
    # lda $0C00 ; Read = $80, Buffer = $80
    assert io.read(0x0C00, 0) == 0x80
    assert io.buffer.value == 0x80


def test_psg_range_returns_the_buffer_in_full_and_forwards_writes():
    io, psg = make_io()
    io.write(0x0805, 0x3C, 0)
    assert psg.writes == [(5, 0x3C)]
    for offset in (0x0800, 0x0809, 0x080F, 0x0B7F):
        assert io.read(offset, 0) == 0x3C
    assert io.buffer.value == 0x3C


def test_timer_and_irq_registers_mirror():
    io, _ = make_io()
    io.write(0x0C01, 0x00, 0)
    io.write(0x0D00, 0x05, 0)  # mirrored every 2 bytes: latch
    assert io.timer.latch == 5
    io.write(0x1502, 0x03, 0)  # mirrored every 4 bytes
    assert io.irq.disable == 3


def test_unused_bits_of_1400_1401_writes_do_nothing():
    io, _ = make_io()
    io.write(0x1400, 0x77, 0)
    io.write(0x1401, 0x66, 0)
    assert io.irq.disable == 0
    assert io.buffer.value == 0x66  # but the buffer takes the value
    assert io.read(0x1400, 0) == 0x66


# --- the timer ----------------------------------------------------------------------------


def test_timer_powers_up_count_zero_disabled():
    io, _ = make_io()
    assert io.timer.count == 0 and not io.timer.enabled
    assert io.timer.next_event() is None


@pytest.mark.parametrize(("latch", "period"), [(0, 1), (1, 2), (2, 3), (0x7F, 128)])
def test_timer_period_is_latch_plus_one_ticks(latch, period):
    """[hw: pcetech 2.2] "A value of $00 counts as 1, $7F counts as 128."""
    io, _ = make_io()
    io.write(0x0C00, latch, 0)
    io.write(0x0C01, 1, 100)  # enabled at master clock 100
    first = 100 + period * TICK_CLOCKS
    assert io.next_event() == first
    io.catch_up(first - 1)
    assert not io.tiq
    io.catch_up(first)
    assert io.tiq
    # reloaded at that moment and counting: the next underflow is one period later
    assert io.next_event() == first + period * TICK_CLOCKS


def test_timer_counts_down_and_reads_the_live_count():
    io, _ = make_io()
    io.write(0x0C00, 5, 0)
    io.write(0x0C01, 1, 0)
    assert io.read(0x0C00, 0) == 5
    assert io.read(0x0C00, TICK_CLOCKS) == 4
    assert io.read(0x0C00, 3 * TICK_CLOCKS) == 2
    # bit 7 is the I/O buffer, not the count
    io.buffer.value = 0xFF
    assert io.read(0x0C01, 3 * TICK_CLOCKS) == 0x82


def test_timer_asserts_when_the_counter_goes_from_zero_to_7f_not_one_to_zero():
    io, _ = make_io()
    io.write(0x0C00, 1, 0)
    io.write(0x0C01, 1, 0)
    io.catch_up(TICK_CLOCKS)  # 1 -> 0
    assert io.timer.count == 0 and not io.tiq
    io.catch_up(2 * TICK_CLOCKS)  # 0 -> underflow
    assert io.tiq
    assert io.timer.count == 1  # reloaded: you read the reloaded value, not $7F


def test_timer_interrupt_holds_until_1403_is_written_and_keeps_counting():
    io, _ = make_io()
    io.write(0x0C00, 0, 0)
    io.write(0x0C01, 1, 0)
    io.catch_up(5 * TICK_CLOCKS)
    assert io.tiq
    assert io.read(0x1403, 5 * TICK_CLOCKS) & 7 == 0b100
    io.write(0x1403, 0x00, 5 * TICK_CLOCKS)  # any value
    assert not io.tiq
    assert io.timer.next_event() == 6 * TICK_CLOCKS  # it never stopped counting


def test_timer_disabled_freezes_and_reenable_reloads_from_the_latch():
    io, _ = make_io()
    io.write(0x0C00, 9, 0)
    io.write(0x0C01, 1, 0)
    io.catch_up(4 * TICK_CLOCKS)
    assert io.timer.count == 5
    io.write(0x0C01, 0, 4 * TICK_CLOCKS)
    io.catch_up(50 * TICK_CLOCKS)
    assert io.timer.count == 5  # frozen
    io.write(0x0C00, 3, 50 * TICK_CLOCKS)  # new latch; the frozen count is untouched
    assert io.timer.count == 5
    io.write(0x0C01, 1, 60 * TICK_CLOCKS)
    assert io.timer.count == 3  # reloaded with the last value written to $0C00
    assert io.timer.next_event() == 64 * TICK_CLOCKS


def test_writing_the_latch_does_not_change_the_running_count():
    io, _ = make_io()
    io.write(0x0C00, 4, 0)
    io.write(0x0C01, 1, 0)
    io.write(0x0C00, 100, TICK_CLOCKS)
    assert io.timer.count == 3
    io.catch_up(5 * TICK_CLOCKS)  # underflows at tick 5, reloads the new latch
    assert io.timer.count == 100


# --- the interrupt controller -------------------------------------------------------------


def test_1402_mask_reads_back_with_buffer_in_the_upper_five_bits():
    seen = []
    io, _ = make_io(on_irq_disable=seen.append)
    io.write(0x1402, 0x06, 0)
    assert seen == [6]
    assert io.read(0x1402, 0) == 0x06  # the buffer holds 6: its upper five bits are clear
    io.buffer.value = 0xF8
    assert io.read(0x1402, 0) == 0xF8 | io.irq.disable
    io.write(0x1402, 0xFF, 0)  # only bits 2-0 are stored
    assert io.irq.disable == 7


def test_1403_reads_the_lines_even_when_masked():
    io, _ = make_io()
    io.write(0x1402, 0x07, 0)  # everything disabled
    io.irq.irq1 = True
    io.irq.irq2 = True
    io.buffer.value = 0
    assert io.read(0x1403, 0) & 7 == 0b011


def test_power_up_mask_is_zero_everything_enabled():
    io, _ = make_io()
    assert io.irq.disable == 0


# --- the I/O port -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("country_pc", "cd", "expected_high"),
    [(True, False, 0xC0), (False, False, 0x80), (True, True, 0x40), (False, True, 0x00)],
)
def test_io_port_d7_cd_sense_d6_country_d5_d4_ones(country_pc, cd, expected_high):
    io, _ = make_io(country_pc_engine=country_pc, cd_attached=lambda: cd)
    value = io.read(0x1000, 0)
    assert value & 0xC0 == expected_high
    assert value & 0x30 == 0x30
    assert value & 0x0F == 0x0F  # no pad: pulled up


def test_io_port_read_loads_the_buffer_but_never_returns_buffer_bits():
    io, _ = make_io()
    io.buffer.value = 0x00
    value = io.read(0x1000, 0)
    assert io.buffer.value == value
    io.buffer.value = 0xAB
    assert io.read(0x1000, 0) == 0xFF  # D7=1 (no CD) D6=1 D5-4=1 pad pins high


def test_io_port_write_sets_sel_and_clr_and_reaches_the_pad():
    pad = FakeController(0x0A)
    io, _ = make_io(pad=pad)
    io.write(0x1000, 0x02, 0)
    io.write(0x1000, 0x01, 0)
    assert pad.writes == [(False, True), (True, False)]
    assert io.read(0x1000, 0) & 0x0F == 0x0A
    assert io.buffer.value == io.read(0x1000, 0)


def test_io_port_mirrors_across_the_whole_1000_13ff_block():
    pad = FakeController()
    io, _ = make_io(pad=pad)
    io.write(0x13FF, 0x03, 0)
    assert pad.writes == [(True, True)]


def test_output_port_powers_up_high_so_sel_and_clr_start_set():
    """[mfr: HuC6280 manual 2.5] a system reset drives the output port high."""
    pad = FakeController(0x07)
    io, _ = make_io(pad=pad)
    assert io.port.sel and io.port.clr
    io.write(0x1000, 0x00, 0)
    assert not io.port.sel and not io.port.clr
    io.reset()
    assert io.port.latch == 0xFF


def test_output_port_keeps_the_upper_bits_for_the_supergrafx_s_exp_port():
    io, _ = make_io()
    io.write(0x1000, 0xFC, 0)
    assert io.port.latch == 0xFC and not io.port.sel


def test_timer_prescaler_restarts_every_time_it_is_enabled_manual_2_7():
    """[mfr 2.7] 'When 0 is written in the Timer Start/Stop flag, the timer stops and the prescaler
    is reset'; the counter loads when the flag goes 0 -> 1: a stop and a start restart the
    first period whatever the phase of the old one."""
    io, _ = make_io()
    io.write(0x0C00, 1, 0)
    io.write(0x0C01, 1, 0)
    io.catch_up(TICK_CLOCKS - 1)  # nearly a whole tick in
    io.write(0x0C01, 0, TICK_CLOCKS - 1)  # stop: the prescaler resets
    io.write(0x0C01, 1, 5 * TICK_CLOCKS)  # start: a whole tick again, not the remainder
    assert io.timer.count == 1
    io.catch_up(6 * TICK_CLOCKS - 1)
    assert io.timer.count == 1
    io.catch_up(6 * TICK_CLOCKS)
    assert io.timer.count == 0
    assert io.next_event() == 7 * TICK_CLOCKS


def test_enabling_an_enabled_timer_does_not_restart_it():
    io, _ = make_io()
    io.write(0x0C00, 3, 0)
    io.write(0x0C01, 1, 0)
    io.write(0x0C01, 1, TICK_CLOCKS + 100)  # 1 -> 1: not a 0 -> 1 change
    assert io.timer.count == 2  # one tick has passed and nothing was reloaded


def test_c25_the_count_reads_7f_for_the_underflow_window_then_the_reload():
    """C25 [emu, tier 5]: Battle Royale polls `$0C00` with latch 0 until it reads non-zero."""
    io, _ = make_io()
    io.write(0x0C00, 0, 0)
    io.write(0x0C01, 1, 0)
    assert io.read(0x0C00, TICK_CLOCKS - 1) == 0
    assert io.read(0x0C00, TICK_CLOCKS) == 0x7F  # the underflow tick
    assert io.read(0x0C00, TICK_CLOCKS + 14) == 0x7F
    assert io.read(0x0C00, TICK_CLOCKS + 15) == 0  # reloaded from latch 0
    io.timer.underflow_window_mclk = 0  # the first model: instant reload
    assert io.read(0x0C00, 2 * TICK_CLOCKS) == 0
