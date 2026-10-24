"""The VDC's bus port and VRAM access against pcetech section 5 and the Hudson VDC manual."""

import random

from pcengine_python.vdc import Vdc
from pcengine_python.vdc import regs as r


def reg(vdc, register, value, mclk=0):
    vdc.write(0, register, mclk)
    vdc.write(2, value & 0xFF, mclk)
    vdc.write(3, value >> 8, mclk)


def select(vdc, register):
    vdc.write(0, register, 0)


def test_status_port_reads_zero_at_power_up_and_port_1_reads_zero():
    vdc = Vdc()
    assert vdc.read(0, 0) == 0
    assert vdc.read(1, 0) == 0
    vdc.write(1, 0x55, 0)  # unused: writes do nothing
    assert vdc.read(1, 0) == 0


def test_register_select_uses_the_low_five_bits_and_mirrors_every_four_bytes():
    vdc = Vdc()
    vdc.write(0, 0xE5, 0)
    assert vdc.regs.select == 0x05
    vdc.write(4, 0x07, 0)  # offset & 3 == 0
    assert vdc.regs.select == 0x07


def test_vram_write_commits_on_the_msb_and_increments_mawr():
    vdc = Vdc()
    reg(vdc, r.MAWR, 0x0100)
    select(vdc, r.VRW)
    vdc.write(2, 0x34, 0)
    assert vdc.vram[0x100] == 0  # the LSB goes to the latch only
    vdc.write(3, 0x12, 0)
    assert vdc.vram[0x100] == 0x1234
    assert vdc.regs.value[r.MAWR] == 0x0101


def test_writing_the_lsb_repeatedly_changes_only_the_latch_and_msb_reuses_it():
    vdc = Vdc()
    reg(vdc, r.MAWR, 0)
    select(vdc, r.VRW)
    vdc.write(2, 0x11, 0)
    vdc.write(2, 0x22, 0)
    assert vdc.regs.value[r.MAWR] == 0
    vdc.write(3, 0xA0, 0)
    vdc.write(3, 0xB0, 0)  # the previously latched LSB is used again
    assert vdc.vram[0] == 0xA022
    assert vdc.vram[1] == 0xB022


def test_increment_width_comes_from_cr_bits_12_11():
    for bits, step in enumerate((1, 32, 64, 128)):
        vdc = Vdc()
        reg(vdc, r.CR, bits << 11)
        reg(vdc, r.MAWR, 0)
        select(vdc, r.VRW)
        vdc.write(2, 1, 0)
        vdc.write(3, 0, 0)
        assert vdc.regs.value[r.MAWR] == step


def test_marr_msb_write_loads_the_read_buffer_and_vrr_reads_advance():
    vdc = Vdc()
    for i, word in enumerate((0x1111, 0x2222, 0x3333)):
        vdc.vram[0x40 + i] = word
    reg(vdc, r.MARR, 0x0040)
    select(vdc, r.VRW)
    # [hw: pcetech 5.1] after the MARR MSB the first word is in the buffer
    assert vdc.read(2, 0) == 0x11 and vdc.read(3, 0) == 0x11
    # the MSB read advances MARR and loads the next word
    assert vdc.read(2, 0) == 0x22 and vdc.read(3, 0) == 0x22
    assert vdc.read(3, 0) == 0x33
    assert vdc.regs.value[r.MARR] == 0x0043


def test_lsb_read_does_not_advance_only_the_msb_read_does():
    vdc = Vdc()
    vdc.vram[0] = 0xAABB
    vdc.vram[1] = 0xCCDD
    reg(vdc, r.MARR, 0)
    select(vdc, r.VRW)
    assert vdc.read(2, 0) == 0xBB
    assert vdc.read(2, 0) == 0xBB
    assert vdc.read(3, 0) == 0xAA
    assert vdc.read(2, 0) == 0xDD


def test_data_port_with_another_register_selected_returns_the_buffer_without_marr_update():
    vdc = Vdc()
    vdc.regs.read_buffer = 0xBEEF
    select(vdc, r.BXR)
    assert vdc.read(2, 0) == 0xEF and vdc.read(3, 0) == 0xBE
    assert vdc.regs.value[r.MARR] == 0


def test_read_buffer_powers_up_ffff():
    assert Vdc().regs.read_buffer == 0xFFFF


def test_invalid_registers_do_nothing():
    vdc = Vdc()
    for register in (0x03, 0x04, 0x14, 0x1F):
        reg(vdc, register, 0x1234)
        assert vdc.regs.value[register] == 0


def test_registers_update_in_part_by_lsb_or_msb():
    vdc = Vdc()
    reg(vdc, r.BXR, 0x0123)
    select(vdc, r.BXR)
    vdc.write(2, 0xFF, 0)
    assert vdc.regs.value[r.BXR] == 0x01FF
    vdc.write(3, 0x02, 0)
    assert vdc.regs.value[r.BXR] == 0x02FF


def test_mirrored_vram_half_ignores_writes_and_reads_zero_u23():
    vdc = Vdc()
    reg(vdc, r.MAWR, 0x8000)
    select(vdc, r.VRW)
    vdc.write(2, 0x11, 0)
    vdc.write(3, 0x22, 0)
    assert all(word == 0 for word in vdc.vram)
    reg(vdc, r.MARR, 0x8000)
    select(vdc, r.VRW)
    assert vdc.read(2, 0) == 0


def test_register_fields_split_as_the_manual_says():
    vdc = Vdc()
    reg(vdc, r.HSR, 0x0A12)
    reg(vdc, r.HDR, 0x053F)
    reg(vdc, r.VPR, 0x1702)
    reg(vdc, r.VDW, 0xFFFF)
    reg(vdc, r.VCR, 0xFF0C)
    regs = vdc.regs
    assert (regs.hds, regs.hdw, regs.hde) == (0x0A, 0x3F, 0x05)
    assert (regs.vds, regs.vsw) == (0x17, 0x02)
    assert regs.vdw == 0x1FF  # nine bits
    assert regs.vcr == 0x0C


def test_status_read_clears_flags_and_releases_irq1():
    vdc = Vdc()
    vdc.status = r.VD | r.RR
    assert vdc.irq1
    assert vdc.read(0, 0) == r.VD | r.RR
    assert not vdc.irq1
    assert vdc.read(0, 0) == 0


def test_status_flags_only_set_when_enabled():
    vdc = Vdc()
    vdc.vblank_test()
    vdc.raster_test(0)
    assert vdc.status == 0
    reg(vdc, r.CR, r.CR_VBLANK_IRQ | r.CR_RASTER_IRQ)
    reg(vdc, r.RCR, 0x40)
    vdc.vblank_test()
    vdc.raster_test(0)
    assert vdc.status == r.VD | r.RR
    vdc.status = 0
    vdc.raster_test(1)
    assert vdc.status == 0  # RCR $40 is line 0 of the display period only


def test_rcr_out_of_range_never_matches():
    vdc = Vdc()
    reg(vdc, r.CR, r.CR_RASTER_IRQ)
    reg(vdc, r.RCR, 0x3F)
    for count in range(263):  # a frame's worth of line counts
        vdc.raster_test(count)
    assert vdc.status == 0


def test_power_up_vram_zero_by_default_random_on_request():
    assert not any(Vdc().vram) and not any(Vdc().sat)
    a, b = Vdc(power_on=random.Random(3)), Vdc(power_on=random.Random(3))
    assert a.vram == b.vram
    assert any(a.vram)


def test_busy_is_not_cleared_by_a_status_read_and_never_raises_irq1():
    """[mfr: HuC6270 manual 2.1.3] the status register clears on read except BSY, and 'even if
    BSY is set, no interrupt request will occur'."""
    from pcengine_python.vdc import regs as regs_

    vdc = Vdc()
    vdc._pending_write = (0, 1)
    vdc._commit_at = 10**9
    assert vdc.read(0, 0) == regs_.BSY
    assert vdc.read(0, 0) == regs_.BSY
    assert not vdc.irq1
