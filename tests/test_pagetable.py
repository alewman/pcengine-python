import pytest
from pcengine_python.pagetable import PageTable, Ram, Unmapped

from fake_devices import FakeCard


def test_unmapped_reads_ff_and_ignores_writes():
    pages = PageTable()
    assert pages.read(0x123456 & 0x1FFFFF, 0) == 0xFF
    pages.write(0x100000, 0x12, 0)
    assert pages.read(0x100000, 0) == 0xFF
    assert isinstance(pages.handler(0), Unmapped)


def test_eight_thousand_one_hundred_ninety_two_pages():
    pages = PageTable()
    assert len(pages._current) == 8192
    assert pages.handler(0x1FFFFF) is pages.handler(0x1FFF00)


def test_ram_mirrors_through_its_claimed_banks():
    pages = PageTable()
    ram = Ram(8 * 1024)
    pages.set_base(0x1F00, 0x1F7F, ram)
    pages.write(0x1F0000 + 0x10, 0x5A, 0)  # bank $F8
    for bank in (0xF8, 0xF9, 0xFA, 0xFB):
        assert pages.read((bank << 13) + 0x10, 0) == 0x5A
    assert pages.read(0x1F8010, 0) == 0xFF  # bank $FC is unused


def test_a_claim_replaces_the_base_handler_by_page_and_release_restores_it():
    pages = PageTable()
    ram = Ram(8 * 1024)
    pages.set_base(0x1F00, 0x1F7F, ram)
    card = FakeCard([(0x1F20, 0x1F2F)])  # banks inside the RAM window, one 4 KiB range
    pages.claim(0x1F20, 0x1F2F, card)
    assert pages.read(0x1F2000, 5) == 0xAA
    assert pages.read(0x1F1FFF, 5) == 0x00  # the page below is still RAM
    assert card.reads == [(0x1F2000, 5)]
    pages.release(0x1F20, 0x1F2F, card)
    assert pages.read(0x1F2000, 5) == 0x00


def test_claim_range_is_checked():
    with pytest.raises(ValueError):
        PageTable().claim(0x1FFF, 0x2000, FakeCard([]))


def test_addresses_are_masked_to_21_bits():
    pages = PageTable()
    card = FakeCard([(0x0000, 0x0000)])
    pages.claim(0, 0, card)
    assert pages.read(0x200000, 1) == 0xAA  # bit 21 is not an address line
