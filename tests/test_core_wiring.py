"""The real core on the board (huc6280-python, pinned): the two handoff checks of the brief and
the first instructions of a program."""

import pytest

from pcengine_python.board import Board
from pcengine_python.cards import RomCard
from pcengine_python.system import build

pytestmark = pytest.mark.needs_cpu


def program(code: bytes, origin=0xE000) -> RomCard:
    rom = bytearray([0xEA] * 8192)  # NOP fill
    rom[origin - 0xE000 : origin - 0xE000 + len(code)] = code
    rom[0x1FFE], rom[0x1FFF] = origin & 0xFF, origin >> 8
    return RomCard(bytes(rom))


def test_reset_reads_the_vector_and_prices_cycles_not_step_returns():
    system = build(Board(card=program(b"\x78")))  # SEI
    system.step()  # the start sequence
    assert system.cpu.pc == 0xE000
    assert system.board.mclk == 7 * 12  # five internal cycles + two vector reads, low speed
    system.step()
    assert system.board.mclk == 9 * 12


def test_csh_speeds_the_clock_up_and_the_cycle_is_3_master_clocks():
    system = build(Board(card=program(b"\xd4\xea\xea")))  # CSH NOP NOP
    system.step()
    system.step()
    assert system.cpu.high_speed
    before = system.board.mclk
    system.step()  # NOP: 2 cycles at 3 clocks
    assert system.board.mclk - before == 6


def run_instructions(system, count):
    for _ in range(count):
        system.step()


def test_block_transfer_reads_of_the_io_range_return_zero_and_leave_the_buffer_alone():
    """Handoff check: the core's zero-read rule (U7) never reaches the board as a read."""
    code = bytes(
        [
            0xA9,
            0xFF,
            0x53,
            0x04,  # LDA #$FF ; TAM #$04: MPR2 = bank $FF, logical $4000
            0xA9,
            0xF8,
            0x53,
            0x08,  # LDA #$F8 ; TAM #$08: MPR3 = work RAM, logical $6000
            0x73,
            0x00,
            0x50,
            0x00,
            0x60,
            0x01,
            0x00,  # TII $5000,$6000,1 (the I/O port)
            0xAD,
            0x00,
            0x50,  # LDA $5000: an ordinary read, for contrast
        ]
    )
    board = Board(card=program(code))
    system = build(board)
    board.cpu_io.buffer.value = 0x5A
    board.ram.data[0] = 0xEE
    run_instructions(system, 1 + 4 + 1)  # reset, 4 setup, the transfer
    assert board.ram.data[0] == 0x00  # the transfer got 0, not the port's $FF
    assert board.cpu_io.buffer.value == 0x5A  # and did not load the buffer
    run_instructions(system, 1)
    assert system.cpu.a == 0xFF  # an ordinary read of the port
    assert board.cpu_io.buffer.value == 0xFF  # which does load the buffer


def test_core_zero_read_range_stops_short_of_the_interrupt_registers():
    """Finding (not a board bug): pcetech 2 says block reads of $0800-$1400 return 0 and lists
    the IRQ registers among the things that cannot be read; huc6280's U7 range ends at $13FF, so
    a block read of $1402 reaches the register. Recorded in docs/m1-record.md for the core."""
    code = bytes(
        [0xA9, 0xFF, 0x53, 0x04, 0xA9, 0xF8, 0x53, 0x08, 0x73, 0x02, 0x54, 0x00, 0x60, 0x01, 0x00]
    )
    board = Board(card=program(code))
    system = build(board)
    board.cpu_io.buffer.value = 0xFA
    run_instructions(system, 6)
    assert board.ram.data[0] == 0xF8  # $1402 answered: disable bits 0 | buffer upper five


def test_block_transfer_writes_to_the_io_range_work_and_load_the_buffer():
    code = bytes(
        [
            0xA9,
            0xFF,
            0x53,
            0x04,
            0xA9,
            0xF8,
            0x53,
            0x08,
            0x73,
            0x00,
            0x60,
            0x06,
            0x54,
            0x01,
            0x00,  # TII $6000,$5406,1 -> $1406 mirror of $1402
        ]
    )
    board = Board(card=program(code))
    board.ram.data[0] = 0x05
    system = build(board)
    run_instructions(system, 6)
    assert board.cpu_io.buffer.value == 0x05
    assert board.cpu_io.irq.disable == 0x05
    assert system.cpu.irq_disable == 0x05  # the core's $1402-layout gate follows the register


def irq_program() -> RomCard:
    rom = bytearray([0xEA] * 8192)
    rom[0] = 0x58  # CLI at $E000
    rom[0x100:0x103] = bytes([0xA2, 0x77, 0x80])  # ISR at $E100: LDX #$77 ; BRA ...
    rom[0x103] = 0xFE
    rom[0x1FF6], rom[0x1FF7] = 0x00, 0xE1  # IRQ2 vector
    rom[0x1FFE], rom[0x1FFF] = 0x00, 0xE0
    return RomCard(bytes(rom))


def test_a_masked_irq2_is_not_taken_and_an_unmasked_one_enters_through_its_vector():
    system = build(Board(card=irq_program()))
    board, cpu = system.board, system.cpu
    system.step()  # reset
    system.step()  # CLI
    board.cpu_io.write(0x1402, 0x01, board.mclk)  # disable IRQ2: the core's gate follows
    assert cpu.irq_disable == 1
    board.irq2.set("test", True)
    for _ in range(10):
        system.step()
    assert cpu.irq_lines == (False, True, False)  # raw level reaches the core
    assert cpu.pc < 0xE100 and cpu.x == 0
    board.cpu_io.write(0x1402, 0x00, board.mclk)
    assert cpu.irq_disable == 0
    for _ in range(4):
        system.step()
    assert cpu.x == 0x77  # taken at $FFF6, still unacknowledged (level)
