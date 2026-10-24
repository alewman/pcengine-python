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
    board.advance(LINE_CLOCKS * 10)
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
    board.advance(LINE_CLOCKS * 3)
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


def test_instances_not_modules_two_boards_two_vdcs_do_not_share_state():
    a, b = Board(), Board()
    a.vdc.vram[5] = 0x1234
    a.vce.palette[5] = 7
    a.ram.data[3] = 9
    a.psg.write(1, 0xFF, 0)
    assert b.vdc.vram[5] == 0 and b.vce.palette[5] == 0 and b.ram.data[3] == 0
    assert b.psg.global_regs[1] == 0
    v1, v2 = Vdc(), Vdc()
    v1.regs.value[5] = 1
    assert v2.regs.value[5] == 0
    assert Vce().palette is not Vce().palette
