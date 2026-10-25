"""The VDC's two DMAs and burst mode: VRAM -> VRAM, and VRAM -> sprite attribute table.

[hw: pcetech 5.4; mfr: Hudson HuC6270 manual DCR/SOUR/DESR/LENR/DVSSR]

VRAM -> VRAM: starts when LENR's MSB is written; one word per two dots (read, then write); SOUR
and DESR step up or down by DCR D2/D3 (not by the CR increment), LENR counts down and ends at
$FFFF; MAWR, MARR, the read buffer and the write latch are untouched. A transfer that is running
when the display period starts is **paused and resumes once the VDC is free again** (C7:
MacDonald, tier 2, and Mesen2 say so; Hudson's manual says the remainder is not transferred
and Mednafen cancels it; `resume=False` selects that reading). Time: 2 dots per word is
Mednafen's and Mesen2's.

VRAM -> SAT: armed by a write to DVSSR, started when the display period ends (or every frame
with DCR D4); the 256 words are copied at the start and the VDC is busy for 1024 dots, which
is three lines at 5 MHz, "four lines after the last active line" as pcetech says (U2). The
done interrupt (DCR D0) follows.

Burst mode (CR D6 and D7 clear when the frame starts) is held by the sequencer; the SAT
transfer and VRAM DMA are allowed whenever the display is not drawing.

While either runs, CPU VRAM accesses wait (BSY).
"""

from __future__ import annotations

from pcengine_python.vdc import regs as r

SAT_DOTS = 1024  # [emu: Mednafen "1024 VDC cycles"; Mesen2 the same]
DMA_DOTS_PER_WORD = 2


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

    # -- state --------------------------------------------------------------------------------

    @property
    def busy(self) -> bool:
        """CPU VRAM accesses wait while a transfer runs, paused or not."""
        return self.running or self.sat_end is not None

    def allowed(self) -> bool:
        """The VRAM is free of display fetches (blanking, or burst mode)."""
        seq = self.chip.seq
        from pcengine_python.vdc.sequencer import VPhase

        return self.sat_end is None and (seq.vphase != VPhase.VDW or seq.burst_mode)

    def next_event(self) -> int | None:
        times = []
        if self.sat_end is not None:
            times.append(self.sat_end)
        if self.running and self.allowed():
            halves = (self.chip.regs.value[r.LENR] + 1) * DMA_DOTS_PER_WORD
            if not self._read_phase:
                halves -= 1  # the read of the current word is done
            times.append(self._t0 + halves * self.chip.seq.divider)
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
        """The SAT transfer test of Mednafen's Run loop: after the display period."""
        self.advance(now)
        chip = self.chip
        if self.satb_pending or chip.regs.value[r.DCR] & 0x10:
            self.satb_pending = False
            start = chip.regs.value[r.SATB]
            for i in range(256):
                chip.sat[i] = chip.vram[start + i] if start + i < len(chip.vram) else 0
            self.sat_end = now + SAT_DOTS * chip.seq.divider
        else:
            chip.seq.burst_mode = True
        self._t0 = now

    # -- running ------------------------------------------------------------------------------

    def advance(self, t: int) -> None:
        """Run what is due up to master-clock time `t`."""
        chip = self.chip
        if self.sat_end is not None and self.sat_end <= t:
            end, self.sat_end = self.sat_end, None
            if chip.regs.value[r.DCR] & 0x01:
                chip.status |= r.DS
            chip.seq.burst_mode = True
            chip.commit_pending()
            self._t0 = end
        if not self.running or not self.allowed():
            if self.running:
                self._t0 = t  # paused: no progress, the clock keeps moving
            return
        regs = chip.regs.value
        half = chip.seq.divider  # one dot: the read, then the write, of each word
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

    def force_complete(self, now: int) -> None:
        """A CPU VRAM access finds the VDC busy for an unknown time (paused DMA): finish it, as
        Mednafen does when nothing can wait for it (its 'DMA completion forced')."""
        if self.sat_end is not None:
            self.advance(self.sat_end)
        saved = self.chip.seq.burst_mode
        self.chip.seq.burst_mode = True
        self._t0 = now - 2 * 65536 * self.chip.seq.divider * DMA_DOTS_PER_WORD
        self.advance(now)
        self.chip.seq.burst_mode = saved
