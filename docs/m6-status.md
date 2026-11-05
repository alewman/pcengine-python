# Milestone 6 status: the SuperGrafx (2026-11-05)

The SuperGrafx is built as the add-on `supergrafx-python` (`/data/emu/supergrafx-python`, local,
nothing pushed) pinning this board by `git+file` at 5d9dc86. The full record, the judges and the U/C
entries (C-SGX1, U-SGX1-U-SGX8, C-MESEN1) are in that repository's `docs/m6-record.md`. What belongs
here:

- **Socket audit result**: one board change, [issues/0001](issues/0001-second-vdc-not-run-by-the-board.md)
  (`Board.vdcs`, one instance per `Machine.vdc_count`), commit 5d9dc86. `vdc_count=1` is unchanged:
  230 tests pass on CPython and PyPy, and the captured frames of Alien Crush (USA) and the Covell CPU
  test (150 frames, SHA-256 of rows and dividers) are identical before and after, run once each,
  niced. The 18-picture gate was not rerun (no VDC/VCE code changed; no sweeps were allowed that day).
  `tests/test_sockets.py` has a test for the second instance.
- **Still open for the core**: `ST0-ST2` cannot be told from stores to `$FF:0000/2/3` on the bus;
  the add-on reads `cpu._opcode`. A public accessor in huc6280-python removes the private read.
- **The five library cards** at frame 300: four row-identical with Mesen2 and Beetle PCE, the fifth
  identical with Beetle and one row (frame line 14) different from Mesen2, which draws that row blank
  in PC Engine mode too (C-MESEN1, not the VPC).
- **The fallback** (the SuperGrafx as a one-VDC machine-table mode) was measured: it draws the wrong
  picture on 4 of 5 cards at frame 300. The add-on stays; the `PixelPath` cost was already within
  noise at M3.
