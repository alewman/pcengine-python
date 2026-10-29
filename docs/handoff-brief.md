# Handoff: build `pcengine-python`, the PC Engine / TurboGrafx-16 board

## Context you are inheriting

The family's shape is **chips are cores, boards compose cores; never copy a chip file between
repositories; extract on the second consumer**. Each core is certified on its own against its oracles
and pinned by the boards that use it; each board is validated against hardware-tier test programs, with
MAME and other emulators as detectors only. `famicom-python` (on 6502-python), `snes-python`,
`gameboy-python`, `a2600-python` and `megadrive-python` are the boards to model this one on.
**The add-on shape** (Aubrey, 2026-10-23) is the Sega console pattern: this is the **base board with
documented sockets**; CD-ROM²/Super CD-ROM²/Arcade Card and (probably) the SuperGrafx are separate
boards that pin it ([sockets.md](sockets.md)).

This board embeds one CPU core, built in parallel and **not read or touched by this phase**:

- **`huc6280-python`** (`/data/emu/huc6280-python`): the HuC6280 instruction set on 6502-python's
  frame. This brief **assumes** it exposes one callback per CPU cycle with a 21-bit physical address
  and that **the board owns the clock, the VDC wait states and the IRQ lines**; the core-vs-board split
  of the MMU, timer, IRQ controller and PSG is open decision 4 (recommendation: MMU in the core, the rest
  in the board).

Read, in order, before writing code:

1. [README.md](../README.md): scope, what is fetched.
2. [start-here.md](start-here.md): machines as data, clocks, module shape, performance.
3. [memory-map.md](memory-map.md): the CPU-side map, hardware page, I/O port, interrupts, timer, the core/board split.
4. [sockets.md](sockets.md): what the Sega sockets teach, the proposed list, add-on versus mode.
5. [vdc.md](vdc.md), [vce.md](vce.md), [psg.md](psg.md): the chips.
6. [cartridge.md](cartridge.md): the connector, mapper census; [cd.md](cd.md): the CD in brief.
7. [validation.md](validation.md): every oracle with tier and pin, what ran here.
8. [mame-oracle.md](mame-oracle.md): the verified MAME recipe and its traps.

Then `python -I scripts/fetch_references.py` (or `--verify`): 12 pinned files (MacDonald's two notes, the
Covell test and page, eight PCEdev wiki pages) and 17 repositories. `reference/` and `tests/test_roms/`
are gitignored. Build the libretro cores as in validation.md (`make` in `reference/src/beetle-pce`
and `reference/src/geargrafx/platforms/libretro`).

## Decided by the user

- **Name `pcengine-python`**, package `pcengine_python` (Aubrey's choice).
- **Follow the Sega console pattern: base board + sockets; add-on boards pin it** (2026-10-23).
  Add-on repositories are **not** created in this phase.
- **No hardware, no capture rigs**: the hardware tier is only what is already published; anything
  unsettled is marked undecidable, never planned as a console experiment.
- **Python floor 3.11** (PyPy must be supported), ruff `py311`; modern over compat; reference boards
  are correct, not fast; the family's rules (never copy a chip file; chip extraction only on a second
  consumer; non-CPU single-family chips stay in the board; CPUs own a core).

## Decisions proposed by this Phase 0 (each is an open decision below if it needs Aubrey)

- **NTSC-J PC Engine first**, TurboGrafx-16 as a machine-table row from day one (the I/O port's country
  bit; 93 of 179 library cards are US and will not run without it, measured).
- **One timeline in master clocks**; the board owns it; **the VDC runs on dot-granular line events**; the
  8-dot character cycle is the grid of its CPU window and fetches, not of the raster compare
  ([vdc.md](vdc.md), [m1-record.md](m1-record.md)); sprite and DMA timing
  stay provisional (tier 5) until a tier 1-2 source exists.
- **Sockets defined first, with test-only fakes**, in M1, audited by the add-on Phase 0s before the
  base is tagged.
- **BYOR everywhere**: no ROM, CHD, System Card or BIOS is committed or fetched by the scripts.
- **Compare pictures at the 9-bit palette index, never at RGB** (there is no standard conversion).

## What the board needs from huc6280-python (the embedding contract, as assumed)

1. **One bus callback per CPU cycle, in order**, with the 21-bit physical address (after the MMU) and an
   **access kind**: opcode fetch, operand, data read/write, stack, vector, internal. The HuC6280 has **no
   dummy reads or writes** in read-modify-write ([hw: pcetech §2]); the core must not invent them.
2. **Block-transfer reads of `$FF:0800-$1400` return 0 and do not update the I/O buffer; writes work**
   ([hw]). huc6280-python's brief puts this rule **in the core** (the CPU returns 0); the board only has
   to know whether the core still calls `read_byte` for those reads (it would load the buffer):
   checked at the first pin: it does not (the core calls `idle`); its range stopped at `$13FF`
   until huc6280-python issue 0001, fixed at `7f789e4` (now `$0800-$17FF`; [m1-record.md](m1-record.md)).
3. **`ST0/ST1/ST2` emit physical `$1FE000/2/3`** (not translated) ([hw]).
4. **Speed state readable** (`high_speed`; power-up low) and the cycle in which `CSL/CSH` takes effect
   documented with its source; the board prices a cycle at 12 or 3 master clocks. **Unknown** whether
   `CSH/CSL` take longer when switching ([hw]: tested only without switching).
5. **IRQ1, IRQ2, timer and NMI levels set by the board from inside a callback**; the core samples them
   between instructions (block transfers are not interruptible) and the brief for the core must state the
   sampling cycle with its source: the board needs it to place VDC IRQs. `RTI`, `BRK` (pushes PC+1, B set;
   interrupts push B clear, then D/T clear and I set).
6. **No RDY input**: the board holds the clock between cycles (VDC `/BUSY` is wired to RDY: [doc: wiki]).
7. **Power-up state**: A, X, Y, S, N, Z, V, C random, MPR7 = 0, other MPRs random, P has T,D clear and I,B
   set [hw]: take a seed or fixed values so runs are reproducible (open decision 4 notes the default).
8. **Instances are independent** (no module globals): a second consumer (a Data East arcade board) and the
   lockstep harness each hold their own.

## The gate (defined before any add-on exists)

With nothing in the card slot, port or SuperGrafx sockets the board must be byte-for-byte what it is when
the base is tagged: the MAME lockstep replays (`0 unexplained`), the sweep rows, the PSG referee stream.
An add-on may not move any of these; its first act is to run the base's gate unchanged
(megadrive-python's sockets PR: "0 sweep rows moved").

## Milestones, the judge for each

| # | Milestone | Judge | Exit |
| --- | --- | --- | --- |
| **M1** | **CPU + bus + VCE + a blank VDC + the sockets and fakes**: page table, hardware page, I/O buffer, timer, IRQ controller, I/O port + pads, VDC timing/status/IRQ skeleton (no tiles), VCE palette; the Protocols and fakes of sockets.md | pcetech §3/§4 worked examples (tier 2); Hudson manuals; **Covell's CPU test** photographs (tier 1): every 2-8 cycle group draws a vertical split at the photographed positions; the core's own single-step tests are the core's | all instruction groups match the photographs within one cycle; block-transfer and VRAM X-cycle rows **provisional** (U1, U20); MAME instruction-stream lockstep on the test ROM, `0 unexplained` |
| **M2** | **VDC background**: VRAM port, BAT/CG fetch, scroll, raster compare, VBLANK, VRAM-VRAM DMA, SATB DMA (armed), burst mode | Hudson VDC manual (tier 3), MacDonald §5 (tier 2); detectors for pictures | first 10 library titles reach their title screen with identical 9-bit rows against Mesen2 **and** Beetle wherever the two agree; DMA continuation (C7) decided and recorded |
| **M3** | **Sprites**: SAT, 16 per line, overflow, collision (sprite 0), 32-wide, flips, priority, the `PixelPath` socket on the hot path (**measure it**: within noise) | manual + MacDonald; detectors; the outlier cards (U15) | sprite-heavy games (Blazing Lazers, R-Type, Bonk's Adventure, Samurai-Ghost) agree with the detectors or the difference is named |
| **M4** | **PSG + timer finish**: six channels, noise, LFO, DDA, volume/pan, the `AudioSource` list | Hudson PSG manual (tier 3), MacDonald §10; referees MAME `c6280` and Mednafen at the native step rate | register streams recorded from 5 games reproduce the referee's step stream with `0` differences or named ones (the two referees' disagreement is a finding) |
| **M5** | **HuCard mappers + sweep + lockstep**: mirroring (384K etc.), SF2, Populous, Tennokoe; the 179-card sweep; lockstep against MAME (and Mesen2 trace if its Lua allows) | MAME instruction stream; detectors for pictures | 152 listed cards boot to a picture identical in rows with the detectors or triaged; 6 games lockstep `>= N M` instructions with 0 unexplained (65816-python reached 55.6 M over 7 games); the 26 unlisted images triaged |
| **M6** | **SuperGrafx** (`supergrafx-python`; or mode, open decision 6): second VDC, VPC windows and priority, 32 KiB RAM, the compat switch | `sgxtech.txt` (tier 2); detectors MAME `sgx`, Mesen2, Beetle | the 5 library cards; the VPC priority/window behaviours of sgxtech reproduced |
| **M7** | **CD-ROM² boot** (`pcenginecd-python`): System Card in the slot, CD RAM, BRAM, the interface registers, SCSI-class controller, bin/cue from `chdman`, IRQ2 | the BIOS executing (it is the test); Hudson BIOS manual (tier 3); detectors boot to the same screens (measured here) | the Super System Card screen; a data read (`CD_READ`); 26 System-Card discs first, then 38 Super System Card discs |
| **M8** | **ADPCM, CD-DA, fader, Arcade Card** | detectors' audio only (MAME's fader "sketchy and unchecked against real HW"); the Arcade Card from `arcade_card.cpp`/`pce_acard.cpp` | audio **provisional, tier 5**; 3 Arcade discs boot |

A milestone is closed when its exit holds and its **undecidable** items are written in the
certification record as "provisional, tier N".

## Unknowns (U) and Conflicts (C), each with its tier

**Unknowns** (open questions; tier = the best source available for it; none is settleable without
hardware unless noted):

| # | Unknown | Best source / tier | Status |
| --- | --- | --- | --- |
| U1 | The VDC's CPU access schedule in active display (which dot cycles the CPU gets; power-up phase) | hw text for mode 0 only (tier 2); FPGA capture (tier 5); Mednafen *approximates* (50% hit); Covell: depends on how the VDC "awakened" | **undecidable**; provisional |
| U2 | When VRAM-to-SAT DMA starts and how long it runs; done IRQ "four lines after active display" | tier 2 vs tier 3 wording | provisional |
| U3 | Sprite fetch details: the dropped-sprite rule on narrow/wide displays, per-sprite fetch cycles (SM table), the "5/10/16-cycle" figure of the brief (**not found**), BXR/BYR latch time | manual (tier 3), emulators | provisional |
| U4 | VCE palette-access conflict: how many dots a CPU access holds | MacDonald, prose only (tier 2) | provisional |
| U5 | VCE bit 2 and the 262/263-line frames (blur, field offset) | C3 | provisional |
| U6 | HuC6280 vs HuC6280A; PSG attenuation table, noise polynomial, LFO details | manual (dB steps only), emulators; `PCE_Soundtest` unread | provisional |
| U7 | Power-on state of VDC, VCE, PSG registers, VRAM, SAT, RAM | MacDonald (MPR/RAM random, SAT garbage, read buffer `$FFFF`) | pick fixed values, option for random |
| U8 | The CD unit: crystal(s), controller timings, what raises IRQ2 via `$1802`, status bits, BRAM behaviour (MAME corrupts), seek times | MacDonald; community schematic; `PCECD_seek` unread | for the add-on's Phase 0 |
| U9 | ADPCM details (`$180D`, nibble addressing, half-IRQ), CD-DA fader and PCM read (`$1805-6`) | MacDonald "currently trying to document"; MAME TODO | undecidable |
| U10 | Arcade Card: the Pro's required BIOS, port semantics | MAME "TODO: same as scdsys?" | emulator source only |
| U11 | The US region check (what exactly is read), which games check | inference from MAME driver behaviour | confirm by disassembly later |
| U12 | Controller signalling: 6-button Avenue Pad, mouse, multitap timing | `PCE_Controller_Info` (unread), MAME devices | read before M1's pads |
| U13 | The expansion video bus and `VCESEL`; any device using them | wiki pinout | none known |
| U14 | SuperGrafx: VPC window edge timing, priority modes, VDC2 IRQ, the compat switch decode | `sgxtech` (tier 2, "much more information in the near future") | for M6 |
| U15 | Detector outliers: Samurai-Ghost, Barbarian (ZX), Death Sword (PC), Mai Nurse, Battle Ace, Gunboat, Madou King Granzort | `tests/detectors/pce-sample-2026-10-23.txt` | lockstep to find the first divergence |
| U16 | Which emulator is closest to hardware per subsystem (CPU, VDC, PSG, CD) | claims only | establish per subsystem as referees are chosen |
| U17 | Python speed of the whole board | extrapolation from famicom-python | measure at M3 |
| U18 | HuCard access times and mirroring of non-power-of-2 images (384K known only from emulators); boards of the 25 unlisted aftermarket images | emulators; running | by running |
| U19 | IRQ sampling cycle, the dot of the vblank flag; Covell: Mednafen's VSync "triggers too late" | tier 1 photo, qualitative | M1 |
| U20 | Block-transfer cycle counts with VRAM/IO targets | Covell X-cycle photos | M1, provisional |
| U21 | Where inside a CPU cycle a device sees the access; where the VDC/VCE stretch cycle goes | Covell photographs (tier 1) | built as "base cycle, access, stretch"; to be placed by the photographs |
| U22 | Dot positions of the VDC's line events (display start, vblank test, line-counter step) | emulators (tier 5) | Mednafen's, in master clocks |
| U23 | Reads of the mirrored half of VRAM | pcetech: "sometimes corrupted" | return 0 |
| U25 | VRAM -> VRAM DMA speed and when it may run | emulators (tier 5): two dots a word; paused during the display | built that way (M2); the CPU side of it is U30 |
| U24 | Delay from the timer's enabling write to its first tick | the prescaler reset is tier 3 (HuC6280 manual 2.7); the delay is not published | one period (MAME, Mednafen) |
| U30 | What a CPU VRAM access does while the SAT or VRAM-to-VRAM DMA runs: does the first access wait, the second, until the end or until the next VDC event, does BSY show | manual and pcetech silent (tier 2-3); Mednafen: first accepted, second held, released at the first VDC event after the end; Mesen2: every MAWR/MARR/VWR write and VRR read waits for a pending access, nothing served during a DMA; MAME: no wait, no BSY | **undecidable**; board: first accepted (BSY), second held to the end, the word served at the end (2026-10-29 fix: a line start no longer serves it); a data read with a fetch pending waits for it (2026-10-29 fix: it returned the old word). [vdc.md](vdc.md), [m5-lockstep-record.md](m5-lockstep-record.md) |
| U31 | When the SAT DMA starts and which phase it needs | manual: "at the beginning of a vertical blanking period"; pcetech: ends 4 lines after the display; Mednafen: when the vertical phase leaves the display *or the vertical sync forces it* (power-up cycling included); Mesen2: at the vblank flag; MAME: at the vblank flag, done 4 lines on | built as Mednafen; **undecidable** (the difference is a fraction of a line) |
| U32 | The VDC's counters before the registers are programmed (power-up display cycling): Mednafen's horizontal machine goes round every 32 dots (HSW 8, HDS, HDW, HDE 8 each) until the first sync, so its vertical phases cycle every ~213 ticks; the board steps once per VCE line | Mednafen logs (patched copy, 2026-10-29); no manual statement | **undecidable**; not built (tried as a switch: the period is right, the phase against the first sync is not reproducible without Mednafen's reset state; After Burner II stops at 187 because its DCR repeat is written while the board is in the VCR phase and Mednafen in the VDS phase) |
| U33 | A window in which a pending VRAM access is not served: Mednafen 16 dots starting 48 dots after the sync begins (`mystery_counter`, vdc.cpp l.538, 635), Mesen2 the first 8 dots of the sync ("test rom result"), board none | emulators (tier 5); a streaming `TIA` to VWR loses 14-17 ticks per line to it (Final Soldier's adopted 907, 3,653 and 4,551 tick waits are three block transfers of 65-262 lines) | **undecidable**; not built (tried: a 48+16 window halves the three waits but the board then runs 15 ticks ahead of Mednafen at the next access, release at the next event) |
| U34 | Status BSY (D6) | manual: "VRAM is being accessed in response to the CPU access"; pcetech: "waiting for a CPU access slot during the active display area" | board: an access is pending; every VDC read value agrees with Mednafen's in the six games (`--check-reads`) |
| U35 | The line position of the overflow and collision flags | emulators (tier 5); manual: overflow also when pattern data cannot be fetched in blanking | board: overflow at the scan, collision at the pixel; no lockstep difference |

**Conflicts** (sources disagree; C-number = the label used in the other documents):

| # | Conflict | Sides | Decision |
| --- | --- | --- | --- |
| C1 | chip names | `pcetech.txt` titles §5 "HuC6260 Video Display Controller" and §6 "HuC6270 Video Color Encoder"; everything else: HuC6270 = VDC, HuC6260 = VCE | the text is right, the **titles are swapped**; cite by function |
| C2 | NMI | MacDonald: "not connected to anything internally nor available on any connector" (tier 2); wiki CPU/EXT BUS pinout: `/NMI` on the expansion port (tier 4) | model NMI as an unconnected socket line; revisit if a device uses it |
| C3 | VCE bit 2 | MacDonald: blur edges; Mednafen, ares, Mesen2: **263 vs 262 lines**; MAME: ignored (commented) | switch both ways; likely one fact (our inference) |
| C4 | the VDC/VCE access penalty | MacDonald: +1 cycle on every VDC and VCE access; ares: only VDC, only outside burst mode; Mednafen: statistical VRAM penalty; MAME: `ST0-2` cost 4+1 | implement MacDonald's, flag it; provisional |
| C5 | dots per line | MacDonald "roughly 342" in 5 MHz mode; 1365 / 4 = 341.25 | a line is 1365 master clocks; dot counts are derived |
| C6 | I/O port D7 polarity | pcetech §4: 1 = CD unit **not** attached; sgxtech: "bit 7 = 1 if a device is connected" | the same author twice; follow pcetech (the wiki's K7 text is silent); verify with the BIOS |
| C7 | VRAM-VRAM DMA over an active period | Hudson manual: remainder is **not** transferred in the next blanking; MacDonald: halted and resumed | decide at M2 by the detectors; manual is tier 3, MacDonald tier 2 | **Decided at M2: resume** (MacDonald tier 2 and Mesen2; `Board(dma_resumes=False)` is the manual's reading); no title of the first ten exercises it |
| C8 | the VCE's modes | Hudson manual: ratios 4 and 3 only, no line bit; MacDonald and all emulators: a divide-by-2 (10 MHz) mode exists | the manual describes the original chip; follow MacDonald |
| C9 | line-counter step pending at the vertical sync | Mednafen drops it; pcetech 5.1's 263-value RCR range needs it | take it (tier 2 over 5) |
| C11 | an interrupt polled one cycle early whose source is gone at entry (`CLI; STZ $1403`) | core issue 0002: the core vectors to IRQ2; Mesen2 drops the timer case and takes the VDC case; After Burner II needs one of them | undecidable here (tier 5); the board runs with the core's default, the experiment is `m2_ours.py --drop-vanished-irq` |
| C10 | multitap read with CLR high after the reset write | pcetech: pad 1's directions; pce-devel port table: 0 | pcetech's, switchable |
| C13-C24 | the PSG's disputed points: R6 data while playing (pcetech ignores, both emulators store), the 45 dB cut-off, the R1/R5 table, the DDA latch, noise NF = 0, LFO needing channel 2, the LFO register 0, the noise shift register running always or only while played, Mednafen's rotating volume latch, key-on (MAME reloads the counter, Mednafen steps the address), LF TRG, Mednafen's averaging at F <= 3 | docs/m4-record.md: the model's defaults follow the manual and pcetech; each referee's way is a named switch that reproduces it with 0 differences on five games | provisional, tier 5 |
| C26 | the wait on a second VRAM access behind a DMA | Mednafen: released at the first VDC event after the DMA ends; Mesen2: at the end, and already at the *first* MAWR/MARR/VWR access after a queued one; MAME: none | board: held to the end of the transfer (U30), provisional |
| C27 | when the SAT DMA starts | Mednafen: display end line step (vertical phase change, or the sync); Mesen2 and MAME: the vblank flag | board: Mednafen's (U31) |
| C28 | the VRAM block window beside the sync | Mednafen 48+16 dots, Mesen2 0+8 dots, board and MAME none | none built (U33) |
| C29 | the overflow flag's time | Mednafen and board: the scan; Mesen2: the next line's HDS; MAME: at the scan only if enabled | board's (U35) |

## Open decisions for Aubrey (each with my recommendation)

1. **Board name and package.** `pcengine-python` / `pcengine_python` (decided). Add-ons: `pcenginecd-python`
   (CD-ROM², Super CD-ROM², Arcade Card) and `supergrafx-python`. *Recommend* these names; not created now.
2. **System scope.** PC Engine NTSC-J first; TurboGrafx-16 a row of the machine table (region bit); no PAL
   machine exists; SuperGrafx and CD in add-ons. *Recommend* this; it covers 93 US + 59 JP listed cards.
3. **NTSC-J only?** Yes for the display (one timing, 263/262 lines); US is the same clocks.
4. **Where the PSG, MMU, timer and IRQ controller live.** MMU, T flag, block moves, speed state and
   interrupt sampling **in the core**; timer, the `$1400` mask/status, the I/O port and I/O buffer **in
   the board** as `cpu_io`; the PSG **in the board** as a package. All with import-boundary tests so that
   if a second consumer appears (a Data East arcade board uses the H6280's timer and IRQ registers) they
   move into a core or their own repository, never copied. Also: **power-up values** deterministic (zeros)
   by default, random on request (U7).
5. **Is CD in scope for the first build?** **No.** First build = M1-M5 (HuCard PC Engine). CD is the next
   board (M7-M8) after the sockets are audited.
6. **Add-on versus mode.** CD-ROM² family: **add-on** (own domains, BIOS, 64 KiB + ADPCM RAM, SCSI-class
   controller; no second CPU, so lighter than Sega CD), with the **Arcade Card in the same repository** as
   its last milestone. SuperGrafx: **add-on, with a measured fallback to a base-board mode** if the
   `PixelPath` socket on the per-line hot path costs more than noise at M3 (the library holds 5 SGX cards;
   the footprint is five sockets).
7. **BIOS handling.** Bring your own, **read in place by path** (`PCE_SYSCARD`, or an argument), never
   committed or copied into the repository: `/data/emu/share/batocera/bios/syscard3.pce` (SHA-1
   `79f5ff55...`, Super CD-ROM² v3.0 Japan) and the No-Intro `[BIOS]` set cover every System Card.
   Evaluate `oss-pce-cd-bios` (open System Card replacement) for CI without Hudson code. *Recommend* both.
8. **Repin pattern.** The CPU core pinned by git revision in `pyproject`/a pin file, repinned deliberately
   per milestone with the gate rerun (as megadrive-python does for its cores); add-ons pin the base board
   by revision and the base tags `pin-N` before an add-on starts; the sockets are audited by each
   add-on's Phase 0 before the base's first tag.
9. **Local until rung N, then public.** *Recommend* local through M5 (the full HuCard sweep with a named
   gate), then public with CI (PyPy only, main + PR, concurrency cancel: Aubrey barely cares about CI
   minutes), like the other boards; boards that embed a BIOS keep it out of the repository either way.
10. **CHD reading for the CD.** Read **bin/cue extracted by `chdman`** (installed, 0.285) in scratch;
    a pure-Python CHD reader needs a FLAC decoder and is a separate piece of work. *Recommend* bin/cue
    first, a CHD reader only if Aubrey wants single-file play.
11. **Colour output.** Expose the 9-bit pixel stream; make RGB a replaceable table (Mesen2's "Default
    (by Kitrinx)" as the default, because it is documented, not because it is right). *Recommend* it.
12. **PC-FX as a possible later consumer.** It uses a HuC6270-family VDC but is beyond the 1990 cutoff;
    recorded only: the VDC stays an instance-based in-board package, broken out (never copied) if PC-FX
    ever comes.
13. **Test programs to build.** The 240p Test Suite PCE source and `PCEngine_TestRoms` need the HuC
    toolchain (pinned, not built). *Recommend* building HuC/PCEAS in M1 only if a milestone needs a
    program the library lacks (a VDC register/IRQ probe), never as a hardware probe pack.
14. **Phase 1 order.** M1 starts with the sockets/fakes and the page table (they gate everything), then the
    timer/IRQ/I-O buffer unit tests from pcetech, then the VDC skeleton and Covell's ROM.

## What was not verified in this phase (candour)

- Nothing was measured on a console; tier 1 is Covell's photographs and nothing else.
- The Python speed estimate is an extrapolation from famicom-python's numbers.
- The `pce.nesdev.org` wiki, Mesen2/Beetle/Geargrafx/ares sources were read for the facts cited, not
  audited; the "Mesen may be the most accurate" claim is the SingleStepTests author's.
- `PCE_Controller_Info`, `PCE_Soundtest`, `PCE_Games_with_Bugs`, `PCECD_seek`, `TG16_Palette` and
  `icc_palettes` are pinned and **unread**; the 240p Test Suite and HuC were not built.
- ares and Mednafen proper were not built; Geargrafx and Mesen2 were run only on a few ROMs.
- MAME's per-register access log could not be made to work (mame-oracle.md trap 1).
- The three-way picture comparison is a crude statistic with a known colour-conversion artefact.

## Decided by the user (Aubrey, 2026-10-23)

All fourteen recommendations above were taken as written, with these three asked
about specifically:

- **Where the timer and IRQ controller live (item 4)**: the board, with
  import-boundary tests, moved out (never copied) if a second consumer such as the
  Data East arcade board is built. The MMU stays in the core, the PSG in the board.
- **SuperGrafx (item 6)**: an add-on (`supergrafx-python`) pinning this board
  through the `PixelPath` socket, with a measured fallback to a base-board mode if
  the socket costs more than noise on the per-line path at M3.
- **CD (items 5, 10)**: out of the first build (M1-M5 are HuCards). CD-ROM² and the
  Arcade Card become one later add-on, `pcenginecd-python`; images are read as
  bin/cue extracted by `chdman` into scratch, and a pure-Python CHD reader is
  built only if single-file play is wanted.

Also taken: bring-your-own BIOS read in place; the pin and repin pattern; local
through M5 then public; the 9-bit pixel stream with a replaceable RGB table;
building HuC/PCEAS only if a milestone needs a program the library lacks. The SF2
card is read in place from the source tree (cartridge.md).
