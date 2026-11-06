"""The sockets (docs/sockets.md), exercised with the test-only fakes: every Protocol has a fake
and the base board works with each of them plugged in, and unchanged without."""

from fake_devices import (
    FakeAudioSource,
    FakeCard,
    FakeController,
    FakePixelPath,
    FakePort,
    ScriptedCpu,
)

from pcengine_python.board import Board
from pcengine_python.machine import LINE_CLOCKS
from pcengine_python.psg import Psg
from pcengine_python.sockets import (
    AudioSource,
    Card,
    CardSlot,
    Clocked,
    ControllerPort,
    DirectPath,
    IrqLine,
    PageHandler,
    PixelPath,
    PortDevice,
    VideoTiming,
)
from pcengine_python.vce import Vce
from pcengine_python.vdc import Vdc


def test_fakes_satisfy_the_protocols_structurally():
    assert isinstance(FakeCard([]), PageHandler)
    assert isinstance(FakePort([]), PageHandler | Clocked)
    assert isinstance(FakePort([]), Clocked)
    # runtime-checkable only for the method Protocols; the attribute ones are checked by use
    # and by the type annotations below (a type checker, not pytest, enforces them)
    card: Card = FakeCard([])
    port: PortDevice = FakePort([])
    source: AudioSource = FakeAudioSource()
    pad: ControllerPort = FakeController()
    path: PixelPath = FakePixelPath()
    assert [type(x).__name__ for x in (card, port, source, pad, path)] == [
        "FakeCard",
        "FakePort",
        "FakeAudioSource",
        "FakeController",
        "FakePixelPath",
    ]


def test_irq_line_is_a_wired_or_of_sources_never_a_max():
    line = IrqLine("IRQ2")
    assert not line.level
    line.set("card", True)
    line.set("cd-adpcm", True)
    assert line.level and line.sources == {"card", "cd-adpcm"}
    line.set("card", False)
    assert line.level  # the CD still holds it
    line.set("cd-adpcm", False)
    assert not line.level


def test_empty_slot_is_a_state_and_the_card_decides_grounds_cd():
    assert not CardSlot().grounds_cd
    assert CardSlot(FakeCard([])).grounds_cd
    assert not CardSlot(FakePort([])).grounds_cd  # type: ignore[arg-type]


def test_direct_path_is_vdc_one_straight_into_the_vce():
    timing = VideoTiming(
        frame=0, line=3, start_mclk=0, dot_divider=4, frame_lines=263, in_vsync=False
    )
    rows = [[1, 2, 3], [9, 9, 9]]
    assert DirectPath().mix(timing, rows) == [1, 2, 3]


def test_a_replacement_pixel_path_sees_every_line():
    path = FakePixelPath()
    board = Board(pixel_path=path)
    board.advance(LINE_CLOCKS * 10 + 237)  # ten rows have ended
    assert path.lines_seen == 10


def test_a_replacement_pixel_path_changes_the_picture():
    class Marker:
        def mix(self, timing, rows):
            return [0x1FF] * len(rows[0])

    board = Board(pixel_path=Marker())
    board.vce.write(2, 0xFF, 0)
    board.vce.write(3, 0x01, 0)
    board.vce.write(4, 0x23, 0)
    board.vce.write(5, 0x01, 0)
    board.advance(LINE_CLOCKS * 263 * 2)
    frame = board.capture.last_frame
    assert frame is not None
    assert all(value == 0x123 for row in frame.rows for value in row)


def test_video_timing_record_per_line_has_the_dot_divider():
    seen = []

    class Spy(FakePixelPath):
        def mix(self, timing, rows):
            seen.append(timing)
            return super().mix(timing, rows)

    board = Board(pixel_path=Spy())
    board.vce.write(0, 0x01, 0)  # 7 MHz
    board.advance(LINE_CLOCKS * 3 + 237)
    assert [t.line for t in seen] == [0, 1, 2]
    assert {t.dot_divider for t in seen[1:]} == {3}
    assert seen[2].start_mclk == 2 * LINE_CLOCKS


def test_audio_source_list_has_the_psg_first():
    board = Board()
    assert board.audio_sources[0] is board.psg
    assert isinstance(board.psg, Psg)
    board.audio_sources.append(FakeAudioSource())
    assert board.audio_sources[1].take_samples(0) == [(1, -1)]


def test_a_port_device_is_caught_up_by_the_board_when_it_asks():
    port = FakePort([(0x1FF8, 0x1FF8)])
    board = Board(port=port)
    cpu = ScriptedCpu(board)
    cpu.read(0x1FF800)
    # the access carries the master-clock time; the device may run itself up to it
    assert port.reads[0][1] == board.mclk


def test_a_port_device_runs_with_the_board_clock_and_can_raise_irq2_by_itself():
    """Issue 0002: the board used to call `catch_up` on the VDCs and the timer only, so a port
    device (a CD drive's REQ, an ADPCM end) saw time at its own register accesses and could not
    raise IRQ2 between them."""

    class Alarm(FakePort):
        due = 5000

        def catch_up(self, mclk: int) -> None:
            super().catch_up(mclk)
            if mclk >= self.due:
                self.set_irq2(True)

    port = Alarm([(0x1FF8, 0x1FF8)])
    board = Board(port=port)
    assert not board.irq2.level
    board.advance(4000)
    assert port.caught_up[-1] == 4000 and not board.irq2.level
    board.advance(1000)  # no access to the device at all: the clock alone reaches it
    assert port.caught_up[-1] == 5000
    assert board.irq2.level
    assert board.lines()[1] is True


def test_instances_not_modules_two_boards_two_vdcs_do_not_share_state():
    a, b = Board(), Board()
    a.vdc.vram[5] = 0x1234
    a.vce.palette[5] = 7
    a.ram.data[3] = 9
    a.psg.write(1, 0xFF, 0)
    assert b.vdc.vram[5] == 0 and b.vce.palette[5] == 0 and b.ram.data[3] == 0
    assert b.psg.balance == 0
    v1, v2 = Vdc(), Vdc()
    v1.regs.value[5] = 1
    assert v2.regs.value[5] == 0
    assert Vce().palette is not Vce().palette


def test_psg_writes_through_the_bus_reach_the_audio_source_list_with_their_time():
    board = Board()
    cpu = ScriptedCpu(board, high_speed=True)
    base = 0x1FE800
    cpu.write(base + 1, 0xFF)  # R1: main level
    cpu.write(base + 0, 0x00)  # R0: channel 1
    cpu.write(base + 4, 0x00)  # ON = 0, DDA = 0: write data mode
    for value in [31] * 16 + [0] * 16:
        cpu.write(base + 6, value)
    cpu.write(base + 2, 0x20)
    cpu.write(base + 3, 0x00)
    cpu.write(base + 5, 0xFF)
    cpu.write(base + 4, 0x9F)  # ON, full level
    source = board.audio_sources[0]
    assert source is board.psg
    board.advance(3 * 21_477_272 // 100)  # about 30 ms
    samples = source.take_samples(board.mclk)
    assert 1200 <= len(samples) <= 1400  # 44.1 kHz
    left = [s[0] for s in samples]
    assert max(left) > 0 > min(left)  # a square wave about the centre
    assert board.cpu_io.buffer.value == 0x9F  # the I/O buffer saw the last write


# --- 12. Instances: a machine row with two VDCs (the SuperGrafx add-on, docs/issues/0001) ---------


def test_one_vdc_is_the_default_and_the_board_holds_a_list():
    board = Board()
    assert len(board.vdcs) == 1 and board.vdc is board.vdcs[0]


def test_a_second_vdc_is_run_synced_read_for_pixels_and_ored_into_irq1():
    from dataclasses import replace

    from pcengine_python.machine import PC_ENGINE

    seen = []

    class Spy:
        def mix(self, timing, rows):
            seen.append((timing.line, len(rows), len(rows[0]), len(rows[1])))
            return rows[0]

    board = Board(replace(PC_ENGINE, vdc_count=2), pixel_path=Spy())
    first, second = board.vdcs
    assert first is not second and board.vdc is first
    cpu = ScriptedCpu(board)
    # the board itself decodes only VDC 1; run a few lines and check VDC 2 was synced with it
    for _ in range(3 * LINE_CLOCKS // 12):
        cpu.idle()
    assert seen and all(n == 2 for _, n, _, _ in seen)
    # IRQ1 is the wired-OR of both: raise VDC 2's status bit and the line follows
    assert board.lines()[0] is False
    second.status |= 0x20  # VD
    assert board.lines()[0] is True
    second.status = 0
    first.status |= 0x04  # RR
    assert board.lines()[0] is True
