# 0001: the board runs one VDC; a second instance (SuperGrafx) was not stepped, synced or read

Raised 2026-11-05 by `supergrafx-python` (M6, the first add-on to pin this board).
Status: **closed** the same day by the smallest board change (below); the base board's results are
unchanged.

## What the SuperGrafx needed and the sockets did not give

docs/sockets.md lists the SuperGrafx's footprint as five sockets: claims for `$FF:0008-0017` (3),
RAM size (machine table), IRQ1 OR (6), the pixel path (7) and VDC instances (12). Four of the five
already worked: page claims replace the VDC page's handler, `Machine.work_ram_bytes` sizes the RAM,
`Vdc` holds no module state, and `PixelPath.mix` takes a *list* of rows. The fifth was not wired:

- `Machine.vdc_count` existed but nothing read it; `Board` built exactly one `Vdc`.
- A `Vdc` is advanced by the board's scheduler (`next_event`, `catch_up`, `hsync`, `vsync`) and
  read for its picture row at the end of each line (`pixel_row`). The scheduler only knew
  `self.vdc`; a second instance built outside the board would never run.
- `Board.lines()` took IRQ1 from `self.vdc.irq1` only. [hw: sgxtech, "Miscellaneous"] `/IRQ1` is
  shared by both VDCs; the CPU reads both status ports to find the source.
- `PixelPath.mix` was always handed `[vdc 1's row]`, so a mixing path had nothing to mix.

An add-on could have subclassed `Board` and overridden `_run_to`, `_new_line`, `_end_row` and
`lines` (copying the scheduler), or the board could count its VDCs. The second is the Sega
lesson (the board owns the clock; a device that needs time goes through it).

## The change (board.py only; no VDC or VCE code)

- `Board.vdcs`: one `Vdc` per `machine.vdc_count` (`vdc_count=1` is the PC Engine and builds
  exactly what was built before); `Board.vdc` stays the first. The extra instances are built with
  the same power-on stream order, `hold` and options.
- The scheduler steps every instance (`catch_up`, `hsync`, `vsync`, earliest `next_event`).
- `_end_row` hands `PixelPath.mix` one row per VDC, in order.
- `lines()` ORs `irq1` over the instances.
- The extra instances have **no decode**: an add-on claims their pages through socket 3
  (`board.pages.claim`), exactly as a card does.

## Gate

`vdc_count=1` is byte-for-byte the old path (same calls in the same order). Checked: the test suite,
and an A/B of the captured frames (SHA-256 of the rows) before and after on two cards (see
docs/m6-status.md). Not rerun: the 18-picture gate, since no VDC/VCE code changed.

## Still open (not a board matter)

`ST0`/`ST1`/`ST2` are indistinguishable from `STA $0000`/`$0002`/`$0003` at the bus: both reach the
page table as a write to `$1FE000`/`2`/`3`. The VPC must steer only the former to VDC 2
([hw: sgxtech] register `$0E`). The add-on reads the core's `_opcode` (`$03`, `$13`, `$23`)
because the core has no public accessor; a public `opcode` property (or a `store_immediate` flag
on the bus callback) in huc6280-python would remove the private read. Raised for the core, not
done here.
