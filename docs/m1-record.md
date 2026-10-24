# Milestone 1 record: what is built, what judges it, what is provisional

Status (2026-10-24): **the CPU-independent half is built and green; the Covell and MAME rungs wait
on huc6280-python's rung 1** (its first commit with a passing rung 1 is the pin; at the time of
writing the core had rung 0, the opcode map, only). The board is driven by `tests/fake_devices.py`'s
`ScriptedCpu`, which makes the same one-callback-per-cycle calls the core's bus contract promises.

## Layout as built

```
src/pcengine_python/
  machine.py       the machine table and the clock constants (each with its source tier)
  sockets.py       the Protocols: Card/CardSlot, PortDevice, PageHandler, BoardPins (hold, IRQ2),
                   Clocked, IrqLine, PixelPath/DirectPath, VideoTiming, AudioSource, ResetKind,
                   ControllerPort
  pagetable.py     8192 x 256-byte pages; base map + claim/release; Ram, Unmapped
  hardware_page.py bank $FF as 32 page handlers (VDC, VCE, cpu_io; $1800-$1FFF left to claims)
  cpu_io/          timer, $1400 interrupt controller, $1000 I/O port, I/O buffer (boundary-tested)
  pads.py          2-button, 6-button, 5-port multitap
  vce.py           colour table, control, dot clock; replaceable RGB table
  vdc/             regs, VRAM port + status/IRQ1 (chip.py), vertical state machine and line events
                   (sequencer.py) (boundary-tested)
  psg/             register file only (the voices are M4) (boundary-tested)
  video.py         Timeline (line/frame clock, 262/263) and Capture (rows of 9-bit values)
  cards.py         the standard ROM card with mirroring
  board.py         one master-clock timeline; the CPU callbacks; IRQ delivery
  system.py        board + CPU, run_frame
tests/             138+ tests, CPython 3.14 and PyPy 3.11 both green
```

## Judges and results

| Item | Judge (tier) | Result |
| --- | --- | --- |
| I/O buffer, the worked example of pcetech 3 note 1 | MacDonald, tested on a console (2) | exact, test `test_pcetech_io_buffer_worked_example` |
| timer: period `latch + 1` ticks of 3072 clocks, 0 counts as 1, $7F as 128, underflow rather than 1 -> 0, reload at the underflow, freeze on disable, reload from the latch on enable, latch write leaves the count alone | pcetech 2.2 (2); HuC6280 manual 2.7 (3) | exact |
| `$1402`/`$1403` layout, the line state visible while masked, any write acknowledges the timer | pcetech 2.1 (2); manual 2.4 (3) | exact |
| I/O port bits, country by machine row, CD sense follows the *port*, not the slot | pcetech 4 (2) | exact; C6 polarity unresolved (follows pcetech) |
| output port powers up high | HuC6280 manual 2.5 (3) | SEL and CLR power up set |
| pads: 2-button groups, CLR high zeros, Turbo Tap counter, reset sequence, `$0F` empty port, 6-button scans | pcetech 4 (2); pce-devel notes (4) | tested; mouse not modelled (U12) |
| VCE colour table, address advance after the MSB, `$0405` bits 7-1 set, unused registers `$FF`, 8-byte mirror, dot clock bits | pcetech 6 (2); VCE manual (3) | exact |
| VDC bus: select/status/data, MAWR/MARR/VWR/VRR with the CR increment, write latch, buffer, invalid registers, status clears except BSY, BSY raises no IRQ, mirrored half | pcetech 5 (2); VDC manual (3) | exact; the mirrored-half read (0) is U23 |
| frame layout: vsync is the last 3 lines; first display line = VDS + VSW; vblank flag on the first line after VDW; RCR counts from `$40` at the first active line; `$146` at the next frame's line 24; out-of-range values never match | pcetech 5, 5.1, 7 (2) | line-exact; the sub-line position is U19/U22 (tier 5) |
| pricing: 12/3 master clocks, VDC and VCE access one cycle longer, `hold` | pcetech 2.4, 3 (2) | exact; where in the cycle the device sees the access is U21 |
| a mid-line palette write changes the row from the dot it was made on | the mechanism of Covell's test | exact (dot = first dot at or after the write) |
| **Covell's CPU test photographs** (tier 1): vertical split for every 2-8 cycle group | needs the core | **waiting** |
| **MAME instruction-stream lockstep on the test ROM**, 0 unexplained | needs the core | **waiting** |

## Provisional items, with their tier (the milestone's "undecidable" list)

U1, U19, U20 (VDC CPU slot schedule, sub-line positions, block-transfer rows): tier 5; U4: not
modelled yet (palette-access conflict is M2/M3); U21-U24 and C9-C10 below. No item here needed a
console and none was guessed silently: each has a named default in code with a `# U..` comment.

## What the data contradicted in the Phase 0 documents

- **The VDC does not step by 8-dot character cycle.** Mednafen's line counter steps 4 dots before
  the end of the display width and its display-start events sit at `(HDS + 1) * 8` dots plus 8 after
  the sync: not on the 8-dot grid. The sequencer is event-driven at dot granularity. (start-here.md,
  vdc.md and the brief's "decided" list said character cycle; corrected there.)
- **A 256-wide line's events run past the line.** With HDS 2 and HDW `$1F` the display width ends
  at 365 + 1024 = 1389 master clocks after the sync starts, 24 clocks into the next line; so the
  next sync must not discard the pending events, and a picture row is measured from the *end* of the
  sync (Mednafen's scanline), not from its start. A first version cut six dots off every 256-wide row.
- **The block-transfer zero-read rule is the core's, not the board's** (huc6280-python brief,
  "The core boundary"). The brief here said the board could not tell; whether the core still calls
  `read_byte` for those reads (and so would load the I/O buffer) is to be checked at the first pin.
- **RCR `$146` needs 263 line-counter steps per frame.** Mednafen drops the step pending at the
  vertical sync, which would make `$146` unreachable although pcetech 5.1 documents it; the board
  takes the step instead (C9).

## New unknowns and conflicts

| # | Entry | Default and tier |
| --- | --- | --- |
| U21 | Where inside a CPU cycle a device sees the access, and where the VDC/VCE stretch cycle goes | the base cycle elapses, then the access, then the stretch (tier 5 convention); Covell's photographs place it |
| U22 | The dot positions of the VDC's line events (display start, vblank test, line-counter step) | Mednafen's, restated in master clocks (tier 5) |
| U23 | Reads of the mirrored VRAM half | return 0 (Mednafen's zero-filled array; pcetech says "sometimes corrupted") |
| U24 | Delay from the timer's enabling write to its first tick | one full period, 3072 master clocks (MAME, Mednafen); the prescaler reset itself is tier 3 |
| C9 | Mednafen drops the line-counter step pending at the vertical sync; pcetech 5.1's RCR range needs it | take the step (tier 2 over tier 5) |
| C10 | Multitap read with CLR high right after the reset write: pcetech says pad 1's directions, the pce-devel port table implies 0 | pcetech's (`MultiTap(clr_high_reads_pad=True)`) |
