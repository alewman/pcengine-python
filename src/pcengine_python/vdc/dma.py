# SPDX-License-Identifier: MIT
"""The VDC's two DMAs and burst mode: VRAM -> VRAM, and VRAM -> sprite attribute table.

[hw: pcetech 5.4; mfr: Hudson HuC6270 manual DCR/SOUR/DESR/LENR/DVSSR]

VRAM -> VRAM: starts when LENR's MSB is written; SOUR and DESR step up or down by DCR D2/D3 (not
by the CR increment), LENR counts down and ends at $FFFF; MAWR, MARR, the read buffer and the
write latch are untouched. A transfer that is running when the display period starts is **paused
and resumes once the VDC is free again** (C7: MacDonald, tier 2; Mesen2 is observed to do the
same; Hudson's manual says the remainder is not transferred, and Mednafen is observed to cancel
it; `resume=False` selects that reading).

Time per word: a word is one VRAM read and one VRAM write, and the VRAM access width (MWR VM) is
"how many clocks should be used for VRAM ... accesses, or for block transfer" [mfr: MWR (a)]: one
dot per access at width 1, so **2 dots a word** in mode 0, 4 in modes 1 and 2, 8 in mode 3 (the
mode as the last vertical blanking took it). DOC for the reading of the table, the per-word count
a derivation from it (HYPOTHESIS for modes 1-3, which no game here uses: pcetech 5.1).

VRAM -> SAT: armed by a write to DVSSR's MSB [mfr: "triggered by access to the high byte"],
started when the vertical blanking period begins (or every frame with DCR D4) [mfr: note (b)]; the
256 words are copied at the start and the VDC is busy until the done flag (DCR D0), which comes
**three lines later**: "four scanlines after the end of the active display period (e.g. if the
last line of the active display is $DF, it happens at $E3)" [hw: pcetech 5.4, tier 2; MacDonald
measured it at the 5 MHz dot clock as far as he says; what it is at 7 and 10 MHz is open, U2].

Burst mode (CR D6 and D7 clear when the VDC's frame starts) is held by the sequencer; the SAT
transfer and VRAM DMA are allowed whenever the display is not drawing.

While either runs, CPU VRAM accesses wait (BSY).
"""

from __future__ import annotations

from pcengine_python.machine import LINE_CLOCKS
from pcengine_python.vdc import regs as r

SAT_CLOCKS = 3 * LINE_CLOCKS  # [hw: pcetech 5.4] done four lines after the last display line
ACCESS_DOTS = (1, 2, 2, 4)  # [mfr: MWR VM] dots per VRAM access by access-width mode


class DmaEngine:
    def __init__(self, chip, *, resume: bool = True) -> None:
        self.chip = chip
        self.resume = resume
        self.running = False  # a VRAM -> VRAM transfer has been started and not finished
        self._read_phase = True
        self._buffer = 0
        self._t0 = 0  # master-clock time up to which the transfer has been run
        self.satb_pending = False
        self.sat_end: int | None = None  # the VDC is busy with the SAT transfer until then
        self._no_display = False  # finish_without_display: a VDC with no sync never displays

    # -- state --------------------------------------------------------------------------------

    @property
    def busy(self) -> bool:
        """CPU VRAM accesses wait while a transfer runs, paused or not."""
        return self.running or self.sat_end is not None

    def allowed(self) -> bool:
        """The VRAM is free of display fetches (blanking, or burst mode)."""
        seq = self.chip.seq
        from pcengine_python.vdc.sequencer import VPhase

        return self.sat_end is None and (
            self._no_display or seq.vphase != VPhase.VDW or seq.burst_mode
        )

    def _half_word(self) -> int:
        """Master clocks of one access (the read or the write of a word)."""
        return ACCESS_DOTS[self.chip._mwr_cache & 3] * self.chip.seq.divider

    def next_event(self) -> int | None:
        times = []
        if self.sat_end is not None:
            times.append(self.sat_end)
        if self.running and self.allowed():
            halves = (self.chip.regs.value[r.LENR] + 1) * 2
            if not self._read_phase:
                halves -= 1  # the read of the current word is done
            times.append(self._t0 + halves * self._half_word())
        return min(times) if times else None

    # -- commands -----------------------------------------------------------------------------

    def start(self, now: int) -> None:
        """LENR's MSB was written."""
        self.advance(now)
        self.running = True
        self._read_phase = True
        self._t0 = now

    def arm_satb(self) -> None:
        self.satb_pending = True

    def display_started(self, now: int) -> None:
        self.advance(now)
        if self.running and not self.chip.seq.burst_mode and not self.resume:
            self.running = False  # the manual's reading: the remainder is lost, no done IRQ
            self.chip.commit_pending()
        self._t0 = now

    def display_ended(self, now: int) -> None:
        """The vertical blanking period begins: run the armed (or, with DCR D4, every frame's)
        sprite-table transfer [mfr: DVSSR note (b), DCR DSR]. The words are copied now; reads
        past the VRAM give 0, as the CPU port's do (U23)."""
        self.advance(now)
        chip = self.chip
        regs = chip.regs.value
        if not (self.satb_pending or regs[r.DCR] & 0x10):
            return
        self.satb_pending = False
        source = regs[r.SATB]
        size = len(chip.vram)
        for i in range(256):
            address = (source + i) & 0xFFFF
            chip.sat[i] = chip.vram[address] if address < size else 0
        self.sat_end = now + SAT_CLOCKS

    # -- running ------------------------------------------------------------------------------

    def advance(self, t: int) -> None:
        """Run what is due up to master-clock time `t`."""
        chip = self.chip
        if self.sat_end is not None and self.sat_end <= t:
            end, self.sat_end = self.sat_end, None
            if chip.regs.value[r.DCR] & 0x01:
                chip.status |= r.DS
            chip.commit_pending()
            self._t0 = end
        if not self.running or not self.allowed():
            if self.running:
                self._t0 = t  # paused: no progress, the clock keeps moving
            return
        regs = chip.regs.value
        half = self._half_word()  # one access: the read, then the write, of each word
        while self.running and self._t0 + half <= t:
            if self._read_phase:
                src = regs[r.SOUR]
                self._buffer = chip.vram[src] if src < len(chip.vram) else 0
                self._t0 += half
                self._read_phase = False
                continue
            dst = regs[r.DESR]
            if dst < len(chip.vram):
                chip.vram[dst] = self._buffer
            dcr = regs[r.DCR]
            regs[r.SOUR] = (regs[r.SOUR] + (-1 if dcr & 0x04 else 1)) & 0xFFFF
            regs[r.DESR] = (regs[r.DESR] + (-1 if dcr & 0x08 else 1)) & 0xFFFF
            regs[r.LENR] = (regs[r.LENR] - 1) & 0xFFFF
            self._t0 += half
            self._read_phase = True
            if regs[r.LENR] == 0xFFFF:
                self.running = False
                chip.commit_pending()
                if dcr & 0x02:
                    chip.status |= r.DV

    def finish_without_display(self, now: int) -> int:
        """Run a paused transfer to its end as if the VRAM were free and return that time: for a
        VDC with no board, whose display never ends because no sync reaches it. (A choice for
        the chip on its own; a board's VDC always gets the VCE's syncs.)"""
        self.advance(now)
        self._no_display = True
        try:
            if self.running:
                self._t0 = max(self._t0, now)
            end = now
            while self.busy:
                due = self.next_event()
                if due is None:
                    break
                self.advance(due)
                end = max(end, due)
        finally:
            self._no_display = False
        return end
