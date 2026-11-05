"""The board: one timeline in master clocks, the page table, and the devices around the CPU.

The CPU core (huc6280-python) calls `read_byte`, `write_byte` and `idle` once per CPU cycle with a
21-bit physical address. **The board prices the cycle**: 12 master clocks at low speed, 3 at high
speed (`cpu.high_speed`), plus the VDC/VCE stretch and any `hold`, all inside the callback; it
never adds `step()`'s return on top (docs/handoff-brief.md, the bus contract).

Where inside a cycle a device sees the access is U21 (provisional): the base cycle elapses, then
the access happens at that instant, then the stretch cycle for a VDC or VCE address elapses.
Covell's CPU test (tier 1) will place it.
"""

from __future__ import annotations

import random

from pcengine_python.cards import RomCard
from pcengine_python.cpu_io import CpuIo
from pcengine_python.hardware_page import map_hardware_page
from pcengine_python.machine import (
    CPU_CLOCKS_HIGH,
    CPU_CLOCKS_LOW,
    HARDWARE_FIRST_PAGE,
    HSYNC_CLOCKS,
    LINE_CLOCKS,
    PC_ENGINE,
    Machine,
)
from pcengine_python.pagetable import PageTable, Ram
from pcengine_python.psg import Psg
from pcengine_python.sockets import (
    BoardPins,
    Card,
    CardSlot,
    ControllerPort,
    IrqLine,
    PixelPath,
    PortDevice,
    ResetKind,
)
from pcengine_python.vce import Vce
from pcengine_python.vdc import Vdc
from pcengine_python.video import Capture, Timeline


class Board:
    def __init__(
        self,
        machine: Machine = PC_ENGINE,
        *,
        card: Card | RomCard | None = None,
        port: PortDevice | None = None,
        pad: ControllerPort | None = None,
        pixel_path: PixelPath | None = None,
        power_on_seed: int | None = None,
        start_line: int = 0,
        start_offset: int = 0,
        vblank_dots: int | None = -8,
        vertical_at_line_start: bool = False,
        dma_resumes: bool = True,
    ) -> None:
        """`power_on_seed=None` powers up with zeros (U7, deterministic); a seed randomises RAM,
        VRAM, the sprite table and the colour table reproducibly. `start_line` is the raster line
        at time zero (U1: the real power-up phase is not published)."""
        self.machine = machine
        rng = random.Random(power_on_seed) if power_on_seed is not None else None

        self.mclk = 0
        self.cpu = None  # set by attach_cpu
        self._held = 0
        self._lines = (False, False, False)
        self._row_end: int | None = None  # set by the first new line
        self._row_timing = None  # VideoTiming of the line whose row is still being drawn

        self.irq2 = IrqLine("IRQ2")
        self.vce = Vce(power_on=rng)
        # One VDC instance per `machine.vdc_count` (docs/sockets.md socket 12). `self.vdc` is the
        # first; the others are run, synced and read for pixels and IRQ1 by the board, but have
        # no decode of their own: an add-on (the SuperGrafx's VPC) claims their pages.
        self.vdcs = [
            Vdc(
                hold=self.hold,
                power_on=rng,
                vblank_dots=vblank_dots,
                vertical_at_line_start=vertical_at_line_start,
                dma_resumes=dma_resumes,
            )
            for _ in range(machine.vdc_count)
        ]
        self.vdc = self.vdcs[0]
        self._extra_vdcs = self.vdcs[1:]
        self.psg = Psg()
        self.cpu_io = CpuIo(
            self.psg,
            country_pc_engine=machine.country_pc_engine,
            cd_attached=lambda: self.port is not None and self.port.present,
            pad=pad,
            on_irq_disable=self._irq_disable_changed,
        )
        self.ram = Ram(machine.work_ram_bytes)
        if rng is not None:
            self.ram.data[:] = bytes(rng.getrandbits(8) for _ in range(machine.work_ram_bytes))
        self.slot = CardSlot(card)  # type: ignore[arg-type]
        self.port = port
        self.audio_sources = [self.psg]

        self.timeline = Timeline(machine, self.vce, start_line, start_offset)
        self.capture = Capture(self.vce, pixel_path)

        self.pages = PageTable()
        # [hw: pcetech 3] banks $F8-$FB work RAM ($F9-$FB mirror $F8), $FF the hardware page.
        self.pages.set_base(0x1F00, 0x1F7F, self.ram)
        map_hardware_page(self.pages, self.vdc, self.vce, self.cpu_io)
        pins = BoardPins(irq2=self.irq2, hold=self.hold)
        for device in (card, port):
            if device is not None:
                if hasattr(device, "bind"):
                    device.bind(pins)
                for first, last in device.claims():
                    self.pages.claim(first, last, device)

        for vdc in self.vdcs:
            vdc.hsync(self.timeline.line_start, self.vce.dot_divider)
            if self.timeline.line >= self.timeline.frame_lines - 3:
                vdc.vsync()

    # -- the CPU ------------------------------------------------------------------------------

    def attach_cpu(self, cpu: object) -> None:
        self.cpu = cpu
        cpu.irq_disable = self.cpu_io.irq.disable  # type: ignore[attr-defined]
        self._deliver_lines(force=True)

    @property
    def high_speed(self) -> bool:
        return bool(self.cpu is not None and self.cpu.high_speed)  # type: ignore[attr-defined]

    def _cycle_clocks(self) -> int:
        return CPU_CLOCKS_HIGH if self.high_speed else CPU_CLOCKS_LOW

    def read_byte(self, address: int) -> int:
        cycle = self._cycle_clocks()
        self.advance(cycle)
        value = self.pages.read(address, self.mclk)
        self._finish_access(address, cycle)
        return value

    def write_byte(self, address: int, value: int) -> None:
        cycle = self._cycle_clocks()
        self.advance(cycle)
        self.pages.write(address, value, self.mclk)
        self._finish_access(address, cycle)

    def idle(self, address: int | None = None) -> None:
        """A cycle with no bus transfer (internal cycle or dummy read: nothing reacts)."""
        self.advance(self._cycle_clocks())

    def _finish_access(self, address: int, cycle: int) -> None:
        # [hw: pcetech 3 note 3] a VDC or VCE access takes one more cycle, reads and writes.
        # C4: ares charges it only outside burst mode and only for the VDC; Mednafen charges
        # a statistical VRAM penalty. MacDonald's rule, tier 2, is this model's.
        page = address >> 8
        if HARDWARE_FIRST_PAGE <= page < HARDWARE_FIRST_PAGE + 8:
            self._held += cycle
        if self._held:
            held, self._held = self._held, 0
            self.advance(held)
        self._deliver_lines()  # the access itself (a status read) may have changed a line

    def hold(self, clocks: int) -> None:
        """A device stretches the current cycle (RDY low); applied when the access returns."""
        self._held += clocks

    # -- time ---------------------------------------------------------------------------------

    def advance(self, clocks: int) -> None:
        """Let `clocks` master clocks pass and run every device up to the new time."""
        self.mclk += clocks
        self._run_to(self.mclk)
        self._deliver_lines()

    def _run_to(self, target: int) -> None:
        tl, vdc, io = self.timeline, self.vdc, self.cpu_io
        while True:
            line_at = tl.next_line_start
            row_at = self._row_end
            vdc_at = vdc.next_event()
            for other in self._extra_vdcs:
                at = other.next_event()
                if at is not None and (vdc_at is None or at < vdc_at):
                    vdc_at = at
            timer_at = io.next_event()
            if row_at is not None and row_at <= target and row_at <= line_at:
                self._end_row(row_at)
            elif line_at <= target and (vdc_at is None or line_at <= vdc_at):
                self._new_line(line_at)
            elif vdc_at is not None and vdc_at <= target:
                for chip in self.vdcs:
                    chip.catch_up(vdc_at)
            elif timer_at is not None and timer_at <= target:
                io.catch_up(timer_at)
            else:
                break
        for chip in self.vdcs:
            chip.catch_up(target)
        io.catch_up(target)

    def _new_line(self, at: int) -> None:
        tl = self.timeline
        for vdc in self.vdcs:
            vdc.catch_up(at)
        self._row_timing = tl.timing()  # the line that is ending; its row ends 237 clocks later
        self._row_end = at + HSYNC_CLOCKS
        tl.advance()
        for vdc in self.vdcs:
            vdc.hsync(at, self.vce.dot_divider)
            if tl.line == tl.frame_lines - 3:
                vdc.vsync()  # [emu: Mednafen] after the hsync of the same line

    def _end_row(self, at: int) -> None:
        """The previous line's picture row ends as this line's sync does: hand it to the capture
        before the VDC starts the new line's geometry (events at `at` itself wait)."""
        for vdc in self.vdcs:
            vdc.catch_up(at - 1)
        timing = self._row_timing
        dots = LINE_CLOCKS // timing.dot_divider
        self.capture.finish_line(timing, [vdc.pixel_row(dots) for vdc in self.vdcs])
        self._row_end = None

    # -- interrupts ---------------------------------------------------------------------------

    def _irq_disable_changed(self, mask: int) -> None:
        if self.cpu is not None:
            self.cpu.irq_disable = mask  # type: ignore[attr-defined]

    def lines(self) -> tuple[bool, bool, bool]:
        """(IRQ1, IRQ2, TIQ) as the interrupt controller sees them, before the mask."""
        # IRQ1 is shared by every VDC (wired-OR; each is acknowledged by reading its status).
        return (any(v.irq1 for v in self.vdcs), self.irq2.level, self.cpu_io.tiq)

    def _deliver_lines(self, force: bool = False) -> None:
        lines = self.lines()
        self.cpu_io.irq.irq1, self.cpu_io.irq.irq2 = lines[0], lines[1]
        if (lines != self._lines or force) and self.cpu is not None:
            self.cpu.set_irq_lines(*lines)  # type: ignore[attr-defined]
        self._lines = lines

    # -- reset --------------------------------------------------------------------------------

    def reset(self, kind: ResetKind) -> None:
        for device in (self.slot.card, self.port):
            if device is not None:
                device.reset(kind)
        if kind is ResetKind.POWER_ON:
            self.cpu_io.reset()
