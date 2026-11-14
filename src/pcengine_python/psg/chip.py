"""The HuC6280's programmable sound generator: six wavetable channels, noise, LFO, DDA.

Written from Hudson's *HuC6280 PSG Manual* (tier 3: "manual" below) and MacDonald's pcetech §10 and
§2.4 (tier 2); where those are silent the choice is named in a comment with a U/C number
(docs/m4-record.md) and may be changed by a class attribute. There is no hardware audio reference
anywhere: **every output of this module is provisional, tier 5**.

Time: one *step* is one PSG clock, master/6 = 3.58 MHz [pcetech 2.4; the manual's "7.16 MHz" and
its formulas' factor 2 agree]. A channel's waveform index advances every F steps (F = the 12-bit
frequency, 0 meaning 4096) [pcetech 10: $000 is the lowest frequency; manual 2.2.1:
f = fmaster / (2 x 32 x F)]. The model is event-driven: output is constant between index changes,
so `advance_to` hands the listener runs `(steps, [(sample, units_left, units_right) x 6])`.

Within a step every channel's output is taken from the state at the start of the step and the
counters then advance together (the manual says nothing of an order): ch 1's modulation of ch 0
therefore reads ch 2's sample *before* ch 2 advances in the same step.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

PSG_CLOCK_DIVIDER = 6  # master clocks per step [pcetech 2.4]
NOISE_TAPS = (0, 1, 11, 12, 17)  # [emu: MAME and Mednafen agree; MacDonald's research] U6
SILENT_UNITS = 30  # [mfr 2.3] about 45 dB below the maximum "none is output"; 1 unit = 1.5 dB


@dataclass
class Channel:
    frequency: int = 0
    control: int = 0  # bit 7 ON, bit 6 DDA, bits 4-0 AL
    balance: int = 0
    wave: list[int] = field(default_factory=lambda: [0] * 32)
    index: int = 0
    latch: int = 0  # the DAC value held by DDA mode
    noise_control: int = 0
    counter: int = 1  # steps until the waveform index advances
    noise_counter: int = 1
    lfsr: int = 1
    override: int | None = None  # C16: a sample forced by an R6 write until the next address step

    @property
    def on(self) -> bool:
        return bool(self.control & 0x80)

    @property
    def dda(self) -> bool:
        return bool(self.control & 0x40)


class Psg:
    # The points on which the manual and pcetech are silent or the two readable emulators differ
    # (docs/m4-record.md, C13-C23). Each default below follows the manual or pcetech where they
    # speak, else the larger share of the sources; `VARIANTS` flips them to one emulator's way.
    #: C13: data written to R6 while a channel is ON and not DDA. pcetech: ignored, the index does
    #: not move. MAME and Mednafen store it in the waveform. True follows the two emulators.
    write_wave_while_playing = False
    #: C16: R6 in DDA mode loads the DAC latch: the manual says whenever DDA is set (also with the
    #: channel off); Mednafen only with the channel on, and it also lets an R6 write while playing
    #: override the sample until the next address step ("tested on a SuperGrafx").
    dda_latch_needs_on = False
    r6_overrides_sample_while_on = False
    #: C22: what key-on (ON 0 -> 1) does to a waveform channel. "reload": the counter restarts
    #: from F, the address stays (MAME). "resume_step": the counter resumes where it stopped and
    #: the address steps once (Mednafen). Neither is in the manual.
    keyon_mode = "reload"
    #: C18: the LFO acts only when channel 2 is on (manual); MAME modulates whatever channel 2 is.
    lfo_requires_ch2_on = True
    #: C19: the LFO frequency register 0: 256 (Mednafen) or 1 (MAME's zero-length counter).
    lfo_zero_multiplier = 256
    #: U6: the modulated frequency wraps in 12 bits (Mednafen) or not (MAME).
    lfo_mask12 = True
    #: C23: LF TRG (R9 bit 7) halts channel 2 whatever LF CTL holds (Mednafen); MAME only with LF
    #: CTL non-zero.
    lf_trg_halts_always = True
    #: C15: R1/R5's table: the manual says 3 dB a step; both emulators share a table in which the
    #: step from 7 to 8 is 1.5 dB and from 8 to 9 4.5 dB (index 8 costs 15 units, not 14). The
    #: sixteen values in `_scale` are that table, as in MAME's c6280.cpp (BSD-3-Clause, Charles
    #: MacDonald; see NOTICE.md).
    scale_table_quirk = False
    #: C14: attenuation at which a channel goes silent, in 1.5 dB units. The manual: 45 dB (30).
    #: Both emulators keep a 31st step (46.5 dB) that is still audible.
    silent_units = 30
    #: False skips the host-rate output (the step stream and the listeners are unaffected).
    render_audio = True
    applies_gain = True  # the mixer (mixer.py) must not apply `gain` a second time
    #: C17: noise frequency NF' = 0 ("undefined" in the manual). MAME clocks the shift register
    #: every step; Mednafen every 32. 32 here.
    noise_zero_period = 32
    #: C20: the noise shift register runs whether or not noise is selected (Mednafen); MAME runs it
    #: only while a channel is playing noise.
    noise_free_running = True

    def __init__(self, rate_hz: float = 44100.0) -> None:
        self.channels = [Channel() for _ in range(6)]
        self.select = 0
        self.balance = 0  # R1
        self.lfo_frequency = 0  # R8
        self.lfo_control = 0  # R9
        self.step = 0  # steps run so far
        self.listeners: list[Callable[[int, list[tuple[int, int, int]]], None]] = []
        # host-rate output (a box average of the step stream; outside the reference path)
        self.rate_hz = rate_hz
        self.gain = 1.0
        # up to 30 + 31 + 30; rebuilt when `silent_units` changes (issue 0004: psg_compare.py
        # sets the switches on an instance after construction)
        self._levels_units = -1
        self._levels: list[float] = []
        self._level_table()
        self._acc = [0.0, 0.0]
        self._phase = 0.0
        self._out: list[tuple[int, int]] = []
        self._noise_period = [0] * 6
        for ch, channel in enumerate(self.channels):
            channel.counter = self._period(ch)
        for ch in (4, 5):
            self._set_noise_period(ch)
            self.channels[ch].noise_counter = 1

    # -- derived values -----------------------------------------------------------------------

    def _lfo_modulating(self) -> bool:
        """[mfr 2.1.10 note] the LFO acts only when channel 1 and 2 are both on; LF TRG halts it."""
        if not self.lfo_control & 3 or self.lfo_control & 0x80:
            return False
        return self.channels[1].on or not self.lfo_requires_ch2_on

    def _period(self, ch: int) -> int:
        channel = self.channels[ch]
        frequency = channel.frequency or 4096
        if ch == 0 and self._lfo_modulating():
            shift = ((self.lfo_control & 3) - 1) * 2  # 0, 2, 4 [mfr 2.1.10]
            modulation = self.channels[1].wave[self.channels[1].index] - 16  # [mfr table]
            frequency = channel.frequency + (modulation << shift)
            frequency = (frequency & 0xFFF or 4096) if self.lfo_mask12 else max(frequency, 1)
        elif ch == 1 and self.lfo_control & 3:
            # [mfr 2.2.2] f_LFO = fmaster / (2x32xF2xFLF)
            frequency *= self.lfo_frequency or self.lfo_zero_multiplier
        return frequency

    def _set_noise_period(self, ch: int) -> None:
        nf = 0x1F - (self.channels[ch].noise_control & 0x1F)  # [mfr 2.3.3] NF is the complement
        self._noise_period[ch] = nf * 64 if nf else self.noise_zero_period  # 2 x 32 x 2 / 2 steps

    def attenuation(self, ch: int, side: int) -> int:
        """Units of 1.5 dB below the maximum for a channel on one side (0 left, 1 right):
        R1 and R5 step 3 dB, R4 1.5 dB [mfr 2.1.2, 2.1.5, 2.1.6, 2.3]. 30 or more is silent."""
        channel = self.channels[ch]
        main = (self.balance >> (4 if side == 0 else 0)) & 0xF
        pan = (channel.balance >> (4 if side == 0 else 0)) & 0xF
        return self._scale(main) + (31 - (channel.control & 0x1F)) + self._scale(pan)

    def _scale(self, nibble: int) -> int:
        """Units below the maximum for an R1/R5 nibble: 2 a step, 30 for 0 [mfr 2.1.2, 2.1.6]."""
        if self.scale_table_quirk:
            return 31 - (0, 3, 5, 7, 9, 11, 13, 15, 16, 19, 21, 23, 25, 27, 29, 31)[nibble]
        return 2 * (15 - nibble)

    # -- the CPU's port ------------------------------------------------------------------------

    def write(self, offset: int, value: int, mclk: int) -> None:
        self.advance_to(mclk // PSG_CLOCK_DIVIDER)
        self._write(offset & 0x0F, value & 0xFF)

    def _write(self, reg: int, value: int) -> None:
        if reg == 0:
            self.select = value & 7
            return
        if reg == 1:
            self.balance = value
            return
        if reg == 8:
            self.lfo_frequency = value  # counters pick up a changed period at their next reload
            return
        if reg == 9:
            if value & 0x80:  # [mfr 2.1.10] LF TRG: ch 2's wave counter and address reset
                self.channels[1].index = 0
                self.channels[1].counter = self._period(1)
            self.lfo_control = value
            return
        if reg > 7 or self.select > 5:
            return  # "no more than 6 channels"
        channel = self.channels[self.select]
        if reg == 2:
            channel.frequency = (channel.frequency & 0xF00) | value
        elif reg == 3:
            channel.frequency = (channel.frequency & 0x0FF) | ((value & 0x0F) << 8)
        elif reg == 4:
            self._write_control(self.select, channel, value)
        elif reg == 5:
            channel.balance = value
        elif reg == 6:
            self._write_wave(channel, value & 0x1F)
        elif reg == 7 and self.select >= 4:
            channel.noise_control = value
            self._set_noise_period(self.select)

    def _write_control(self, ch: int, channel: Channel, value: int) -> None:
        was_dda, was_on = channel.dda, channel.on
        channel.control = value
        if value & 0x40:
            channel.index = 0  # [mfr 2.1.5] DDA: the address counter is reset
        elif was_dda:
            channel.index = 0  # [pcetech 10] reset when DDA goes 1 -> 0
            channel.counter = self._period(ch)
        if channel.on and not was_on and not channel.dda:
            if self.keyon_mode == "reload":
                channel.counter = self._period(ch)
            else:
                channel.index = (channel.index + 1) & 31
        channel.override = None

    def _write_wave(self, channel: Channel, value: int) -> None:
        if channel.dda:
            if channel.on or not self.dda_latch_needs_on:
                channel.latch = value  # [mfr 2.1.7 (3)] "data is transferred directly to the D/A"
        elif not channel.on:
            channel.wave[channel.index] = value  # [mfr 2.1.5] write data mode
            channel.index = (channel.index + 1) & 31
        elif self.write_wave_while_playing:
            channel.wave[channel.index] = value
        if self.r6_overrides_sample_while_on and channel.on:
            channel.override = value

    # -- running --------------------------------------------------------------------------------

    def state(self) -> list[tuple[int, int, int]]:
        """Per channel (sample, units left, units right) for the step about to run; sample is
        -1 for a channel that is off (it contributes nothing)."""
        out = []
        for ch, channel in enumerate(self.channels):
            if not channel.on:
                sample = -1
            elif ch >= 4 and channel.noise_control & 0x80:
                sample = 31 if channel.lfsr & 1 else 0  # [mfr 2.1.8] noise overrides the wave
            elif channel.dda:
                sample = channel.latch
            elif channel.override is not None:
                sample = channel.override
            else:
                sample = channel.wave[channel.index]
            out.append((sample, self.attenuation(ch, 0), self.attenuation(ch, 1)))
        return out

    def advance_to(self, target: int) -> None:
        """Run the steps up to (not including) step `target`."""
        while self.step < target:
            remaining = target - self.step
            n = remaining
            lfo = self._lfo_modulating()
            for ch, channel in enumerate(self.channels):
                if self._clocked(ch, channel):
                    n = min(n, channel.counter)
                if ch >= 4 and (self.noise_free_running or self._plays_noise(channel)):
                    n = min(n, channel.noise_counter)
            if n < 1:
                n = 1
            snapshot = self.state()
            self._emit(n, snapshot)
            self.step += n
            self._tick(n, lfo)

    def _plays_noise(self, channel: Channel) -> bool:
        return channel.on and bool(channel.noise_control & 0x80)

    def _clocked(self, ch: int, channel: Channel) -> bool:
        """[mfr 2.1.5] the waveform address advances only in mixing mode (ON, not DDA); LF TRG
        halts channel 2's counter (Mednafen: whatever the LF CTL bits)."""
        if not channel.on or channel.dda:
            return False
        if ch == 1 and self.lfo_control & 0x80:
            return not self.lf_trg_halts_always and not self.lfo_control & 3
        return True

    def _tick(self, n: int, lfo: bool) -> None:
        # the modulating sample is read before channel 2 moves in the same step
        modulation = self.channels[1].wave[self.channels[1].index]
        for ch, channel in enumerate(self.channels):
            if self._clocked(ch, channel):
                channel.counter -= n
                if channel.counter <= 0:
                    channel.index = (channel.index + 1) & 31
                    channel.override = None
                    if ch == 0 and lfo:
                        shift = ((self.lfo_control & 3) - 1) * 2
                        frequency = channel.frequency + ((modulation - 16) << shift)
                        if self.lfo_mask12:
                            channel.counter = frequency & 0xFFF or 4096
                        else:
                            channel.counter = max(frequency, 1)
                    else:
                        channel.counter = self._period(ch)
            if ch >= 4 and (self.noise_free_running or self._plays_noise(channel)):
                channel.noise_counter -= n
                if channel.noise_counter <= 0:
                    bit = 0
                    for tap in NOISE_TAPS:
                        bit ^= (channel.lfsr >> tap) & 1
                    channel.lfsr = (channel.lfsr >> 1) | (bit << 17)
                    channel.noise_counter = self._noise_period[ch]

    # -- host-rate output ------------------------------------------------------------------------

    def _emit(self, n: int, snapshot: list[tuple[int, int, int]]) -> None:
        for listener in self.listeners:
            listener(n, snapshot)
        if not self.render_audio:
            return
        levels = self._level_table()
        left = right = 0.0
        for sample, ul, ur in snapshot:
            if sample >= 0:
                left += levels[ul] * (sample - 16)
                right += levels[ur] * (sample - 16)
        scale = self.gain / (6 * 16)
        left, right = left * scale, right * scale
        per_sample = 3_579_545 / self.rate_hz
        remaining = float(n)
        while remaining > 0:
            room = per_sample - self._phase
            take = min(room, remaining)
            self._acc[0] += left * take
            self._acc[1] += right * take
            self._phase += take
            remaining -= take
            if self._phase >= per_sample - 1e-9:
                self._out.append(
                    (
                        round(self._acc[0] / per_sample * 32767),
                        round(self._acc[1] / per_sample * 32767),
                    )
                )
                self._acc = [0.0, 0.0]
                self._phase = 0.0

    def _level_table(self) -> list[float]:
        """Amplitude by attenuation units (1.5 dB each), silent from `silent_units` on (C14)."""
        if self._levels_units != self.silent_units:
            self._levels_units = self.silent_units
            self._levels = [
                10 ** (-1.5 * u / 20) if u < self.silent_units else 0.0 for u in range(128)
            ]
        return self._levels

    def take_samples(self, mclk: int) -> list[tuple[int, int]]:
        """Stereo samples at `rate_hz` up to `mclk` since the last call (a box average of the
        step stream; the reference check is the unresampled step stream)."""
        self.advance_to(mclk // PSG_CLOCK_DIVIDER)
        out, self._out = self._out, []
        return out


#: Each readable emulator's way on the disputed points, for scripts/psg_compare.py.
VARIANTS: Mapping[str, Mapping[str, object]] = MappingProxyType(
    {
        "manual": {},
        "mame": {
            "write_wave_while_playing": True,
            "noise_zero_period": 1,
            "noise_free_running": False,
            "keyon_mode": "reload",
            "lfo_requires_ch2_on": False,
            "lfo_zero_multiplier": 1,
            "lfo_mask12": False,
            "lf_trg_halts_always": False,
            "scale_table_quirk": True,
            "silent_units": 31,
        },
        "mednafen": {
            "write_wave_while_playing": True,
            "dda_latch_needs_on": True,
            "r6_overrides_sample_while_on": True,
            "noise_zero_period": 32,
            "noise_free_running": True,
            "keyon_mode": "resume_step",
            "lfo_requires_ch2_on": True,
            "lfo_zero_multiplier": 256,
            "lfo_mask12": True,
            "lf_trg_halts_always": True,
            "scale_table_quirk": True,
            "silent_units": 31,
        },
    }
)
