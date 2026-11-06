# 0002: the board never called `PortDevice.catch_up`, so a port device could not raise IRQ2 by itself

Raised 2026-11-05 by `pcenginecd-python` (M7, finding S1); fixed 2026-11-06. Status: **closed** by the
smallest board change (below); the PC Engine results are unchanged.

## What the CD needed and the board did not give

[docs/sockets.md](../sockets.md) socket 5 names `catch_up(mclk)` for a device with its own clock domain, and
`PortDevice` carries it in the Protocol. `Board._run_to` ran the VDCs and the timer only. A port device
therefore saw time only inside its own register accesses: the CD drive's REQ, a sector arriving or an
ADPCM end could not raise IRQ2 between two accesses (the game polls a different register, or none, and
waits for the interrupt). `CdBoard._run_to` worked around it by subclassing the scheduler.

## The change (board.py only; no VDC or VCE code)

At the end of `Board._run_to`, after the VDCs and the timer: `self.port.catch_up(target)` when a port is
present. `_run_to` runs on every `advance`, i.e. every CPU cycle: a device keeps a cheap early-out.
A card is not caught up (a HuCard has no clock of its own; the Protocol does not ask for it).
Not added: the device's own `next_event`, so the board does not split a stretch at a device's due time
(it is caught up at every cycle boundary, which is finer than any device here needs).

## Gate

`tests/test_sockets.py::test_a_port_device_runs_with_the_board_clock_and_can_raise_irq2_by_itself`
(an alarm port raises IRQ2 at a due time with no access to it; fails with the call removed, passes with
it). No port in the PC Engine path: the captured frames of Alien Crush (USA) and the Covell CPU test
(150 frames, SHA-256 of rows and dividers) are identical before and after, and the suite passes on
CPython and PyPy. The 18-picture gate was not rerun (no VDC/VCE code changed).
