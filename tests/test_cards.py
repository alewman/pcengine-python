"""HuCard mirroring (docs/cartridge.md): tier 3-4, confirmed only by games running."""

import pytest

from pcengine_python.cards import BANK, RomCard, bank_map, strip_copier_header


def image(banks):
    """An image whose every 8 KiB bank is filled with its own number."""
    return b"".join(bytes([i]) * BANK for i in range(banks))


def window(card):
    return [card.read(bank << 13, 0) for bank in range(128)]


def test_256_kib_mirrors_four_times_through_the_window():
    assert window(RomCard(image(32))) == [b % 32 for b in range(128)]


def test_512_kib_is_straight_then_the_upper_half_twice():
    got = window(RomCard(image(64)))
    assert got[:64] == list(range(64))
    assert got[64:] == [32 + (b % 32) for b in range(64)]
    assert got[64:96] == got[96:]
    assert got[64] == 32  # the upper 256 KiB


def test_384_kib_first_256_twice_then_the_last_128_four_times():
    got = window(RomCard(image(48)))
    assert got[:32] == list(range(32)) and got[32:64] == list(range(32))
    assert got[64:80] == list(range(32, 48))
    assert got[64:80] == got[80:96] == got[96:112] == got[112:128]


def test_1_mib_fills_the_window_exactly():
    assert window(RomCard(image(128))) == list(range(128))


def test_768_kib_repeats_modulo_the_image_u18():
    assert window(RomCard(image(96))) == [b % 96 for b in range(128)]


def test_copier_header_is_stripped():
    data = bytes(512) + image(32)
    assert strip_copier_header(data) == image(32)
    assert RomCard(data).read(0, 0) == 0


def test_ragged_images_are_padded_and_empty_images_refused():
    card = RomCard(b"\x01" * (BANK + 5))
    assert card.read(BANK + 6, 0) == 0
    with pytest.raises(ValueError):
        RomCard(b"")


def test_claims_the_1_mib_window_pages():
    assert RomCard(image(32)).claims() == [(0x0000, 0x0FFF)]


def test_bank_map_is_a_pure_function():
    assert len(bank_map(32)) == 128
