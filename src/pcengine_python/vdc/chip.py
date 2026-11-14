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
from pcengine_python.vdc import sprites
from pcengine_python.vdc.background import Background
from pcengine_python.vdc.dma import DmaEngine
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
        serve: Callable[[Vdc], int] | None = None,
        power_on: random.Random | None = None,
        vblank_dots: int | None = -8,
        vertical_at_line_start: bool = False,
        dma_resumes: bool = True,
    ) -> None:
        self.regs = r.VdcRegisters()
        self._hold = hold
        # The board's wait (issue 0004): run the whole machine, line clock included, until this
        # chip's pending CPU access is served, and return that time. None (a VDC on its own, with
        # no sync to deliver) waits on the chip's own events.
        self._serve = serve
        # U7: zeros by default, random on request.
        if power_on is None:
            self.vram = array("H", bytes(VRAM_WORDS * 2))
            self.sat = array("H", bytes(256 * 2))
        else:
            self.vram = array("H", (power_on.getrandbits(16) for _ in range(VRAM_WORDS)))
            self.sat = array("H", (power_on.getrandbits(16) for _ in range(256)))
        self.status = 0
        self.now = 0  # master-clock time of the sequencer event being handled
        self.seq = Sequencer(self, vblank_dots, vertical_at_line_start)
        self.dma = DmaEngine(self, resume=dma_resumes)
        self._background = Background()
        # [emu: Mednafen BG_YMoo, BG_YOffset, BG_XOffset] the scroll as the line latched it
        self._bg_y = 0
        self._need_bg_y_step = False
        self._bg_y_offset = 0
        self._bg_x_offset = 0
        self._mwr_cache = 0  # MWR as the vertical sync latched it
        self._row: list[int] | None = None
        self._sprite_entries: list[sprites.Entry] = []
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
        times = [
            t
            for t in (self.seq.next_event(), self._commit_event(), self.dma.next_event())
            if t is not None
        ]
        return min(times) if times else None

    def _commit_event(self) -> int | None:
        return self._commit_at if self.bsy else None

    def catch_up(self, mclk: int) -> None:
        while True:
            seq_t = self.seq.next_event()
            dma_t = self.dma.next_event()
            commit_t = self._commit_at if self.bsy else None
            due = [t for t in (seq_t, dma_t, commit_t) if t is not None and t <= mclk]
            if not due:
                self.dma.advance(mclk)
                return
            t = min(due)
            if dma_t is not None and dma_t == t:
                self.dma.advance(t)
            elif commit_t is not None and commit_t == t and (seq_t is None or commit_t <= seq_t):
                self.commit_pending()
            else:
                self.dma.advance(t)
                self.seq.run_to(t)

    # -- the sync generator's calls (the VCE's line clock) -----------------------------------

    def hsync(self, mclk: int, divider: int) -> None:
        self.seq.hsync(mclk, divider)

    def vsync(self) -> None:
        self.seq.vsync()
        self._need_bg_y_step = False
        self._mwr_cache = self.regs.mwr

    # -- events from the sequencer ------------------------------------------------------------

    def vblank_test(self) -> None:
        if self.regs.cr & r.CR_VBLANK_IRQ:
            self.status |= r.VD

    def raster_test(self, count: int) -> None:
        # [hw: pcetech 5.1] RCR is compared with the line counted from $40 at the first active
        # line; values outside $40-$146 never match.
        if count == self.regs.rcr - 0x40 and self.regs.cr & r.CR_RASTER_IRQ:
            self.status |= r.RR

    def latch_byr(self) -> None:
        self._step_bg_y()
        self._bg_y_offset = self._bg_y

    def latch_bxr(self) -> None:
        self._bg_x_offset = self.regs.value[r.BXR] & 0x3FF

    def _step_bg_y(self) -> None:
        if self._need_bg_y_step:
            self._need_bg_y_step = False
            self._bg_y = (
                (self.regs.value[r.BYR] & 0x1FF) if self.seq.rcr_count == 0 else self._bg_y + 1
            )

    def line_counter_step(self, count: int) -> None:
        self._step_bg_y()
        self._need_bg_y_step = True

    def fetch_sprites(self, line: int) -> None:
        """The scan for the next line's sprites, with the overflow flag and the narrow-display
        budget (U3: Mesen2's: the VDC fetches 4, 4, 8 or 16 dots per entry between the end of
        one line's display width and 16 dots before the next line's)."""
        seq = self.seq
        dots = 1365 // seq.divider
        previous_end = (seq.active_end - seq.origin - HSYNC_CLOCKS) // seq.divider
        next_start = dots + 8 + (self.regs.hds + 1) * 8 - 16
        budget = (
            max(0, next_start - previous_end)
            // sprites.CLOCKS_PER_SPRITE[(self._mwr_cache >> 2) & 3]
        )
        entries, overflow = sprites.scan(
            self.vram, VRAM_WORDS, self.sat, line, self._mwr_cache, limit=budget
        )
        self._sprite_entries = entries
        if overflow and self.regs.cr & r.CR_OVERFLOW_IRQ:
            self.status |= r.OR

    def collision_hit(self) -> None:
        if self.regs.cr & r.CR_COLLISION_IRQ:
            self.status |= r.CR_FLAG

    def display_started(self) -> None:
        self.dma.display_started(self.now)

    def display_ended(self) -> None:
        self.dma.display_ended(self.now)

    def burst_began(self) -> None:
        self.dma.advance(self.now)

    def render_line(self) -> None:
        """The 9-bit pixels of this line, drawn as the display width begins (M2: background only;
        the sprites are M3). [hw: pcetech 5.2, 6] Backdrop (background colour 0, $000) inside the
        width if either layer is on, overscan (sprite colour 0, $100) otherwise and outside."""
        seq = self.seq
        dots = 1365 // seq.divider
        row = [0x100] * dots
        self._row = row
        if not seq.display_line:
            return
        row_start = seq.origin + HSYNC_CLOCKS
        first = (seq.active_start - row_start) // seq.divider
        width = (seq.active_end - seq.active_start) // seq.divider
        cr = seq.cr_cache
        if cr & 0x80:
            pixels = self._background.row(
                self.vram, VRAM_WORDS, self._mwr_cache, self._bg_x_offset, self._bg_y_offset, width
            )
        else:
            # sprites only, or neither layer inside a non-burst display period: the backdrop.
            # [emu: Mednafen, Mesen2 and Beetle all show colour 0 of the background palette when
            # both layers are off (Space Harrier's last 12 lines); pcetech 5.2 says overscan: C30]
            pixels = [0x000] * width
        # first <= dots: a display start past the row's end would come after the next line's
        # sync, whose `_leave_hsync` drops this line's events before it is drawn (issue 0004)
        end = min(first + width, dots)
        row[first:end] = pixels[: end - first]
        if cr & 0x40 and self._sprite_entries:
            hit = sprites.draw(self._sprite_entries, end - first, row, first)
            if hit is not None and self.regs.cr & r.CR_COLLISION_IRQ:
                # the flag rises when the beam reaches the pixel (Mesen2 runs the VDC per CPU cycle
                # for this; Mednafen raises it as the line is drawn): U3
                when = row_start + (first + hit) * seq.divider
                seq.schedule(max(when, self.now), "collision")

    def commit_unless_dma(self) -> None:
        """Commit a waiting CPU access unless a transfer holds the VRAM (Mednafen's
        `CheckAndCommitPending`: nothing is committed while the SAT or VRAM DMA runs)."""
        if not self.dma.busy:
            self.commit_pending()

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
        if self._pending_read is not None:
            # The word the last MARR write or VRR read asked for is not in the buffer yet (it
            # waits for a CPU slot or a DMA): the CPU waits for it rather than reading the old
            # word. The manual's read sequence and both Mednafen and Mesen2 ("D&D Order of the
            # Griffon breaks without this") agree; the model's slot wait made the case possible.
            mclk = self._data_access(mclk)
        value = (self.regs.read_buffer >> 8) if msb else (self.regs.read_buffer & 0xFF)
        if msb and self.regs.select == r.VRW:
            # [hw: pcetech 5.1 $02] after the MSB read MARR advances and the next word is read
            mclk = self._data_access(mclk)
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
                mclk = self._data_access(mclk)
                word = regs.write_latch | (value << 8)
                self._pending_write = (regs.value[r.MAWR], word)
                regs.value[r.MAWR] = (regs.value[r.MAWR] + regs.increment) & 0xFFFF
                self._schedule_commit(mclk)
            return
        regs.set_byte(register, value, msb)
        if register == r.MARR and msb:
            # [hw: pcetech 5.1 $01] writing the MSB loads the read buffer from VRAM[MARR]
            mclk = self._data_access(mclk)
            self._pending_read = regs.value[r.MARR]
            self._schedule_commit(mclk)
        elif register == r.BYR:
            # [emu: Mednafen] set on both bytes: only changing on the MSB breaks a game
            self._bg_y = regs.value[r.BYR] & 0x1FF
        elif register == r.SATB:
            self.dma.arm_satb()  # [mfr] armed by a write; starts when the display period ends
        elif register == r.LENR and msb:
            self.dma.start(mclk)

    # -- VRAM access timing -------------------------------------------------------------------

    def _data_access(self, mclk: int) -> int:
        """A second data-port access while one is pending holds the CPU until it commits; the
        time at which the new access is accepted is returned.

        The hold is the /BUSY pin on the CPU's RDY [wiki: VDC pinout]: only the CPU stops. The
        VDC's syncs come from the VCE, so the display keeps its lines while the CPU waits, and a
        VRAM -> VRAM transfer the CPU waits on meets the display start like any other: paused
        (C7, the default) or cancelled (`dma_resumes=False`, which serves the access there).
        Issue 0004: the wait used to run this chip alone to the transfer's end, lines ahead of
        the board's line clock, so the display never started during it."""
        if not self.bsy:
            return mclk
        if self._serve is not None:
            served = self._serve(self)
            if served > mclk:
                self._hold(served - mclk)
            return max(served, mclk)
        return self._wait_alone(mclk)

    def _wait_alone(self, mclk: int) -> int:
        """`_data_access` for a VDC with no board: no line clock reaches it during the wait."""
        now = mclk
        while self.bsy and self.dma.busy:  # the pending access is stuck behind a transfer
            due = self.dma.next_event()
            if due is None:  # paused behind the display: nothing to wait for but the end of it
                self.dma.force_complete(now)
                break
            if due > now:
                self._hold(due - now)
            self.catch_up(due)
            now = max(now, due)
        if self.bsy:
            wait = self._commit_at - now
            if wait > 0:
                self._hold(wait)
                now = self._commit_at
            self.commit_pending()
        return now

    def _schedule_commit(self, mclk: int) -> None:
        if self.dma.busy:  # waits for the transfer; its end commits (BSY meanwhile)
            self._commit_at = 1 << 62
            return
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
        """The 9-bit VDC output for the line that just ran (drawn by `render_line`)."""
        row = self._row
        if row is None or len(row) != dots:
            return [0x100] * dots
        return row
