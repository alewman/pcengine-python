# 0004: what the Rust port found in this board

Raised 2026-11-12 by the pcengine-rust build (its `scripts/reference_notes.py` shows the first two
on this board). Settled 2026-11-13. Status: **closed.** Item 1 was a bug against the board's own
rules and is fixed; item 2 is fixed; items 3 and 4 are left (unreachable, or reachable by design);
item 5 is cleaned up and the reset question documented. No picture of the 18-title gate moved.

## 1. A CPU access that waits for a VRAM DMA let the DMA ignore the display: **fixed**

**What happened.** `Vdc._data_access` ran the waiting chip alone (`catch_up(due)`) to the transfer's
end, which can be many lines ahead, while `hsync` and `vsync` come from the board only after the
access returns. With `dma_resumes=False` and a 16,384-word DMA started 15 lines before the display:
left alone, 13,850 words were not transferred (cancelled, as the switch says); followed by one VRAM
read, 0 were left, the transfer completed as if the display never started, and the CPU was held
about 96 lines. Reproduced on 5533552 with the Rust port's script.

**What the hardware does.** The hold is the VDC's `/BUSY` output wired to the CPU's `RDY` [wiki:
VDC pinout, tier 4]: it stops the CPU and nothing else. The VDC's line and frame are the VCE's
`/HSYN` and `/VSYN` [wiki: VCE and VDC pinouts]; no source has the VCE wait for the CPU. So a wait
that spans the start of the display period meets it, and C7 applies to that transfer as to any
other: Hudson's manual (tier 3) cancels the remainder with no done status, MacDonald (tier 2) halts
and resumes it. The detectors read as behaviour agree that the machine runs through the wait:
Mednafen's `WS_Hook(-1)` steals the CPU's time up to the next VCE/VDC event and repeats; Mesen2's
`WaitForVramAccess` steps the whole system a CPU cycle at a time until the access is served. Neither
runs the VDC ahead of the line clock.

**Decision: fix** (a bug against the board's stated rules: one timeline, C7 and `dma_resumes`). The
board's display events must be delivered during the wait. The board now runs every device, line
clock included, event by event until the waiting access is served, and the CPU is held to that
time:

- default (C7, resume): the CPU stays held through the display period until the paused transfer
  ends after it (Mesen2's behaviour);
- `dma_resumes=False`: the display start cancels the remainder (no DV) and serves the access there;
  the CPU is released at the display start (Mednafen's).

The Rust port's script now prints 13,850 words left in both cases.

**Board functions changed** (for the lockstep ports):

- `Vdc.__init__`: new keyword `serve: Callable[[Vdc], int] | None = None`, stored as `_serve`
  (wiring, not state). The board passes `serve=self._serve_vram`.
- `Vdc._data_access(mclk) -> int` (was `-> None`): returns `mclk` if nothing is pending; with
  `_serve` it calls `served = _serve(self)`, holds `served - mclk` if positive and returns
  `max(served, mclk)`; without `_serve` it runs the old loop, now `Vdc._wait_alone(mclk) -> int`,
  which returns the time it waited to (the DMA end, or `_commit_at` after a slot wait; `mclk`
  otherwise).
- `Vdc.read` and `Vdc.write`: the four call sites (`VRR` read with a pending fetch, `VRR` MSB read,
  `VWR` MSB write, `MARR` MSB write) assign `mclk = self._data_access(mclk)`, so the new access is
  accepted and its slot scheduled (`_schedule_commit`) at the time the wait ended, not at the time
  it began.
- `Board._run_to(target)` is now `while self._step(target) is not None: pass` then
  `self._settle(target)` (the old tail: every VDC, `cpu_io` and the port caught up to `target`).
- `Board._step(target) -> int | None`: one iteration of the old loop, returning the event's time.
  One change of order: a row end is handled first only if no VDC event is earlier
  (`row_at <= vdc_at`); before, a row end that came before the next line start went first even if a
  VDC event was earlier. `_end_row` runs the VDCs to `row_at - 1` itself, so the work done and its
  order are the same; the change only makes `_step` return the time of the event that served the
  access.
- `Board._serve_vram(chip) -> int` (new): from `self.mclk`, `_step(1 << 62)` until `chip.bsy` is
  false (the next line start always exists, so it always moves), then `_settle(now)`; returns the
  time of the step that served it. The held clocks reach `mclk` when the access returns, as before.
- No new state fields, no default changed, no new switch.

**Tests** (fail on 5533552: released at line 44 of frame 1, the transfer complete; pass now):
`test_a_cpu_waiting_on_a_dma_sees_the_manuals_cancel_at_the_display_start`,
`test_a_cpu_waiting_on_a_dma_is_held_through_the_display_while_it_is_paused_c7`
(`tests/test_vdc_background.py`). The comment of the C7 test's 12,288-word transfer said "about 24.6
lines"; it is about 72 (170 words a line at 5 MHz), corrected.

**Not settled:** how long the real chip holds the CPU behind a transfer (U30, C26) is unchanged.

## 2. `Psg.silent_units` was read once in `__init__`: **fixed**

`scripts/psg_compare.py` applies `VARIANTS` with `setattr` on an instance; the host-rate level table
stayed as built. Decision: fix (the switch is documented as a class attribute any instance may set).
`Psg._level_table()` (new) rebuilds `_levels` when `silent_units` differs from `_levels_units` (new
field, set to -1 then built in `__init__`); `Psg._emit` reads the table through it once per call. The
referee comparison was never affected (it uses the step stream). Test:
`test_silent_units_set_on_an_instance_reaches_the_host_rate_output` (fails on 5533552). Note: the
Rust port's script reads `_levels` straight after `setattr`, before anything renders, so it still
prints 0.0 there; the rendered output changes.

## 3. `render_line`'s slice with a negative count: **left** (unreachable)

The hdw event that calls `render_line` lands at most at the row's last dot: at 5 and 10 MHz the row
ends one master clock before the next line's `leave` event, at 7 MHz on it (and the earlier-queued
hdw runs first on the tie), so `first <= dots` and the count is `>= 0`; any later display start
falls after `_leave_hsync`, which drops the line's events. A comment says so; no code change.

## 4. `Capture.finish_line`'s `self.path is None` branch: **left** (reachable by design)

The constructor never stores `None`, but `scripts/pixelpath_bench.py` sets `board.capture.path =
None` to measure the socket against no socket (docs/m3-record.md), as the branch's comment says.

## 5. Small things

- `Psg._acc_steps`, `Psg._reload_lfo_channels` (a no-op called on R8/R9 writes; its comment moved to
  the R8 write) and `PopulousCard.RAM_BANKS`: **removed**. `_acc_steps` was an instance field, so it
  leaves the save state; a state that has it still loads (an extra attribute is set and unused).
- `sockets.py` cites U13, `docs/sockets.md` said U15: the brief's U13 is the expansion video bus and
  U15 the detector outliers, so **docs/sockets.md was wrong**, corrected. Its `reset(kind, mclk)` is
  `reset(kind)` in the code; corrected too.
- `Board.reset(POWER_ON)` does not reset the VDC, VCE, PSG or RAM: **documented, not changed.** The
  board is built at power-on and construction is those chips' power-on state (U7). RAM has no reset;
  the VCE has no reset pin [wiki: VCE pinout]; the VDC has `/RST` [wiki: VDC pinout] but Hudson's
  manual says nothing of what it clears, and the PSG manual is silent; the PC Engine has no reset
  button. No caller needs more (the only callers pass the event on to the card and the port). A host
  that wants a power cycle builds a new board. `Board.reset`'s docstring and docs/sockets.md socket
  10 say this.

## Judges

- **Picture gate**, `scripts/m2_ours.py`, PyPy, extracted cards, US cards as TurboGrafx-16, 18 titles
  of docs/m3-record.md (the first ten at 300 frames, Air Zonk and Ballistix at 450; Blazing Lazers,
  Bonk's Adventure, R-Type (USA), Samurai-Ghost, Barbarian (ZX Spectrum), Death Sword (PC), Mai Nurse
  and Gunboat at 300 and 600): 26 pictures, before (5533552) and after: **26 of 26
  byte-identical** (and the same frame numbers and VCE control). The comparisons against Mesen2 and
  Beetle PCE therefore stand; they were not rerun.
- **Library smoke** (`scripts/m5_sweep.py --names`, the nine "different" cards of docs/m5-record.md,
  After Burner II among them), code at a156918, frames 300 and 600, Mesen2 and Beetle
  PCE run fresh: **18 of 18 checkpoints have the same share of equal rows and pixels against both
  referees as the full run of 2026-11-12** (`tests/detectors/m5-sweep-full-2026-11-12.txt`); no
  verdict moved. The other 170 cards were not rerun.
- Quick suite: CPython 3.14 and PyPy, ruff check and format: clean.
