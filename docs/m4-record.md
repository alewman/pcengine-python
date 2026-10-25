# Milestone 4 record: the PSG, and the timer finished

Status (2026-10-24): **built; the step stream is reproduced with 0 differences by each referee's own
switches, and the differences that remain between the manual's reading and each referee are named.**
Every PSG result is **provisional, tier 5**: there is no hardware audio reference anywhere (no capture, no
measurement of the attenuation, the noise or the LFO), only Hudson's manual (tier 3, no numbers for
the curve), MacDonald's tests (tier 2) and two emulators.

## Built

`psg/chip.py` (the `psg` package, import-boundary tested, board-owned; nothing split into a core):
six channels with 32 x 5-bit waveform RAM, 12-bit frequency (0 = 4096), write-data / reset-counter /
mixing / DDA modes, noise on channels 5 and 6 (18-bit shift register, taps 0, 1, 11, 12, 17, period from
the complement of NF), the LFO (channel 2's wave modulates channel 1: shift 0, 2 or 4, F2 x FLF counter),
main/channel/pan attenuation in 1.5 dB units with the manual's 45 dB cut-off, a host-rate box average
for the `AudioSource` list (`Board.audio_sources[0]`). It is event-driven: output is constant between
address steps, so a window of millions of steps costs thousands of events; listeners get
`(steps, [(sample, units left, units right)] x 6)`. 19 + 1 tests (`tests/test_psg.py`,
`tests/test_sockets.py`) against the manual and pcetech: write data and the start address, DDA, the
frequency formula, the manual's 12 dB / 45 dB attenuation example, noise period and taps, LFO periods,
LF TRG, key-on, the timing of writes (the step their master clock falls in).

## The judges

**Referees**: MAME 0.285's `c6280.cpp` and Mednafen's `pce_psg.cpp`, both compiled **unchanged** from the pinned
trees against small shims (`scripts/psg_referees/`: `emu.h` stand-in for MAME, `mednafen.h` for
Mednafen, a harness each; built by `build_mame.py` and `build_mednafen.py`; no referee file is
copied) and driven one PSG step (3.58 MHz) at a time from a register log. **Recorder**:
`scripts/psg_record.py` runs a card on the board with the real core and logs each write to `$0800-$0809`
with its master clock (`tests/psg_logs/` keeps a 6.9 KB excerpt). **Comparison**:
`scripts/psg_compare.py`: the model's per-channel digital state per step is put through each referee's
own numeric curve (MAME's table and `sample - 16`; Mednafen's `dbtable`, HuC6280 centring), so equal state
is equal integers and a difference is a difference of *behaviour*, not of scale.

Five games, 900 frames each, the window 16,100,000-18,100,000 steps (4.50-5.06 s, 2 M steps):
Aero Blasters, Alien Crush, Blazing Lazers, Bonk's Adventure, Samurai-Ghost (R-Type never turns a channel on
in its first 15 s).

| Game (writes in the 900 frames) | ours[MAME's switches] vs MAME | ours[Mednafen's switches] vs Mednafen (steps excluded for C21) |
| --- | --- | --- |
| Aero Blasters (21,507) | 0 differences | 0 (305,017) |
| Alien Crush (28,538) | 0 | 0 (308,995) |
| Blazing Lazers (124,580) | 0 | 0 (317,339) |
| Bonk's Adventure (131,674) | 0 | 0 (57,184) |
| Samurai-Ghost (33,590) | 0 | 0 (325,177) |

(`tests/test_psg_referees.py` repeats it on the excerpt, 3 M steps: 0 differences, both referees.)

With **the manual's and pcetech's readings** (the model's defaults) the same windows differ from MAME in
0 steps (Alien Crush, Blazing Lazers), 62,403 (Bonk's Adventure), 63,794 (Samurai-Ghost) and 1,038,273 (52 %,
Aero Blasters) of 2 M, and from Mednafen in 28-97 % of the steps. Which switch accounts for which steps, each reverted alone in the referee's
variant (steps that then differ, of 2 M):

| Switch | MAME | Mednafen |
| --- | --- | --- |
| C22 key-on (MAME reloads the counter; Mednafen steps the address) | 0 | **555,129 to 1,941,080 in every game** |
| C20 noise shift register runs always (Mednafen) or only while a channel plays noise (MAME) | Aero Blasters 1,011,156; Samurai-Ghost 63,794 | 0 |
| C14 silence at 45 dB (manual) or 46.5 dB (both emulators) | Aero Blasters 56,007 | Aero Blasters 50,670 |
| C13 R6 data while a channel plays (pcetech ignores; both emulators store) | Bonk's Adventure 62,403 | Bonk's Adventure 121,081 |
| C15 R1/R5 table, C16 DDA latch, C17 noise NF = 0, C18-C19, C23 LFO details | 0 | 0 |

The last row's switches are **not exercised** by these windows: the model and the referees agree
only where the games go. C15 (the emulators' shared table steps 1.5 dB between R1/R5 nibbles 7 and 8 and
4.5 dB after; the manual says 3 dB throughout), C16, C17, C18, C19, C23 and Mednafen's high-frequency
averaging of F <= 3 (C24: not modelled) wait for a game that uses them.

### The two referees disagree with each other (a finding)

Run through the model's two variants, MAME and Mednafen differ on **nearly every step** of every window
(1.99 to 2.0 M of 2 M), and from the first key-on: Alien Crush's first differing step is **1,258,514
(0.3516 s)**, channel 3, sample 9 against 14; Blazing Lazers' is **242,446 (0.0677 s)**, channel 1, 19 against
16: the first time a waveform channel is switched on. **Cause: C22.** Mednafen steps the waveform
address once when ON goes 0 -> 1 and keeps the counter; MAME reloads the counter and keeps the
address, so every note starts one position and some counter steps apart, for good. Flipping only
that switch to MAME's value leaves 0 differing steps in Alien Crush, 556 in Blazing Lazers, 2,154 in Bonk's, 63,794 in Samurai-Ghost
and 1,011,156 in Aero Blasters (the latter two are C20). Neither the manual nor pcetech says
what key-on does; the model follows MAME's (no step) and names it. Their volume paths also differ
(**C21**): MAME applies R1/R4/R5 at once; Mednafen latches them through a rotating 32-slot pipeline that
takes up to about 3,000 steps (0.8 ms) to reach a channel. The model applies them at once; Mednafen's
windows after a volume write (9,000 steps) are excluded and counted in the table above.

## Timer: U24 closed as far as the sources go

Hudson's manual 2.7 (tier 3): stopping the timer resets the prescaler and the counter loads on the 0 -> 1 change,
so the first tick is one full prescaler period (1024 cycles of master/3 = 3,072 master clocks) after the
enabling write, and a stop-and-restart always starts a fresh period; enabling an enabled timer changes
nothing. Two tests (`test_cpu_io.py`). Still tier 5 and unmodelled: Mednafen's reload one master clock after the
underflow (MAME has none; pcetech 2.2 "reloaded when it occurs", as here), and the manual's note that the
count can read invalid while it changes.

## New entries

C13-C24 as above (also in the brief); **U6** narrowed: the noise taps agree between the emulators, the
attenuation is 1.5 dB a unit by the manual and both emulators (the curve's absolute scale and the DAC's
centre, `sample - 16` or `2 x sample`, are the emulators' own); the LFO and noise details are the
named switches. **U28**: the output level of the DAC around its centre (no source).
