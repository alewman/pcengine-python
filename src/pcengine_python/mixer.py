"""The audio mixer: sums the board's `audio_sources` (socket 9) into one stereo stream.

The sockets list a source as `(rate_hz, gain, take_samples(mclk))`; until this module nothing
consumed the list (add-on finding S3, docs/issues/0003). A source answers `take_samples(mclk)`
with the stereo samples it produced since the last call, one per 1/`rate_hz` second (zeros when
silent, so the mixer keeps its place). The mixer keeps one queue per source, turns each source's
stream into the output rate, applies `gain` (unless the source applies its own: `applies_gain`),
sums sample for sample and clips to 16 bits. It emits only as many samples as every source has
produced, so the sources need not agree on how many each call returns.

A source at another rate is held (zero-order) up to the output rate: no filter, no interpolation.
The reference for a source is its own stream at its own rate; this is a host-side convenience
(docs/psg.md says the same of the PSG).
"""

from __future__ import annotations

from collections.abc import Sequence

OUTPUT_HZ = 44_100.0


class _Lane:
    def __init__(self) -> None:
        self.queue: list[tuple[float, float]] = []
        self.carry = 0.0


class Mixer:
    def __init__(self, sources: list, output_hz: float = OUTPUT_HZ) -> None:
        self.sources = sources  # the board's list itself: add-ons append to it
        self.output_hz = output_hz
        self._lanes: dict[int, _Lane] = {}

    def take(self, mclk: int) -> list[tuple[int, int]]:
        """Mixed stereo samples at `output_hz` that every source has produced up to `mclk`."""
        lanes = []
        for source in self.sources:
            lane = self._lanes.setdefault(id(source), _Lane())
            lanes.append((source, lane))
            self._feed(source, lane, source.take_samples(mclk))
        if not lanes:
            return []
        count = min(len(lane.queue) for _, lane in lanes)
        out = [[0.0, 0.0] for _ in range(count)]
        for source, lane in lanes:
            gain = 1.0 if getattr(source, "applies_gain", False) else float(source.gain)
            taken, lane.queue = lane.queue[:count], lane.queue[count:]
            for mix, (left, right) in zip(out, taken, strict=True):
                mix[0] += left * gain
                mix[1] += right * gain
        return [(_clip(left), _clip(right)) for left, right in out]

    def _feed(self, source, lane: _Lane, samples: Sequence[tuple[int, int]]) -> None:
        if float(source.rate_hz) == self.output_hz:
            lane.queue.extend(samples)
            return
        step = self.output_hz / float(source.rate_hz)
        for sample in samples:
            lane.carry += step
            repeats = int(lane.carry)
            lane.carry -= repeats
            lane.queue.extend([sample] * repeats)


def _clip(value: float) -> int:
    return max(-32768, min(32767, round(value)))
