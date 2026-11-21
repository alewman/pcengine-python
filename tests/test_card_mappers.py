"""SF2, Populous, Tennokoe and the card factory (docs/cartridge.md; emulator tier for all three)."""

import hashlib
import zipfile
import zlib
from pathlib import Path

import pytest

from pcengine_python.cards import (
    BANK,
    PopulousCard,
    RomCard,
    Sf2Card,
    TennokoeCard,
    make_card,
)


def banks(n):
    """An image whose every 8 KiB bank holds its own number in every byte (mod 251)."""
    return b"".join(bytes([i % 251]) * BANK for i in range(n))


def read(card, bank, offset=0):
    return card.read((bank << 13) + offset, 0)


def test_sf2_first_512k_fixed_and_the_upper_window_follows_the_latch():
    data = banks(320)  # 2.5 MiB = 320 banks
    card = Sf2Card(data)
    assert [read(card, b) for b in (0, 0x3F)] == [0, 63]
    assert [read(card, b) for b in (0x40, 0x7F)] == [64, 127]  # page 0 = ROM $80000-$FFFFF
    for page in (1, 2, 3):
        card.write(0x1FF0 + page, 0, 0)  # bank $00, $1FF0-$1FF3
        assert read(card, 0x40) == (64 + 64 * page) % 251
        assert read(card, 0x7F) == (127 + 64 * page) % 251
    assert read(card, 0x3F) == 63  # the fixed half never moves


def test_sf2_latch_decodes_1ff0_to_1fff_and_masks_by_the_page_count():
    card = Sf2Card(banks(320))
    card.write(0x1FF7, 0, 0)  # 7 & 3 = 3 [emu: Mednafen masks; MAME decodes only $1FF0-$1FF3]
    assert card.page == 3
    card.write(0x1FEF, 0, 0)  # outside the latch
    card.write(0x2FF0, 0, 0)  # another bank-0 address: not the latch
    assert card.page == 3
    card.reset(__import__("pcengine_python.sockets", fromlist=["ResetKind"]).ResetKind.POWER_ON)
    assert card.page == 0


def test_sf2_extended_images_have_more_pages_and_need_a_power_of_two():
    card = Sf2Card(banks(64 * 9 + 8))  # 512 KiB + 8.x pages of 512 KiB: rounded up to 16 pages
    assert card.page_mask == 15
    card.write(0x1FFF, 0, 0)
    assert card.page == 15
    assert read(card, 0x40) == 0  # past the image: zero padding


def test_sf2_refuses_a_small_image():
    with pytest.raises(ValueError):
        Sf2Card(banks(64))


def test_populous_ram_is_four_unmirrored_banks_at_40_43_and_the_rest_is_rom():
    data = bytearray(banks(32))
    data[0x1F26 : 0x1F26 + 8] = b"POPULOUS"
    card = make_card(bytes(data))
    assert isinstance(card, PopulousCard)
    assert read(card, 0x40) == 0xFF  # Mednafen's power-up fill
    card.write((0x40 << 13) + 5, 0xAA, 0)
    card.write((0x43 << 13) + 5, 0xBB, 0)
    assert read(card, 0x40, 5) == 0xAA and read(card, 0x43, 5) == 0xBB
    assert read(card, 0x41, 5) == 0xFF  # a different bank: not a mirror
    assert read(card, 0x44) == 4 % 32 % 251  # beyond the RAM: the ROM mirror (32 banks)
    card.write(0x10, 0x99, 0)  # ROM ignores writes
    assert read(card, 0, 0x10) == 0


def test_tennokoe_bank_ram_is_locked_until_a_nonzero_write_to_f0000():
    card = TennokoeCard(banks(64))
    assert read(card, 0x40, 3) == 0xFF
    card.write(0x80000 + 3, 0x11, 0)  # locked: ignored
    card.write(0xF0000, 1, 0)  # unlock [emu: MAME, "a complete guess"]
    card.write(0x80000 + 3, 0x11, 0)
    assert read(card, 0x40, 3) == 0x11
    assert read(card, 0x47, 3) == 0x11  # mirrored every 8 KiB through $8FFFF
    assert read(card, 0x20) == 32  # the ROM below is untouched
    assert read(card, 0x50) == 0xFF  # nothing decoded above it
    card.write(0xFFFFF, 0, 0)  # lock again
    assert read(card, 0x40, 3) == 0xFF


def test_the_factory_picks_plain_for_everything_else_and_strips_a_copier_header():
    assert type(make_card(banks(48))) is RomCard
    assert type(make_card(bytes(512) + banks(32))) is RomCard
    assert isinstance(make_card(banks(320)), Sf2Card)


@pytest.mark.parametrize("banks_count", [9, 15, 91, 96, 98, 109])
def test_odd_sizes_repeat_modulo_the_image_u18(banks_count):
    """[emu: Mednafen `x % (len / 8192)`] the odd sizes of the library (72 KiB .. 872 KiB)."""
    card = RomCard(banks(banks_count))
    assert [read(card, b) for b in range(128)] == [b % banks_count % 251 for b in range(128)]


SF2_ZIP = Path(
    "/data/emu/source/myrient.erista.me/files/No-Intro/NEC - PC Engine - TurboGrafx-16/"
    "Street Fighter II' - Champion Edition (Japan).zip"
)


@pytest.mark.skipif(not SF2_ZIP.exists(), reason="BYOR: the No-Intro tree is Aubrey's")
def test_the_real_sf2_card_read_in_place_has_the_documented_hashes():
    with zipfile.ZipFile(SF2_ZIP) as z:
        data = z.read(z.namelist()[0])
    assert zlib.crc32(data) == 0xD15CB6BB
    assert hashlib.sha1(data).hexdigest() == "e757ecdf857803cb46cdf37ecf4596f6eaccdd76"
    card = make_card(data)
    assert isinstance(card, Sf2Card) and card.page_mask == 3
    for page in range(4):
        card.write(0x1FF0 + page, 0, 0)
        assert card.read(0x80000, 0) == data[0x80000 + page * 0x80000]
        assert card.read(0xFFFFF, 0) == data[0xFFFFF + page * 0x80000]
