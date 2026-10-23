# The HuC6280's PSG: six wavetable channels (board-owned module)

Tiers: **[mfr]** Hudson's *HuC6280 CMOS Programmable Sound Generator Manual* (37 KB of text,
`reference/src/turbografx-mister/docs/`), **[hw]** MacDonald `pcetech.txt` §10 and §2.4, **[emu]**
MAME `src/devices/sound/c6280.cpp`, Mednafen `hw_sound/pce_psg/pce_psg.cpp`, ares
`ares/pce/psg/`, Mesen2 `Core/PCE/PcePsg*.cpp`. **No hardware audio capture is pinned**: the PSG
has a manufacturer document and emulators, nothing between. `pce-devel/PCE_Soundtest` ("a quick test
of HuC6280 vs HuC6280A differences", unknown provenance) is a candidate program, not yet read.

Placement: the PSG is on the CPU die but nothing else uses it, so it is a **board module** (`psg`
package, behind an import-boundary test and a pin-shaped interface, as gameboy-python keeps its APU),
reached through `$FF:0800-0BFF` ([memory-map.md](memory-map.md)). The sibling `huc6280-python`
core does not own it (recommendation; core Phase 0 may differ).

## Registers (`$0800-$0809`, 16-byte mirror; the whole block returns the I/O buffer on read) [mfr]

Numbering trap: Hudson's manual numbers channels **1-6**, emulators 0-5. "ch.1/ch.2" below are
channels 0 and 1.

| Reg | Address | Scope | Contents |
| --- | --- | --- | --- |
| R0 | `$0800` | global | channel select (0-5 meaningful) for R2-R7 |
| R1 | `$0801` | global | main amplitude: LMAL (7-4), RMAL (3-0); 3 dB per step |
| R2/R3 | `$0802/3` | channel | 12-bit frequency `F`, `F = 0` forbidden (MacDonald: `$000` is the lowest frequency, `$001` the highest) |
| R4 | `$0804` | channel | bit 7 channel on, bit 6 DDA, bits 4-0 amplitude AL (1.5 dB per step) |
| R5 | `$0805` | channel | LAL (7-4), RAL (3-0); 3 dB per step |
| R6 | `$0806` | channel | waveform data port, 5 bits x 32 words |
| R7 | `$0807` | ch 4, 5 only | bit 7 noise enable, bits 4-0 noise frequency |
| R8 | `$0808` | global | LFO frequency |
| R9 | `$0809` | global | bit 7 LFO trigger/reset, bits 1-0 LFO control (0 off, 1 / 2 / 3 = add the modulating wave shifted by 0 / 2 / 4 bits) |

Output frequency `f = fmaster / (2 x 32 x F)`, where Hudson's `fmaster` is 7.16 MHz; MacDonald says
the clock is master/6 = 3.58 MHz and "all formulas multiply by two": **the same number**, so
no conflict (and the PSG runs at master/6 regardless of CPU speed). Noise clock
`fmaster / (2 x 32 x 2 x NF)` with `NF` the **complement** of the 5 bits (NF = 0 undefined).

## Mixing and amplitude [mfr]

Each channel's level is the sum of three attenuations: main (R1 L/R), channel (AL's high 4 bits)
and balance (R5 L/R), in 3 / 1.5 / 3 dB units; the chip's dynamic range is "about 45 dB (circuit
design value)" and nothing is output past it (a leak "because of device characteristics" is
acknowledged). Hudson's worked example: R1 = `$C8`, AL = `$E`, R5 = `$F8` gives -12 dB left and
-45 dB (silent) right. The exact attenuation table is not in the manual (it gives dB steps only):
emulators carry their own tables (MAME `c6280.cpp`, Mednafen `pce_psg.cpp`; not compared
here) so **the numeric output level is emulator-derived, tier 5, until a measurement exists (U6)**.

## Waveform RAM, DDA, noise, LFO

- **Write data mode** (on = 0, DDA = 0): each R6 write stores a word and advances the 5-bit address;
  writes while the channel is **on** are ignored and do not move the address [hw].
  **DDA 1 then 0** resets the address to 0 (regardless of the other R4 bits) [hw, mfr].
- **Direct D/A** (on = 1, DDA = 1): each R6 write goes straight to the DAC and is held (the
  waveform RAM is untouched); the counter is reset. Hudson: set DDA first with R6 = 0 or AL = 0 to
  avoid a click. This is how sampled speech and drums are played.
- **Noise** (channels 4 and 5): when R7 bit 7 is set the channel outputs pseudo-random square noise
  from a shift register (the polynomial is not documented: an emulator choice, U6).
- **LFO**: the LFO frequency register combines with channel 1's `R2/R3` into a 20-bit divider that
  steps the **modulating** channel's (ch.2 in Hudson's numbering = index 1) waveform; its 5-bit
  sample (sign in bit 4) shifted by LF CTL is **added to channel 0's frequency**. Active only when
  both channels are on; channel 1 still sounds at its own amplitude. R9 bit 7 resets and halts it.
  Hudson's table gives the sample-to-offset mapping (`$10` = 0, `$1F` = +15, `$0F` = -1, `$00` = -16).

## Audio out

Stereo, one DAC per side; no sample rate exists (an analogue output). The board produces samples
by the list-of-sources socket ([sockets.md](sockets.md)): the PSG is the first `AudioSource`, with
its own native rate (master/6 per output step is a natural base: a channel's wave counter steps at
that rate) and a resampler to the host rate **outside** the reference path. The reference check is the
unresampled step stream compared with an emulator referee at native rate, as ym2612-python did
against Nuked-OPN2.

## Judge for milestone 4

No hardware-tier judge exists. Order: Hudson manual (mfr) for every documented register behaviour;
MacDonald's tests for the quirks in his §10; then emulator referees at native step rate:
MAME's `c6280` (BSD-3) and Mednafen's are the two readable ones, **their disagreement is a research
question, not a verdict**. A raw-step differential between two emulators proves only that they agree.
