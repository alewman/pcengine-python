# Milestone 5, lockstep half: the board against MAME and Mednafen, instruction by instruction

Run 2026-10-24 with `scripts/lockstep.py` (the library sweep and the card mappers are in
[m5-record.md](m5-record.md)). Both referees are **emulators, tier 5**: neither is a judge, and a
third vote does not make one ([validation.md](validation.md)). Every difference below is named with
its tier; nothing is masked except the B flag (not a stored flag of the core). An **experiment
flag** makes the board behave as the referee does *at one named point*, so the run can go on past a
known difference; each flag is off by default and its use is counted in the output.

## The harness

```text
python -I scripts/mednafen_record.py CARD.7z --out DIR --count 20000000   # Mednafen 1.32.1 trace build
python -I scripts/mame_trace.py pce|tg16 CARD.7z --seconds 20 --out DIR   # MAME 0.285
python scripts/lockstep.py mednafen DIR/error.log DIR/cart.pce [flags]
python scripts/lockstep.py mame     DIR/error.log CARD.pce [--tg16] [flags]
```

- Mednafen is the trace build of the sibling repository (huc6280-python, read only here: its
  binary, built from the pinned source plus `tools/mednafen-trace.patch`, `--without-libflac`).
  3.4 million instructions take about a second; 20 million, about 950 MB of log per game.
  The trace is `PC A X Y S P ticks` and `M MPR0-7`, before each instruction; there is no beam
  position. MAME's is `C PC A X Y S P ticks beamy beamx frame MPR1-4`, 30-35 million instructions
  in 20 emulated seconds, about 17 minutes of wall time (debugger trace), 1.3-1.8 GB.
- How the board is started as each referee starts. **MAME**: beam line 260, 263-line frames
  (`lines_follow_vce_bit2=False`, MAME ignores the bit), x = 0 at the end of the sync (as M1). **Mednafen**:
  its VCE powers up in the vertical sync with 4095 + 30 clocks left and the horizontal sync begins at
  time zero, so scanline 0 begins 4095 clocks after the first instruction (`mednafen_start()`); it
  honours VCE bit 2; its I/O port reports TurboGrafx-16 for every card (the board row is
  `TURBOGRAFX_16` against Mednafen; MAME's `pce` driver for the Japanese cards, `tg16` for the `(USA)`
  one). Interrupt entries are compared as the logs show them (the entry is a prefix of the next line).
- Speed: CPython 3.14 about 21,000 instructions per second through this harness, so 20 million is
  about 16 minutes. PyPy 3.11 was *slower* on a 3 M-instruction run (15,000 per second, 199 s against
  139 s; the reason was not investigated); CPython was used for every run here. The runs went in
  parallel in the background; the traces were deleted afterwards.
- Experiments in `scripts/lockstep.py` (all off by default): `--mame-csh --mame-blocks
  --mame-entry7 --mame-vertical` (MAME's behaviour, from M1); `--adopt-reset-s` (Mednafen's S = 0 at
  reset); `--adopt-io-waits` (add Mednafen's VDC/VCE wait states to the board's clock after an
  instruction that touched `$FF:0000-07FF`); `--adopt-power-on` (Mednafen's checkerboard colour
  table); `--adopt-timer-lag` (the timer interrupt reaches the CPU only when the referee enters it);
  `--resync-late` (when the referee enters an interrupt one instruction before the board does, run
  that instruction, enter, and carry on if all registers then equal the referee's); `--adopt-cd-sense`
  (`$1000` bit 7 clear, as MAME reads it); `--vblank-dots mednafen` (the vblank flag at the start of
  the display width, Mednafen's own position; the board's default is -8, fitted to the photographs);
  `--raster-shift N` (the raster N master clocks earlier against the CPU).

## What agrees without any override (Mednafen)

On the Covell ROM and on R-Type the stream needs nothing for: **C3** (interrupt entry 8 cycles,
54 entries on the test ROM, 668 in R-Type, each equal to the tick), **C7** (`CSH` at instruction 2,
clock equal), **C14** (the ROM's block fill at instruction 11: A, X, Y equal with the core's pushes),
the 8-cycle block structure, every register and MPR at every instruction. MAME agrees with none of
C3, C7, C14 (M1: MAME 7, after, and no pushes).

## The Covell ROM against Mednafen (M1's lockstep)

Core a379416, 2,100,000 instructions recorded.

| Flags | First difference | Cause and tier |
| --- | --- | --- |
| none (vblank -8) | instruction 0, **S**: Mednafen `$00`, board `$FF` | the registers at power-on are random on hardware (U2); Mednafen's `Power()` zeroes S, MAME and the core give `$FF`. Tier 5 convention |
| `--adopt-reset-s` | 136,994, the first vblank interrupt: the board enters 8 instructions (30 ticks) before Mednafen | the **vblank position** (U19): -8 dots is the photograph fit (tier 1); Mednafen's own is the start of the display width, 24 dots later (Covell: its VSync "triggers too late") |
| + `--vblank-dots mednafen` | 201,927, clock: the board is 14 ticks short on `ST2 #$01` to the VDC data port | **VDC wait state** (U18/U20): Mednafen charges 19 ticks for the access, the board 5. Three interrupts equal to the tick before it |
| + `--adopt-io-waits` | 290,925: Mednafen enters the 7th interrupt at the boundary where the board asserts its line, the board one instruction later | **interrupt visibility** (U21): the line rises exactly at an instruction boundary (probed: mclk 3,584,877, the start of the next instruction); Mednafen counts it as visible, the core's sample does not. 6 entries equal first |
| + `--raster-shift 1` (also 2 and 3; not 0, not 4) | **none in 2,100,000 instructions**, 54 entries | the raster placed 1 to 3 master clocks earlier against the CPU, i.e. less than one high-speed cycle: the tie rule of U21. 36 wait states adopted, 14 to 32 ticks, all in the first 200,000 instructions |

So against Mednafen the M1 lockstep gap closes completely, with four named overrides, each an
emulator-tier convention: the reset S, the vblank position (Mednafen's own), 36 VDC wait states, and
a 1-3 clock tie rule. `--resync-late` is not needed there (7 late entries without the shift, 0 with).

## Six games, 20 million instructions each: what was reached

Cards: R-Type I, Gradius, Final Soldier, After Burner II, Bomberman '94 (Japan) and Bonk's
Adventure (USA), read in place and extracted in the scratchpad. Recorded: 20 M instructions of
Mednafen, 30-35 M of MAME. **Only R-Type reaches 20 million; the other five stop at named causes.**
Counts are instructions equal before the first difference (the instruction at that index differs).

### Against Mednafen

"Level 1" = `--adopt-reset-s` only. "Full" = `--adopt-reset-s --adopt-io-waits --adopt-power-on
--adopt-timer-lag --resync-late --vblank-dots mednafen --raster-shift 1`.

| Game | No flag | Level 1 | Full | First difference under Full: cause (tier) |
| --- | --- | --- | --- | --- |
| R-Type I | 0 (S) | 137,047 clock (VDC wait) | **20,000,000**, 668 entries, 1,390 waits adopted (27-54 ticks) | none |
| Gradius | 0 | 16,891 vblank position | 107,737 | IRQ1 reaches Mednafen one instruction before the board; the instruction in between changes A, so it cannot be resynced (U21, tier 5 v 5). 148 timer entries gated, 87 waits |
| Final Soldier | 0 | 17,340 vblank position | 630,583 | an interrupt entry one instruction apart after 2,607 entries (2,520 timer entries gated; 5 late IRQ1 entries resynced; waits adopted include 907, 3,653 and 4,551 ticks, which are not slot waits: unexplained size, see below) |
| After Burner II | 0 | 187 clock | 187 | **SATB DMA stall**: the ROM writes a VRAM word while the sprite-table DMA runs; the board holds the CPU until the DMA's end (3,071 clocks, 1,023 ticks); Mednafen charges 5 ticks. A board model (M3, "a second data access waits behind a transfer") against Mednafen's, tier 5 |
| Bomberman '94 | 0 | 435 clock (VDC wait) | 343,164 | `LDA $25` (a RAM byte filled from a VDC status read in the handler): the byte differs (1 against 0), probably a VDC status bit (bit 0, sprite collision) stored earlier by the handler and set in the board only (not checked): **VDC status flag timing** (U20-class, M3; tier 5) |
| Bonk's Adventure | 0 | 85,378 vblank position | 142,068 | `LDA $0000` (VDC status): Mednafen `$60`, board `$20`: **BSY** (bit 6) set in Mednafen, clear in the board (the VRAM-access slot model, U1/U20, tier 5) |

- **The timer.** Three of the six games (Gradius, Bomberman '94, Final Soldier) stopped, before the gate, at an
  interrupt the board took *earlier* than Mednafen, in each the timer (TIQ). Mednafen shows the timer interrupt to the CPU
  between 0 and ~300 ticks (a few hundred master clocks to a line) after the underflow, variably; the
  board shows it at the underflow (pcetech 2.2, tier 2, the model of M4). `--adopt-timer-lag` reports
  the lags (Gradius: 148, median 9, max 37,074; Bomberman: 16, median 25, max 235; Final Soldier:
  2,520, median 2, max 114,553). The large maxima are lines left asserted until acknowledged, not a measure of the
  delay. This difference cannot be decided without hardware: the board follows the tier-2 source.
- **The Final Soldier waits of 907, 3,653 and 4,551 ticks** are adopted as waits by the harness but are
  too long to be slot waits; they are probably VDC accesses blocked behind a DMA (the same model as
  After Burner; not checked).
- **Colour table at power-on** (`--adopt-power-on`): Final Soldier reads `$0404/5` before writing the
  table; Mednafen has a checkerboard, the board zeros, hardware is random (U7). Named, tier 5.

### Against MAME

Flags: the M1 set. "B" = `--mame-csh --mame-blocks --vblank-dots 0 --adopt-cd-sense`; "C" = B plus
`--mame-vertical --mame-entry7`; "D" = C plus `--resync-late`. Without flags every game stops at the
`CSH` (instruction 2 or 5; C7) except Bonk's Adventure, which stops at instruction 5 on its first read
of `$1000` (**C6**: MAME reads bit 7 clear with no CD unit, pcetech and Mednafen set).

| Game | B | C | D | Cause of the stop under D (tier) |
| --- | --- | --- | --- | --- |
| R-Type I | 144,876 | 172,272 | 172,272 | the first vblank entry: clock off by 2 ticks (MAME's entry 7 v the board's 8 is overridden; the phase is MAME's vertical stepping, U19) |
| Gradius | 1,864 | 1,864 | 1,864 | the first interrupt entry 3-4 ticks early (U19/U21) |
| Final Soldier | 701 | 701 | 1,177 | an interrupt entry one instruction apart (U21; MAME's visibility is not repeatable, M1) |
| After Burner II | 53,136 | 53,044 | 53,044 | the SATB DMA stall, as against Mednafen |
| Bomberman '94 | 133,715 | 133,715 | 133,715 | the second interrupt: MAME enters the IRQ1 vector (`E133`), the board is at `E11D`, near the timer handler: a different interrupt or order (not run down) |
| Bonk's Adventure | 58,156 | 58,156 | 58,156 | the first interrupt entry one instruction apart (U21) |

MAME has no VDC wait states, so the stops are interrupts and one DMA stall; as in M1, MAME's
interrupt visibility is not repeatable at sub-instruction level, so a long MAME lockstep is not to
be had with the flags that exist. Nothing here is "unexplained" in the sense of an unnamed cause, but
the exit "6 games, 20 million instructions, 0 unexplained against both" is **not met**: one game
against Mednafen, none against MAME.

## What this shows, and what it does not

- **Shows**: the core on the board executes the same instruction stream, with the same registers,
  MPRs and (for R-Type, 20 M instructions, 668 interrupts) the same clock as Mednafen's, given five
  named conventions; and the interrupt-entry cost (C3), the speed switch (C7) and the block-transfer
  push (C14) are the same as Mednafen's with no override.
- **Does not show**: that either is right. Where the board differs, the cause is a VDC/VCE slot or
  status model (U1, U18, U20), a sub-instruction visibility rule (U21), the power-on state (U2, U7)
  or the timer's delivery; all of them are tier 5 against a board built on tier 2-3 sources or on
  provisional models. No difference found here has a tier-1 judge.
- **Open, for the owners of those models** (M2/M3): the SATB-DMA write stall (After Burner), the
  status-flag timing (Bomberman, Bonk), and the one-to-three-clock tie of interrupt visibility.

## Verifying this

`tests/test_lockstep_readers.py` covers the two trace readers. The runs themselves need the traces
(not stored) and the cards (BYOR); the commands above reproduce them.
