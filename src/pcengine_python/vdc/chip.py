"""The HuC6270 VDC as the CPU sees it: the bus port, VRAM access, status, IRQ1.

Milestone 1 scope (docs/handoff-brief.md): timing, status/IRQ and the VRAM port with no
tiles. Background and DMA are M2, sprites M3. The registers they will use are stored already.

Instances, not module state: a SuperGrafx has two, a PC-FX may one day pin this package.

Bus ($FF:0000-03FF, 4-byte mirror) [hw: pcetech 5]:
    $0  write: register select (low 5 bits); read: status
    $1  unused, reads 0
    $2  data LSB     $3  data MSB

Provisional (U1, tier 5): the VDC's CPU access schedule in active display. Hudson's table and
MacDonald's give the mode-0 slot order (CPU, BAT, CPU, ?, CPU, CG0, CPU, CG1) but not the
phase against the line. A VRAM data access made during the display width is *accepted* at once
and *committed* at the next CPU slot of an 8-dot cycle counted from the display start; BSY
(status bit 6) is set until then; a second data access while one is pending holds the CPU
(RDY) until the first commits. Mednafen instead charges a statistical 1-cycle penalty (C4).
"""

from __future__ import annotations

import random
from array import array
from collections.abc import Callable

from pcengine_python.machine import HSYNC_CLOCKS
from pcengine_python.vdc import regs as r
from pcengine_python.vdc.sequencer import Sequencer, VPhase

VRAM_WORDS = 0x8000  # [hw: pcetech 5] 64 KiB; the upper half of the 128 KiB space mirrors it

# [hw: pcetech 5.1 register $09] CPU slots within the 8-dot cycle, by VRAM access mode
# (MWR D1-D0): mode 0 "CPU BAT CPU ??? CPU CG0 CPU CG1", modes 1 and 2 "BAT CPU CG0 CG1" over
# two dots each, mode 3 none for the CPU (four-dot accesses, BAT then CG).
CPU_SLOTS = ((0, 2, 4, 6), (2,), (2,), ())


class Vdc:
    def __init__(
        self,
        *,
        hold: Callable[[int], None] = lambda clocks: None,
        power_on: random.Random | None = None,
    ) -> None:
        self.regs = r.VdcRegisters()
        self._hold = hold
        # U7: zeros by default, random on request.
        if power_on is None:
            self.vram = array("H", bytes(VRAM_WORDS * 2))
            self.sat = array("H", bytes(256 * 2))
        else:
            self.vram = array("H", (power_on.getrandbits(16) for _ in range(VRAM_WORDS)))
            self.sat = array("H", (power_on.getrandbits(16) for _ in range(256)))
        self.status = 0
        self.seq = Sequencer(self)
        # A pending CPU VRAM access: ("w", address, word) or ("r", address, 0)
        self._pending_write: tuple[int, int] | None = None
        self._pending_read: int | None = None
        self._commit_at = 0

    # -- outputs ------------------------------------------------------------------------------

    @property
    def irq1(self) -> bool:
        """The /IRQ pin: held until the status port is read."""
        return bool(self.status & r.IRQ_BITS)

    @property
    def bsy(self) -> bool:
        return self._pending_write is not None or self._pending_read is not None

    def next_event(self) -> int | None:
        times = [t for t in (self.seq.next_event(), self._commit_event()) if t is not None]
        return min(times) if times else None

    def _commit_event(self) -> int | None:
        return self._commit_at if self.bsy else None

    def catch_up(self, mclk: int) -> None:
        while True:
            seq_t = self.seq.next_event()
            commit_t = self._commit_at if self.bsy else None
            if commit_t is not None and commit_t <= mclk and (seq_t is None or commit_t <= seq_t):
                self.commit_pending()
            elif seq_t is not None and seq_t <= mclk:
                self.seq.run_to(seq_t)
            else:
                return

    # -- the sync generator's calls (the VCE's line clock) -----------------------------------

    def hsync(self, mclk: int, divider: int) -> None:
        self.seq.hsync(mclk, divider)

    def vsync(self) -> None:
        self.seq.vsync()

    # -- events from the sequencer ------------------------------------------------------------

    def vblank_test(self) -> None:
        if self.regs.cr & r.CR_VBLANK_IRQ:
            self.status |= r.VD

    def raster_test(self, count: int) -> None:
        # [hw: pcetech 5.1] RCR is compared with the line counted from $40 at the first active
        # line; values outside $40-$146 never match.
        if count == self.regs.rcr - 0x40 and self.regs.cr & r.CR_RASTER_IRQ:
            self.status |= r.RR

    def commit_pending(self) -> None:
        if self._pending_write is not None:
            address, word = self._pending_write
            if address < VRAM_WORDS:  # [hw] writes to the mirrored half are ignored
                self.vram[address] = word
            self._pending_write = None
        if self._pending_read is not None:
            address = self._pending_read
            # Mirrored reads "sometimes return corrupted data" [hw]; U23: this model reads 0.
            self.regs.read_buffer = self.vram[address] if address < VRAM_WORDS else 0
            self._pending_read = None

    # -- the CPU's port -----------------------------------------------------------------------

    def read(self, offset: int, mclk: int) -> int:
        self.catch_up(mclk)
        port = offset & 3
        if port == 0:
            value = self.status | (r.BSY if self.bsy else 0)
            self.status &= ~r.IRQ_BITS
            return value
        if port == 1:
            return 0
        msb = port == 3
        value = (self.regs.read_buffer >> 8) if msb else (self.regs.read_buffer & 0xFF)
        if msb and self.regs.select == r.VRW:
            # [hw: pcetech 5.1 $02] after the MSB read MARR advances and the next word is read
            self._data_access(mclk)
            self.regs.value[r.MARR] = (self.regs.value[r.MARR] + self.regs.increment) & 0xFFFF
            self._pending_read = self.regs.value[r.MARR]
            self._schedule_commit(mclk)
        return value

    def write(self, offset: int, value: int, mclk: int) -> None:
        self.catch_up(mclk)
        port = offset & 3
        if port == 0:
            self.regs.select = value & 0x1F
            return
        if port == 1:
            return
        register = self.regs.select
        if register not in r.VALID_REGISTERS:
            return
        msb = port == 3
        regs = self.regs
        if register == r.VRW:
            if not msb:
                regs.write_latch = value
            else:
                self._data_access(mclk)
                word = regs.write_latch | (value << 8)
                self._pending_write = (regs.value[r.MAWR], word)
                regs.value[r.MAWR] = (regs.value[r.MAWR] + regs.increment) & 0xFFFF
                self._schedule_commit(mclk)
            return
        regs.set_byte(register, value, msb)
        if register == r.MARR and msb:
            # [hw: pcetech 5.1 $01] writing the MSB loads the read buffer from VRAM[MARR]
            self._data_access(mclk)
            self._pending_read = regs.value[r.MARR]
            self._schedule_commit(mclk)
        elif register == r.SATB:
            pass  # M2: arms the VRAM -> SAT DMA ("armed" at the MSB write)
        elif register == r.LENR and msb:
            pass  # M2: starts the VRAM -> VRAM DMA

    # -- VRAM access timing -------------------------------------------------------------------

    def _data_access(self, mclk: int) -> None:
        """A second data-port access while one is pending holds the CPU until it commits."""
        if self.bsy:
            wait = self._commit_at - mclk
            if wait > 0:
                self._hold(wait)
            self.commit_pending()

    def _schedule_commit(self, mclk: int) -> None:
        self._commit_at = self.slot_time(mclk)
        if self._commit_at <= mclk:
            self.commit_pending()

    def slot_time(self, mclk: int) -> int:
        """Earliest time at or after `mclk` that the CPU owns a VRAM slot (U1, provisional)."""
        seq = self.seq
        if not (seq.active_display and seq.active_start <= mclk < seq.active_end):
            return mclk
        div = seq.divider
        dot = -(-(mclk - seq.active_start) // div)  # first dot boundary at or after mclk
        slots = CPU_SLOTS[self.regs.mwr & 3]
        if not slots:
            return seq.active_end
        while True:
            when = seq.active_start + dot * div
            if when >= seq.active_end:
                return seq.active_end
            if dot % 8 in slots:
                return when
            dot += 1

    # -- display ------------------------------------------------------------------------------

    @property
    def vphase(self) -> VPhase:
        return self.seq.vphase

    def pixel_row(self, dots: int) -> list[int]:
        """The 9-bit VDC output for the line that just ran: M1 has no tiles or sprites.

        [hw: pcetech 5.2, 6] Inside the display width of a display-period line, with the
        background or sprites enabled, the backdrop (background palette 0 colour 0 = $000)
        shows; with both off ("burst") and outside the width, the overscan colour (sprite
        palette 0 colour 0 = $100)."""
        seq = self.seq
        row = [0x100] * dots
        if seq.display_line and seq.cr_cache & 0xC0:
            row_start = seq.origin + HSYNC_CLOCKS  # dot 0 of a row: the end of the line's sync
            first = (seq.active_start - row_start) // seq.divider
            last = (seq.active_end - row_start) // seq.divider
            for x in range(max(first, 0), min(last, dots)):
                row[x] = 0x000
        return row
