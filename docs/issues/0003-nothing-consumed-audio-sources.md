# 0003: nothing consumed `Board.audio_sources`

Raised 2026-11-05 by `pcenginecd-python` (M7, finding S3); fixed 2026-11-06. Status: **closed** by a new
module and one board method; the PC Engine's video and CPU results are unchanged.

## What the CD needed and the board did not give

[docs/sockets.md](../sockets.md) socket 9 lists audio sources (`rate_hz`, `gain`, `take_samples(mclk)`),
PSG first, and the CD adds CD-DA (44.1 kHz) and ADPCM. The list existed; nothing called `take_samples`
on more than the PSG, so a host had to mix by hand and every add-on would have mixed differently.

## The change

- `pcengine_python/mixer.py`: `Mixer(sources, output_hz=44100)`. One queue per source; a source at another
  rate is held (zero-order) up to the output rate; `gain` is applied unless the source says
  `applies_gain` (the PSG scales by its own `gain` inside, so `Psg.applies_gain = True`); samples are
  summed and clipped to 16 bits; only as many samples as **every** source has produced are emitted (a
  source that returns nothing stalls the mix: sources emit zeros when silent).
- `Board.mixer` (over the board's list itself, so add-ons' appends count) and `Board.take_audio()`.

## Gate

`tests/test_mixer.py` (sum, clip, gain, own-gain, waiting queues, rate hold, the board with an added
source). Video: captured frames of Alien Crush (USA) and the Covell CPU test over 150 frames are identical
before and after; the suite passes on CPython and PyPy; the 18-picture gate was not rerun (no VDC/VCE code).
Levels and the hold are not hardware facts: the sources' own streams at their own rates are the reference.
