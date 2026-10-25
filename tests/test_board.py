"""The board's bus: pricing, the decode, interrupts and the sockets, driven by a scripted
stand-in for the CPU core (the core's contract is in huc6280-python's docs/handoff-brief.md)."""

from fake_devices import FakeCard, FakeController, FakePort, ScriptedCpu
from helpers import vdc_reg

from pcengine_python.board import Board
from pcengine_python.cards import RomCard
from pcengine_python.machine import (
    HARDWARE_BASE,
    LINE_CLOCKS,
    PC_ENGINE,
    TURBOGRAFX_16,
    Machine,
)
from pcengine_python.sockets import ResetKind

FIXED_263 = Machine("test machine, 263 lines", country_pc_engine=True, lines_follow_vce_bit2=False)


def make(**kw):
    board = Board(kw.pop("machine", PC_ENGINE), **kw)
    return board, ScriptedCpu(board, high_speed=kw.pop("high_speed", True))


# --- pricing ------------------------------------------------------------------------------


def test_a_cycle_is_12_master_clocks_at_low_speed_and_3_at_high_speed():
    board, cpu = make()
    cpu.high_speed = False
    cpu.read(0x1F0000)
    assert board.mclk == 12
    cpu.high_speed = True
    cpu.read(0x1F0000)
    assert board.mclk == 15
    cpu.write(0x1F0000, 1)
    cpu.idle()
    assert board.mclk == 21


def test_power_up_speed_is_low():
    board = Board()
    board.idle(None)
    assert board.mclk == 12  # no CPU attached: the console powers up in low speed


def test_vdc_and_vce_accesses_take_one_more_cycle_reads_and_writes():
    board, cpu = make()
    start = board.mclk
    cpu.read(HARDWARE_BASE)  # VDC status
    assert board.mclk - start == 6
    cpu.write(HARDWARE_BASE + 0x0400, 0)  # VCE control
    assert board.mclk - start == 12
    cpu.write(HARDWARE_BASE + 0x0003, 0)  # the highest VDC page edge: $0003
    cpu.read(HARDWARE_BASE + 0x07FF)  # the last VCE byte
    assert board.mclk - start == 24
    cpu.read(HARDWARE_BASE + 0x0800)  # PSG: no extra cycle
    cpu.read(HARDWARE_BASE + 0x1800)  # CD range: "the CD-ROM registers are not affected"
    assert board.mclk - start == 30


def test_the_extra_cycle_is_one_cycle_at_the_current_speed():
    board, cpu = make()
    cpu.high_speed = False
    cpu.read(HARDWARE_BASE)
    assert board.mclk == 24


def test_a_device_hold_lengthens_the_cycle_once_the_access_returns():
    board, cpu = make()
    card = FakeCard([(0x1F20, 0x1F20)])
    board.pages.claim(0x1F20, 0x1F20, card)
    board.hold(100)
    cpu.read(0x1F2000)
    assert board.mclk == 103


# --- the decode ---------------------------------------------------------------------------


def test_st0_st1_st2_go_to_the_vdc_at_physical_1fe000_2_3():
    board, cpu = make()
    cpu.write(0x1FE000, 0x05)  # ST0 #5: select CR
    cpu.write(0x1FE002, 0x34)  # ST1
    cpu.write(0x1FE003, 0x12)  # ST2
    assert board.vdc.regs.value[5] == 0x1234


def test_work_ram_mirrors_through_f8_fb_and_unused_banks_read_ff():
    _board, cpu = make()
    cpu.write(0x1F0000 + 0x123, 0x77)
    assert [cpu.read((bank << 13) + 0x123) for bank in (0xF8, 0xF9, 0xFA, 0xFB)] == [0x77] * 4
    assert cpu.read(0xFC << 13) == 0xFF
    assert cpu.read(0xFE << 13) == 0xFF
    assert cpu.read(0x80 << 13) == 0xFF
    assert cpu.read(0xF7 << 13) == 0xFF


def test_the_hardware_page_unmapped_blocks_read_ff():
    _board, cpu = make()
    for offset in (0x1800, 0x18FF, 0x1A00, 0x1FFF):
        assert cpu.read(HARDWARE_BASE + offset) == 0xFF


def test_hardware_page_dispatch_by_block():
    board, cpu = make()
    cpu.write(HARDWARE_BASE + 0x0C00, 0x05)  # timer latch
    assert board.cpu_io.timer.latch == 5
    cpu.write(HARDWARE_BASE + 0x0805, 0x99)  # PSG R5 (selected channel 0)
    assert board.psg.channels[0].balance == 0x99
    cpu.write(HARDWARE_BASE + 0x1402, 0x03)
    assert board.cpu_io.irq.disable == 3
    assert cpu.irq_disable == 3  # forwarded to the core for its gate
    cpu.write(HARDWARE_BASE + 0x0402, 0x10)  # VCE address
    assert board.vce.address == 0x10


def test_the_io_buffer_is_shared_by_the_whole_0800_17ff_range():
    _board, cpu = make()
    cpu.write(HARDWARE_BASE + 0x0C01, 0x00)
    cpu.write(HARDWARE_BASE + 0x0C00, 0x00)
    cpu.write(HARDWARE_BASE + 0x1402, 0x05)
    cpu.write(HARDWARE_BASE + 0x080F, 0xFF)
    assert cpu.read(HARDWARE_BASE + 0x1400) == 0xFF
    assert cpu.read(HARDWARE_BASE + 0x1402) == 0xFD
    cpu.write(HARDWARE_BASE + 0x1000, 0xFD)
    assert cpu.read(HARDWARE_BASE + 0x0C00) == 0x80


def test_vdc_reads_do_not_touch_the_io_buffer():
    board, cpu = make()
    cpu.write(HARDWARE_BASE + 0x080F, 0xA5)
    cpu.read(HARDWARE_BASE)
    cpu.read(HARDWARE_BASE + 0x0404)
    assert board.cpu_io.buffer.value == 0xA5


# --- cards and the port -------------------------------------------------------------------


def test_empty_slot_reads_ff_and_does_not_ground_cd():
    board, cpu = make()
    assert cpu.read(0x000000) == 0xFF
    assert cpu.read(0x0FFFFF) == 0xFF
    assert not board.slot.grounds_cd


def test_a_rom_card_answers_the_1_mib_window_with_mirroring():
    rom = bytes(i % 251 for i in range(256 * 1024))
    board, cpu = make(card=RomCard(rom))
    assert cpu.read(0x000010) == rom[0x10]
    assert cpu.read(0x040010) == rom[0x10]  # 256 KiB mirrored through the window
    assert cpu.read(0x0FE010) == rom[(0x0FE010) % len(rom)]
    cpu.write(0x000010, 0)  # ROM ignores writes
    assert cpu.read(0x000010) == rom[0x10]
    assert board.slot.grounds_cd


def test_card_and_port_get_the_pins_and_claim_their_pages():
    card = FakeCard([(0x0000, 0x00FF)], fill=0x11)
    port = FakePort([(0x1000, 0x107F)], fill=0x22)
    _board, cpu = make(card=card, port=port)
    assert card.pins is not None and port.pins is not None
    assert cpu.read(0x000100) == 0x11
    assert cpu.read(0x100000) == 0x22
    assert cpu.read(0x1FFF00 - 0x2000) == 0xFF  # an unclaimed address still reads $FF


def test_a_port_device_can_claim_hardware_page_blocks_1800_18ff():
    port = FakePort([(0x1FF8, 0x1FF8)], fill=0x5A)
    board, cpu = make(port=port)
    assert cpu.read(HARDWARE_BASE + 0x1800) == 0x5A
    assert port.reads == [(HARDWARE_BASE + 0x1800, board.mclk)]  # carries its master-clock time
    assert cpu.read(HARDWARE_BASE + 0x1900) == 0xFF
    cpu.write(HARDWARE_BASE + 0x1801, 0x42)
    assert port.writes[-1][:2] == (HARDWARE_BASE + 0x1801, 0x42)


def test_io_port_d7_follows_the_expansion_port_not_the_slot():
    card = RomCard(bytes(8192))
    _board, cpu = make(card=card)
    assert cpu.read(HARDWARE_BASE + 0x1000) & 0x80  # a card in the slot, no CD unit: 1
    port = FakePort([])
    _board2, cpu2 = make(port=port)
    assert not cpu2.read(HARDWARE_BASE + 0x1000) & 0x80  # attached: 0 (C6)
    port.present = False
    assert cpu2.read(HARDWARE_BASE + 0x1000) & 0x80


def test_country_bit_is_a_row_of_the_machine_table():
    _, cpu_j = make(machine=PC_ENGINE)
    _, cpu_u = make(machine=TURBOGRAFX_16)
    assert cpu_j.read(HARDWARE_BASE + 0x1000) & 0x40
    assert not cpu_u.read(HARDWARE_BASE + 0x1000) & 0x40


def test_pad_reaches_the_io_port():
    pad = FakeController(0x06)
    _board, cpu = make(pad=pad)
    cpu.write(HARDWARE_BASE + 0x1000, 0x01)
    assert cpu.read(HARDWARE_BASE + 0x1000) & 0x0F == 0x06
    assert pad.writes[-1] == (True, False)


def test_reset_reaches_card_and_port():
    card, port = FakeCard([]), FakePort([])
    board, _ = make(card=card, port=port)
    board.reset(ResetKind.POWER_ON)
    assert card.resets == [ResetKind.POWER_ON] and port.resets == [ResetKind.POWER_ON]


# --- interrupts ---------------------------------------------------------------------------


def test_timer_interrupt_reaches_the_core_as_tiq_and_1403_write_releases_it():
    board, cpu = make()
    cpu.write(HARDWARE_BASE + 0x0C00, 0x00)
    cpu.write(HARDWARE_BASE + 0x0C01, 0x01)
    enabled_at = board.mclk
    while not cpu.lines[2]:
        cpu.idle()
    assert enabled_at + 3072 <= board.mclk <= enabled_at + 3072 + 6
    assert cpu.lines == (False, False, True)
    cpu.write(HARDWARE_BASE + 0x1403, 0)
    assert cpu.lines == (False, False, False)


def test_irq2_is_a_per_source_level_set_by_a_port_device():
    port = FakePort([])
    board, cpu = make(port=port)
    port.set_irq2(True)
    board.advance(3)
    assert cpu.lines == (False, True, False)
    assert cpu.read(HARDWARE_BASE + 0x1403) & 1  # visible in the controller status
    port.set_irq2(False)
    board.advance(3)
    assert cpu.lines == (False, False, False)


def test_the_core_gets_raw_lines_even_when_masked():
    port = FakePort([])
    board, cpu = make(port=port)
    cpu.write(HARDWARE_BASE + 0x1402, 0x01)  # IRQ2 disabled
    port.set_irq2(True)
    board.advance(3)
    assert cpu.lines[1] is True  # the core applies irq_disable
    assert cpu.irq_disable == 1


# --- power-up -----------------------------------------------------------------------------


def test_power_up_is_zero_by_default_and_random_on_request_reproducibly():
    zero = Board()
    assert not any(zero.ram.data) and not any(zero.vdc.vram) and not any(zero.vce.palette)
    a, b = Board(power_on_seed=5), Board(power_on_seed=5)
    assert a.ram.data == b.ram.data and a.vdc.vram == b.vdc.vram and a.vce.palette == b.vce.palette
    assert any(a.ram.data) and any(a.vdc.vram) and any(a.vce.palette)
    assert a.ram.data != Board(power_on_seed=6).ram.data


# --- the VDC's CPU slot (U1, provisional) -------------------------------------------------


def test_vram_write_is_accepted_at_once_outside_the_display_and_commits_immediately():
    board, cpu = make()
    vdc_reg(cpu, 0x00, 0x0200)
    cpu.write(HARDWARE_BASE, 0x02)
    cpu.write(HARDWARE_BASE + 2, 0x34)
    cpu.write(HARDWARE_BASE + 3, 0x12)
    assert board.vdc.vram[0x200] == 0x1234
    assert not board.vdc.bsy


def _into_display(board, cpu):
    from helpers import standard_display

    standard_display(cpu, cr=0x00C0)
    board.advance(263 * LINE_CLOCKS)
    target = (263 + 100) * LINE_CLOCKS + 700  # frame 1, line 100, well inside the width
    board.advance(target - board.mclk)
    assert board.vdc.seq.active_display
    assert board.vdc.seq.active_start < board.mclk < board.vdc.seq.active_end


def test_mode_0_vram_access_commits_within_one_slot_period():
    board, cpu = make(machine=FIXED_263)
    _into_display(board, cpu)
    cpu.write(HARDWARE_BASE, 0x02)
    cpu.write(HARDWARE_BASE + 2, 0x11)
    cpu.write(HARDWARE_BASE + 3, 0x22)  # accepted
    assert board.vdc.bsy or board.vdc.vram[0] == 0x2211
    board.advance(8)  # mode 0 gives the CPU a slot every 2 dots = 8 master clocks at 5 MHz
    assert board.vdc.vram[0] == 0x2211 and not board.vdc.bsy


def test_a_mode_with_no_cpu_slot_holds_the_second_access_to_the_end_of_the_display():
    board, cpu = make(machine=FIXED_263)
    _into_display(board, cpu)
    vdc_reg(cpu, 0x09, 0x0003)  # MWR: four-dot accesses, no CPU slot
    cpu.write(HARDWARE_BASE, 0x02)
    cpu.write(HARDWARE_BASE + 2, 0x11)
    cpu.write(HARDWARE_BASE + 3, 0x22)
    assert board.vdc.bsy  # BSY: waiting for a slot
    assert board.vdc.read(0, board.mclk) & 0x40
    cpu.write(HARDWARE_BASE + 3, 0x33)  # a second data access: the CPU is held (RDY)
    assert board.mclk >= board.vdc.seq.active_end
    assert board.vdc.vram[0] == 0x2211


def test_start_line_sets_the_raster_phase_at_time_zero():
    board = Board(FIXED_263, start_line=260)
    assert board.timeline.line == 260 and board.timeline.in_vsync
    assert board.vdc.seq.vphase.name == "VSW"  # the vertical sync has begun
    board.advance(LINE_CLOCKS * 3)
    assert board.timeline.line == 0 and board.timeline.frame == 1
    import pytest

    with pytest.raises(ValueError):
        Board(FIXED_263, start_line=263)
