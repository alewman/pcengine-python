# Documents

Read in this order.

| Document | What it holds |
| --- | --- |
| [start-here.md](start-here.md) | The machines as data (PC Engine, TG-16, SuperGrafx, CD); the clocks; the module shape; performance as an extrapolation; floors and rules |
| [memory-map.md](memory-map.md) | The HuC6280's MMU and the 21-bit map, the hardware page, the I/O buffer, the I/O port and pads, interrupts, the timer, clocks; **who owns what** between core and board |
| [sockets.md](sockets.md) | What the Sega socket list teaches; the 12 proposed sockets; CD and SuperGrafx as add-on or mode; what each add-on needs |
| [vdc.md](vdc.md) | The HuC6270: registers, VRAM, BAT, sprites, DMA, burst mode, the display and the memory schedule, what is unknown |
| [vce.md](vce.md) | The HuC6260: palette, dot clocks, 262/263 lines, palette conflicts, output colours |
| [psg.md](psg.md) | The six-channel PSG: registers, DDA, noise, LFO, mixing; no hardware reference exists |
| [cartridge.md](cartridge.md) | The HuCard connector, mirroring, mappers (SF2, Populous, Tennokoe), the library census |
| [cd.md](cd.md) | CD-ROM², Super CD-ROM², Arcade Card in brief; BIOS handling; what boots here |
| [validation.md](validation.md) | Every oracle by tier with pins and provenance; what ran here; the detector comparison |
| [mame-oracle.md](mame-oracle.md) | The verified MAME 0.285 recipe, output format, seven traps |
| [handoff-brief.md](handoff-brief.md) | Decisions, the embedding contract for huc6280-python, 8 milestones with judges, U and C lists, 14 open decisions |
| [m5-lockstep-record.md](m5-lockstep-record.md) | **Milestone 5, lockstep half**: the board against MAME and Mednafen instruction by instruction; the Covell ROM closes against Mednafen, six games' first differences named |
| [m4-record.md](m4-record.md) | **Milestone 4 as built**: the PSG, the referee comparison (MAME, Mednafen), C13-C24, the timer finished |
| [m3-record.md](m3-record.md) | **Milestone 3 as built**: sprites; 26 titles identical to both detectors with sprites on; the PixelPath cost measured |
| [m2-record.md](m2-record.md) | **Milestone 2 as built**: the background, DMAs and burst mode; the first ten titles against Mesen2 and Beetle PCE; C7 decided |
| [m1-record.md](m1-record.md) | **Milestone 1 as built**: layout, judges and results, provisional items, what the data corrected, new U21-U24 and C9-C10 |

## Findings made while gathering (2026-10-23)

1. **One tier-1 source**: Covell's CPU timing test with photographs of a real PC Engine. Everything
   else for the VDC and PSG is manuals (tier 3), MacDonald's prose (tier 2) or emulators (tier 5).
2. **The VDC's CPU access schedule is not settled by any source here**; Mednafen, the reference,
   approximates it ("assume a 50% hit rate").
3. **The `(USA)` HuCards run only on MAME's `tg16` driver**: US games check the I/O port's country bit.
4. **Mesen2's headless DLL returns black PC Engine frames** until `PcEngineConfig` gets a palette and
   frame skipping is disabled; fixed in `scripts/mesen_run.py`.
5. **MAME 0.285 cannot log hardware-page accesses** (`wpset` is logical; Lua taps logged nothing).
6. **The library has no SF2 card, but the source tree does** ([cartridge.md](cartridge.md), read in place); 152 of 179 cards (listed) need only ROM mirroring; 3 of 80 CDs
   need the Arcade Card; 38 need the Super System Card.
7. **Three emulators (MAME, Beetle PCE, Geargrafx) boot the Super System Card screen** from a CHD; MAME's own CD source lists its
   fader as "sketchy and unchecked against real HW".
8. **"CD Unit SCH.pdf" is a 2020 community redraw, not NEC's schematic**; the MiSTer `docs/logs` captures
   are FPGA signal traces, not logic-analyser captures of a console.
9. **Eight source conflicts** (C1-C8), the first being that `pcetech.txt` titles its VDC and VCE
   sections with each other's names.
