"""The PSG against Hudson's PSG manual (tier 3), pcetech section 10 (tier 2) and the step
rules its docstring names. Writes are made at master-clock times: step n starts at 6 * n."""

import pytest

from pcengine_python.psg import Psg


def w(psg, reg, value, step=None):
    psg.write(reg, value, 6 * (psg.step if step is None else step))


def select(psg, ch):
    w(psg, 0, ch)


def fill_wave(psg, ch, values):
    select(psg, ch)
    w(psg, 4, 0x00)  # ON = 0, DDA = 0: write data mode
    for v in values:
        w(psg, 6, v)


def start(psg, ch, frequency, control=0x9F, balance=0xFF):
    select(psg, ch)
    w(psg, 2, frequency & 0xFF)
    w(psg, 3, frequency >> 8)
    w(psg, 5, balance)
    w(psg, 4, control)


def runs(psg, steps):
    out = []
    psg.listeners.append(lambda n, state: out.append((n, state)))
    psg.advance_to(psg.step + steps)
    psg.listeners.pop()
    return out


def samples(psg, ch, steps):
    """The channel's sample at each of the next `steps` steps."""
    out = []
    for n, state in runs(psg, steps):
        out.extend([state[ch][0]] * n)
    return out


def test_write_data_mode_stores_and_increments_the_address():
    psg = Psg()
    fill_wave(psg, 0, range(32))
    assert psg.channels[0].wave == list(range(32)) and psg.channels[0].index == 0
    select(psg, 0)
    w(psg, 6, 0x1F)
    assert psg.channels[0].wave[0] == 0x1F and psg.channels[0].index == 1


def test_dda_one_then_zero_resets_the_address_so_the_start_can_be_chosen():
    psg = Psg()
    fill_wave(psg, 0, [5, 6, 7])
    w(psg, 4, 0x40)  # ON = 0, DDA = 1: reset counter mode [mfr 2.1.5]
    assert psg.channels[0].index == 0
    w(psg, 4, 0x00)
    w(psg, 6, 9)
    assert psg.channels[0].wave[0] == 9


def test_data_is_ignored_while_the_channel_plays_pcetech_10_c13():
    psg = Psg()
    fill_wave(psg, 0, [3] * 32)
    start(psg, 0, 0x100)
    index = psg.channels[0].index
    w(psg, 6, 0x1F)
    assert psg.channels[0].wave[index] == 3 and psg.channels[0].index == index
    emulators = Psg()
    emulators.write_wave_while_playing = True  # the MAME/Mednafen reading
    fill_wave(emulators, 0, [3] * 32)
    start(emulators, 0, 0x100)
    w(emulators, 6, 0x1F)
    assert emulators.channels[0].wave[emulators.channels[0].index] == 0x1F


def test_direct_da_sends_r6_to_the_dac_and_leaves_the_waveform_alone():
    psg = Psg()
    fill_wave(psg, 0, [1] * 32)
    select(psg, 0)
    w(psg, 4, 0x40)  # ON = 0, DDA = 1: write 0 first, as the manual says, to avoid a click
    w(psg, 6, 0)
    w(psg, 4, 0xDF)  # ON = 1, DDA = 1
    w(psg, 5, 0xFF)
    w(psg, 1, 0xFF)
    w(psg, 6, 0x1A)
    assert psg.channels[0].wave == [1] * 32
    assert samples(psg, 0, 10) == [0x1A] * 10
    w(psg, 6, 0x07)
    assert samples(psg, 0, 3) == [7] * 3


def test_the_waveform_advances_every_f_steps_and_f_zero_is_4096():
    psg = Psg()
    fill_wave(psg, 0, list(range(32)))
    start(psg, 0, 3)
    got = samples(psg, 0, 12)
    assert got == [0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3]
    psg2 = Psg()
    fill_wave(psg2, 0, list(range(32)))
    start(psg2, 0, 0)
    assert samples(psg2, 0, 4096) == [0] * 4096
    assert samples(psg2, 0, 1) == [1]


def test_frequency_one_is_the_highest_and_the_output_frequency_follows_the_manual():
    psg = Psg()
    fill_wave(psg, 0, list(range(32)))
    start(psg, 0, 1)
    assert samples(psg, 0, 4) == [0, 1, 2, 3]
    # f = 3.58 MHz / (32 x F): a 32-word cycle of F steps each
    psg2 = Psg()
    fill_wave(psg2, 0, [0] * 31 + [31])
    start(psg2, 0, 100)
    got = samples(psg2, 0, 3200 * 2)
    rises = [i for i in range(1, len(got)) if got[i] == 31 and got[i - 1] == 0]
    assert rises[1] - rises[0] == 3200


def test_manual_attenuation_example_12_db_left_and_silent_right():
    """[mfr 2.3] R1 = $C8, AL high bits E, R5 = $F8: -12 dB left, -45 dB (no sound) right."""
    psg = Psg()
    fill_wave(psg, 0, [31] * 32)
    start(psg, 0, 10, control=0x80 | 0x1D, balance=0xF8)
    w(psg, 1, 0xC8)
    assert psg.attenuation(0, 0) == 8  # 8 units of 1.5 dB = 12 dB
    assert psg.attenuation(0, 1) >= 30  # 45 dB or more
    assert psg._levels[psg.attenuation(0, 1)] == 0.0
    assert psg._levels[8] == pytest.approx(10 ** (-12 / 20))


@pytest.mark.parametrize("register", ["main", "al", "pan"])
def test_a_zero_register_silences_the_channel_manual_2_3(register):
    psg = Psg()
    fill_wave(psg, 0, [31] * 32)
    start(psg, 0, 10, control=0x9F, balance=0xFF)
    w(psg, 1, 0xFF)
    assert psg.attenuation(0, 0) == 0
    if register == "main":
        w(psg, 1, 0x00)
    elif register == "al":
        w(psg, 4, 0x80)
    else:
        w(psg, 5, 0x00)
    assert psg.attenuation(0, 0) >= 30


def test_key_on_restarts_the_counter_and_a_channel_that_is_off_makes_no_sound():
    psg = Psg()
    fill_wave(psg, 0, list(range(32)))
    start(psg, 0, 5, control=0x1F)  # ON = 0
    assert samples(psg, 0, 3) == [-1, -1, -1]
    w(psg, 4, 0x9F)
    assert samples(psg, 0, 5) == [0] * 5 and samples(psg, 0, 1) == [1]


def test_noise_is_channels_5_and_6_only_and_the_complement_sets_the_period():
    psg = Psg()
    for ch in (4, 5):
        fill_wave(psg, ch, [20] * 32)
        start(psg, ch, 10)
    select(psg, 4)
    w(psg, 7, 0x80 | 0x1D)  # NF = complement of $1D = 2: a step every 128 steps
    select(psg, 3)
    w(psg, 7, 0x80)  # channel 4 has no noise: ignored
    assert psg.channels[3].noise_control == 0
    first = samples(psg, 4, 300)
    assert set(first) <= {0, 31}
    changes = [i for i in range(1, len(first)) if first[i] != first[i - 1]]
    assert all((c % 128) == 1 or c % 128 == 0 for c in changes)  # only at multiples of 128 + phase
    assert samples(psg, 5, 8) == [20] * 8  # channel 6 stays on its waveform


def test_noise_shift_register_taps_18_bits_from_seed_1():
    psg = Psg()
    lfsr = 1
    seen = []
    for _ in range(40):
        seen.append(lfsr & 1)
        bit = (lfsr ^ lfsr >> 1 ^ lfsr >> 11 ^ lfsr >> 12 ^ lfsr >> 17) & 1
        lfsr = lfsr >> 1 | bit << 17
    assert seen[:3] == [1, 0, 0]
    fill_wave(psg, 4, [0] * 32)
    start(psg, 4, 10)
    select(psg, 4)
    w(psg, 7, 0x80 | 0x1F)  # NF = the complement of $1F = 0: undefined in the manual (C17)
    before = psg.channels[4].lfsr
    runs(psg, 33)
    assert psg.channels[4].lfsr != before  # clocked every 32 steps


def test_lfo_needs_both_channels_and_modulates_channel_1_by_channel_2s_wave():
    psg = Psg()
    fill_wave(psg, 0, list(range(32)))
    fill_wave(psg, 1, [16 + 3] * 32)  # +3
    start(psg, 0, 100)
    select(psg, 1)
    w(psg, 2, 7)
    w(psg, 3, 0)
    w(psg, 5, 0xFF)
    w(psg, 8, 4)  # LFO frequency
    w(psg, 9, 0x01)  # LF CTL 1: add the wave as is
    assert psg._lfo_modulating() is False  # channel 2 is off: no modulation
    w(psg, 4, 0x9F)
    assert psg._lfo_modulating() is True
    assert psg._period(0) == 103
    w(psg, 9, 0x02)
    assert psg._period(0) == 100 + (3 << 2)
    w(psg, 9, 0x03)
    assert psg._period(0) == 100 + (3 << 4)
    assert psg._period(1) == 7 * 4  # [mfr 2.2.2] ch 2's counter is F2 x FLF long
    w(psg, 8, 0)
    assert psg._period(1) == 7 * 256


def test_lfo_negative_waveform_values_subtract_and_the_sum_is_12_bits():
    psg = Psg()
    fill_wave(psg, 1, [0] * 32)  # 0 means -16 [mfr table]
    start(psg, 0, 100)
    select(psg, 1)
    w(psg, 4, 0x9F)
    w(psg, 9, 0x01)
    assert psg._period(0) == 84
    psg.channels[0].frequency = 4
    assert psg._period(0) == (4 - 16) & 0xFFF  # wraps in 12 bits (U6)


def test_lf_trg_resets_channel_2s_address_and_halts_the_modulation():
    psg = Psg()
    fill_wave(psg, 1, list(range(32)))
    start(psg, 0, 100)
    start(psg, 1, 2)
    w(psg, 9, 0x01)
    runs(psg, 20)
    assert psg.channels[1].index != 0
    w(psg, 9, 0x81)
    assert psg.channels[1].index == 0
    assert psg._lfo_modulating() is False
    before = psg.channels[1].index
    runs(psg, 50)
    assert psg.channels[1].index == before  # halted while LF TRG is set


def test_step_stream_runs_add_up_and_state_is_constant_inside_a_run():
    psg = Psg()
    fill_wave(psg, 0, list(range(32)))
    start(psg, 0, 7)
    total = 0
    for n, state in runs(psg, 1000):
        total += n
        assert state[0][0] >= 0
    assert total == 1000


def test_writes_take_effect_at_the_step_their_master_clock_falls_in():
    psg = Psg()
    fill_wave(psg, 0, [10] * 32)
    start(psg, 0, 0x100)
    psg.write(1, 0xFF, 6 * 100 + 5)  # in step 100
    assert psg.step == 100
    psg2 = Psg()
    psg2.write(0, 0, 6 * 5)
    assert psg2.step == 5


def test_host_rate_output_averages_the_step_stream():
    psg = Psg(rate_hz=44100.0)
    fill_wave(psg, 0, [31] * 32)
    start(psg, 0, 10)
    w(psg, 1, 0xFF)
    out = psg.take_samples(6 * 81_000)
    assert 995 <= len(out) <= 1000  # 81,000 steps at 81.17 steps a sample
    assert len(set(out[5:])) == 1 and out[10][0] == out[10][1] > 0
    assert psg.rate_hz == 44100.0
