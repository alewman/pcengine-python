# 0004: what the Rust port found in this board (not yet decided)

Raised 2026-11-12 by the pcengine-rust build (its `scripts/reference_notes.py` shows the first two
on this board). Status: **open; nothing changed.** pcengine-rust reproduces each (275 lockstep
cases identical), so the two boards agree; the question is whether this board is right.

1. **A CPU access that waits for a VRAM DMA lets the DMA ignore the display.** `Vdc._data_access`
   calls `catch_up(due)` with the transfer's end, which can be many lines ahead, while `hsync` and
   `vsync` come from the board only after the access returns. With `dma_resumes=False` and a
   16,384-word DMA started 15 lines before the display: left alone, 13,850 words are not
   transferred (cancelled, as the switch says); followed by one VRAM read, 0 words are left, the
   transfer completes as if the display never started, and the CPU is held about 96 lines. So
   `dma_resumes` cannot matter for a transfer the CPU waits on. No judge was consulted yet.
2. **`Psg.silent_units` is read once in `__init__`.** `scripts/psg_compare.py` applies `VARIANTS`
   with `setattr` on an instance, which leaves the host-rate `_levels` unchanged. The referee
   comparison is unaffected (it uses the step stream and its own curve).
3. `render_line`'s `row[first:end] = pixels[: end - first]` would take a negative count if the
   display started past the row's end; unreachable (the next line's sync drops such events).
4. `Capture.finish_line`'s `self.path is None` branch is unreachable through the constructor.
5. Small: `Psg._acc_steps`, `_reload_lfo_channels` and `PopulousCard.RAM_BANKS` are unused;
   `sockets.py` cites U13 where `docs/sockets.md` says U15; `Board.reset(POWER_ON)` does not reset
   the VDC, VCE, PSG or RAM.

Item 1 is the one about behaviour. Any change here is repinned and transcribed into pcengine-rust.
