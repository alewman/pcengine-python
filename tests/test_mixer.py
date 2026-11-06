"""Socket 9: the board mixes `audio_sources` (docs/issues/0003)."""

from pcengine_python.board import Board
from pcengine_python.machine import MASTER_HZ
from pcengine_python.mixer import Mixer


class Source:
    def __init__(self, rate_hz, gain, per_call):
        self.rate_hz, self.gain, self.per_call = rate_hz, gain, per_call
        self.applies_gain = False

    def take_samples(self, mclk):
        return list(self.per_call.pop(0)) if self.per_call else []


def test_sources_are_summed_with_their_gain_and_clipped():
    a = Source(44100.0, 0.5, [[(1000, -1000), (2000, 0)]])
    b = Source(44100.0, 1.0, [[(30000, 30000), (30000, -30000)]])
    out = Mixer([a, b]).take(0)
    assert out == [(30500, 29500), (31000, -30000)]
    c = Source(44100.0, 1.0, [[(32767, -32768)]])
    d = Source(44100.0, 1.0, [[(32767, -32768)]])
    assert Mixer([c, d]).take(0) == [(32767, -32768)]


def test_a_source_that_applies_its_own_gain_is_not_scaled_twice():
    a = Source(44100.0, 0.5, [[(1000, 1000)]])
    a.applies_gain = True
    assert Mixer([a]).take(0) == [(1000, 1000)]


def test_only_what_every_source_has_produced_is_emitted_and_the_rest_waits():
    a = Source(44100.0, 1.0, [[(1, 1), (2, 2), (3, 3)], [(4, 4)]])
    b = Source(44100.0, 1.0, [[(10, 10)], [(20, 20), (30, 30)]])
    mixer = Mixer([a, b])
    assert mixer.take(0) == [(11, 11)]
    assert mixer.take(0) == [(22, 22), (33, 33)]


def test_a_source_at_another_rate_is_held_up_to_the_output_rate():
    slow = Source(22050.0, 1.0, [[(5, 5), (7, 7)]])
    assert Mixer([slow]).take(0) == [(5, 5), (5, 5), (7, 7), (7, 7)]


def test_the_board_mixes_its_psg_and_an_added_source():
    board = Board()
    extra = Source(44100.0, 1.0, [])

    board.audio_sources.append(extra)
    board.advance(MASTER_HZ // 100)
    assert board.take_audio() == []  # `extra` has produced nothing: nobody runs ahead of it
    extra.per_call.append([(7, 7)] * 100000)
    mixed = board.take_audio()
    assert mixed and all(left == 7 for left, _ in mixed)  # the silent PSG adds zeros
