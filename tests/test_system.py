from fake_devices import FakePort

from pcengine_python.board import Board
from pcengine_python.machine import HARDWARE_BASE, LINE_CLOCKS
from pcengine_python.system import System


class LoopCpu:
    """Spins on `LDA $1FE000` (a VDC status read): 4 cycles, the last one a VDC access."""

    def __init__(self, board):
        self.board = board
        self.high_speed = True
        self.irq_disable = 0
        self.lines = (False, False, False)
        self.steps = 0

    def step(self):
        for _ in range(3):
            self.board.idle(None)
        self.board.read_byte(HARDWARE_BASE)
        self.steps += 1
        return 4

    def set_irq_lines(self, irq1, irq2, tiq):
        self.lines = (irq1, irq2, tiq)


def test_run_frame_stops_at_the_next_frame_and_prices_cycles_not_step_returns():
    system = System(Board(), LoopCpu)
    system.run_frame()
    assert system.frame == 1
    # 262-line first frame (VCE bit 2 clear); each step is 3 idle + (read + stretch) = 5 cycles x 3
    assert LINE_CLOCKS * 262 <= system.board.mclk < LINE_CLOCKS * 262 + 15
    assert system.cpu.steps == -(-LINE_CLOCKS * 262 // 15)


def test_run_until_and_the_cpu_sees_the_lines():
    port = FakePort([])
    system = System(Board(port=port), LoopCpu)
    system.run_until(1000)
    assert system.board.mclk >= 1000
    port.set_irq2(True)
    system.step()
    assert system.cpu.lines == (False, True, False)
