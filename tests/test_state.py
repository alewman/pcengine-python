"""Save states (state.py): a saved and loaded run continues as the run that was not interrupted."""

from __future__ import annotations

import json
import sys
import zlib
from pathlib import Path

import pytest

from pcengine_python import pads
from pcengine_python.board import Board
from pcengine_python.cards import PopulousCard, RomCard, Sf2Card, TennokoeCard
from pcengine_python.machine import PC_ENGINE, TURBOGRAFX_16
from pcengine_python.state import FORMAT, StateError, load_state, save_state
from pcengine_python.system import build

pytestmark = pytest.mark.needs_cpu

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from state_roundtrip import roundtrip  # noqa: E402

COVELL = ROOT / "tests/test_roms/CPU_Test/CPU_Test_10.pce"


def system_with(card, machine=PC_ENGINE):
    return build(Board(machine, card=card, pad=pads.Pad2()))


def image(size=0x2000, fill=0xEA):
    """A card image that is only its reset vector (to $E000) and a fill."""
    data = bytearray([fill]) * size
    data[-2:] = b"\x00\xe0"
    return bytes(data)


def program() -> bytes:
    """A card that does something: counts in work RAM and writes the count to the VCE's colour
    table and a PSG register, for ever (so a state has RAM, a palette and sound to carry)."""
    code = bytes.fromhex(
        "78"  # SEI
        "a9ff5302"  # LDA #$FF; TAM #$02: the hardware page at $2000
        "a9f85304"  # LDA #$F8; TAM #$04: work RAM at $4000
        "ee0040"  # loop ($E009): INC $4000
        "ad0040"  # LDA $4000
        "8d0224"  # STA $2402 (VCE colour address, low)
        "8d0424"  # STA $2404 (VCE colour data, low)
        "8d0628"  # STA $2806 (PSG channel data)
        "4c09e0"  # JMP loop
    )
    data = bytearray([0xEA]) * 0x2000
    data[: len(code)] = code
    data[-2:] = b"\x00\xe0"
    return bytes(data)


def test_a_loaded_run_continues_bus_cycle_for_bus_cycle():
    def make():
        pad = pads.Pad2()
        board = Board(card=RomCard(program()), pad=pad)
        return board, lambda: build(board), pad

    passed, what = roundtrip(make, at=2, to=4, extra=777)
    assert passed, what


@pytest.mark.skipif(not COVELL.exists(), reason="Covell's CPU test is fetched, not tracked")
def test_a_loaded_run_of_covells_cpu_test_continues_the_same():
    def make():
        pad = pads.Pad2()
        board = Board(card=RomCard(COVELL.read_bytes()), pad=pad)
        return board, lambda: build(board), pad

    passed, what = roundtrip(make, at=2, to=4, extra=777)
    assert passed, what


def test_a_state_holds_no_rom_bytes_and_names_only_this_package():
    system = system_with(RomCard(program()))
    system.run_frame()
    body = json.loads(zlib.decompress(save_state(system)))
    assert body["format"] == FORMAT and body["packages"] == ["pcengine_python"]
    card = body["board"]["fields"]["slot"]["fields"]["card"]["fields"]["data"]
    assert set(card) == {"rom", "length"} and card["length"] == len(program())


def test_the_mappers_registers_and_ram_come_back():
    sf2 = system_with(Sf2Card(image(0x280000)))
    sf2.board.slot.card.page = 2
    other = system_with(Sf2Card(image(0x280000)))
    load_state(other, save_state(sf2))
    assert other.board.slot.card.page == 2

    populous = system_with(PopulousCard(image(0x80000)))
    populous.board.slot.card.ram[0x1234] = 0x5A
    other = system_with(PopulousCard(image(0x80000)))
    load_state(other, save_state(populous))
    assert other.board.slot.card.ram[0x1234] == 0x5A

    tennokoe = system_with(TennokoeCard(image()))
    tennokoe.board.slot.card.locked = False
    tennokoe.board.slot.card.ram[7] = 0x33
    other = system_with(TennokoeCard(image()))
    load_state(other, save_state(tennokoe))
    assert other.board.slot.card.locked is False and other.board.slot.card.ram[7] == 0x33


def test_loading_keeps_the_wiring_and_the_shared_objects():
    system = system_with(RomCard(program()))
    system.run_frame()
    other = system_with(RomCard(program()))
    board = other.board
    before = (board.vdc, board.vce, board.psg, board.cpu, board.machine, board.slot.card.data)
    load_state(other, save_state(system))
    after = (board.vdc, board.vce, board.psg, board.cpu, board.machine, board.slot.card.data)
    assert all(a is b for a, b in zip(before, after, strict=True))
    assert board.vdcs[0] is board.vdc and board.mixer.sources is board.audio_sources
    assert board.mclk == system.board.mclk and other.frame == system.frame


def test_a_state_of_something_else_is_refused():
    system = system_with(RomCard(program()))
    state = save_state(system)
    with pytest.raises(StateError, match="not a save state"):
        load_state(system, b"not zlib")
    with pytest.raises(StateError, match="not a pcengine-python state"):
        load_state(system, zlib.compress(b'{"format": "another"}'))
    body = json.loads(zlib.decompress(state))
    body["version"] = 0
    with pytest.raises(StateError, match="version 0"):
        load_state(system, zlib.compress(json.dumps(body).encode()))
    with pytest.raises(StateError, match="of the PC Engine, not the TurboGrafx-16"):
        load_state(system_with(RomCard(program()), TURBOGRAFX_16), state)
    with pytest.raises(StateError, match="another ROM image"):
        load_state(system_with(RomCard(image(len(program())))), state)
    body = json.loads(zlib.decompress(state))
    body["packages"].append("an_addon_python")
    with pytest.raises(StateError, match="needs an_addon_python"):
        load_state(system, zlib.compress(json.dumps(body).encode()))


def test_a_state_names_no_class_outside_the_registered_packages():
    system = system_with(RomCard(program()))
    body = json.loads(zlib.decompress(save_state(system)))
    body["board"]["fields"]["ram"] = {"object": "subprocess.Popen", "fields": {}}
    with pytest.raises(StateError, match="not a class a state may hold"):
        load_state(system, zlib.compress(json.dumps(body).encode()))
