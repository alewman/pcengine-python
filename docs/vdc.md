# The HuC6270 VDC: registers, memory, sprites, DMA, per-line timing, and what is still open

Sources, by tier ([validation.md](validation.md)): **[mfr]** Hudson's *HuC6270 CMOS Video Display
Controller Manual* (`reference/src/turbografx-mister/docs/`, 69 KB of extracted text), **[hw]**
MacDonald's `pcetech.txt` §5-§7 (tested by him on a TurboGrafx-16; note that the file *titles*
the VDC section "HuC6260" and the VCE section "HuC6270": conflict C1), **[doc]** Schleussinger's
`vdcdox.txt` (1998, rev 0.3) and the PCEdev wiki, **[emu]** MAME's `huc6270.cpp`/`huc6260.cpp`
(BSD-3-Clause, read) or a GPL emulator run as a closed box and observed (Mesen2, Beetle PCE,
Mednafen: their source is not read since the clean rewrite of 2026-11-19, [restart.md](restart.md)).

The VDC is a background layer + 64 sprites + sync generator with a 16-bit VRAM interface; it has 20
16-bit registers and addresses up to 128 KiB (64 K words) of VRAM. **The PC Engine has 64 KiB**
(32 K words): the upper half mirrors the lower one; writes to the mirror are ignored, and "sometimes
reading mirrored VRAM returns corrupted data" [hw]. The SuperGrafx has two VDCs with 64 KiB each.

## Bus interface (`$FF:0000-03FF`, 4-byte mirror) [hw, mfr]

`$0` = address register (low 5 bits) when written, **status** when read; `$1` unused (reads 0);
`$2/$3` = data LSB/MSB of the selected register. Valid registers `$00-$02`, `$05-$13`; `$03-$04`,
`$14-$1F` do nothing. A read of the data port with a register other than VRR selected returns the
read buffer.

| Reg | Name | Notes |
| --- | --- | --- |
| `$00` | MAWR | VRAM write address |
| `$01` | MARR | read address; writing the **MSB** loads the read buffer with VRAM[MARR] |
| `$02` | VWR / VRR | write: LSB goes to a latch, the **MSB write commits the word** to MAWR and increments MAWR by the CR increment (1, 32, 64, 128); read: LSB/MSB of the buffer, after the **MSB read** MARR increments and the next word is read into the buffer |
| `$05` | CR | D0 collision IRQ enable, D1 overflow IRQ, D2 raster IRQ, D3 vblank IRQ, D4-5 external sync, D6 sprites, D7 background, D8-9 DISP pin mode, D10 DRAM refresh, D11-12 increment |
| `$06` | RCR | raster compare, 10 bits; counts from `$40` at the first active line; valid `$40-$146`, others never match [hw] |
| `$07/$08` | BXR / BYR | background scroll; BYR's either byte reloads the line's vertical scroll counter, which counts one per line, so a write during the display shows as BYR + 1 on the next line [mfr, emu: MAME]; both are taken 16 dots before the display start (a closed-box fit, U3, provisional) |
| `$09` | MWR | D0-1 VRAM access width (1, 2, 2, 4 cycles), D2-3 sprite access width, D4-6 virtual screen (32/64/128 x 32/64), D7 CG mode |
| `$0A` | HSR | HSW (4-0), HDS (14-8); N-1 coded |
| `$0B` | HDR | HDW (6-0), HDE (14-8) |
| `$0C` | VPR | VSW (4-0), VDS (15-8) |
| `$0D` | VDW | 9 bits |
| `$0E` | VCR | 8 bits |
| `$0F` | DCR | D0 SATB-done IRQ enable, D1 VRAM-DMA-done IRQ enable, D2/D3 source/destination decrement, D4 SATB auto-repeat |
| `$10-$12` | SOUR, DESR, LENR | VRAM-to-VRAM DMA; writing LENR's MSB starts it; the registers **count** during the transfer and keep their end values (LENR ends at `$FFFF`) [hw] |
| `$13` | SATB | source of the sprite-table DMA; writing the MSB arms it |

Status (read `$0`) [hw, mfr]: D6 BSY (the VDC is waiting to service a CPU VRAM access during
active display; "even if BSY is set no interrupt occurs"), D5 VD (vblank), D4 DV (VRAM DMA done),
D3 DS (SATB DMA done), D2 RR (raster), D1 OR (sprite overflow), D0 CR (sprite 0 collision). A status
bit is set only if the matching enable is set; **reading the status clears bits 5-0 and releases
IRQ1**; an unacknowledged IRQ re-enters after every `RTI`.

## Background

Tiles are 8x8, 4 bits per pixel, planar: 32 bytes = words 0-7 hold bitplanes 0/1 of lines 0-7,
words 8-15 bitplanes 2/3. The BAT starts at VRAM word 0; an entry is `ppppnnnnnnnnnnnn` (palette
0-15, name 0-4095; **no flip bits, no priority**). With 64 KiB only names 0-2047 are real; 2048-4095
read garbage [hw]. The BAT wraps if smaller than the display. The background uses VCE entries
0-255. CG mode (MWR D7, only with 4-cycle access) reads planes 0/1 **or** 2/3 and treats the other
pair as zero. [hw]

## Sprites

64 sprites in the SAT (the **sprite attribute table is internal to the VDC**, filled only by the
VRAM-to-SAT DMA; power-up contents are garbage [hw]), four words each: Y (10 bit), X (10 bit),
pattern index + CG bit, flags (vflip, height CGY 16/32/64/64, hflip, width CGX 16/32, priority,
palette). Positions are in a 1024x1024 space, the visible area starts at (32, 64). Patterns are 16x16
(128 bytes: four 16-word bitplane groups); larger sprites mask the low pattern-index bits. Flips
act on the whole sprite. [hw]

Per line [hw, mfr]: during horizontal blanking the VDC scans the SAT from sprite 0 and fills a
**16-entry buffer**; a 32-wide sprite counts as two entries (if one slot remains only the left half
enters). More than 16 (the manual says "17 or more") sets overflow (OR) and drops the rest; the
scan also stops when horizontal blank ends, **so narrow displays lose sprites** (the Image 15-in-1
Collection avoids sprites for this reason; "making the display too wide cuts out multiple ranges":
the rule is unknown, U3). Overflow can fire anywhere in the line, even for off-screen sprites. The
first opaque pixel in buffer order wins; **collision** (CR) when sprite #0's opaque pixel overlaps any
other buffered sprite's, never outside active display. Sprite priority bit = in front of the
background pixel, else only over a transparent one; background priority cannot reorder
sprites (games mask with a low-priority sprite earlier in the SAT).

## DMA

- **VRAM to VRAM**: one word per cycle, source/destination step up or down per DCR, **not** by the CR
  increment; starts on the LENR MSB write; does not touch MAWR/MARR/read buffer/write latch [hw].
  Possible only outside active display or in burst mode. **Conflict C7**: the manual says an
  over-long transfer's remainder is **not** continued in the next blanking period, MacDonald says it
  is halted (not aborted) at the start of active display and resumes after it.
- **VRAM to SAT**: 256 words, armed by the DVSSR MSB write (starts at the next vblank, [mfr]); with
  DSR set it repeats each frame. The done interrupt "always seems to happen four lines after the
  last active line" [hw]; when the transfer starts and how long it takes is not known (U2).
- Both may run at once; priority on a shared range unknown [hw].

## Burst mode

If CR D6 and D7 are both clear **when the next frame starts**, they are locked for the frame: the
VDC does no background or sprite fetches, every active line is colour 0 of sprite palette 0, the
CPU has unlimited VRAM access and VRAM DMA always runs; it only begins at the end of active display
(which is also when SATB DMA happens) and ends the frame after either bit is set [hw, mfr]. Clearing
the bits mid-frame does not enter it. (The wiki and MacDonald's "patent" word is BURST; Hudson's
manual says VD0-7 are low and SPBG high in burst mode.)

## The display, vertically [hw §7]

A frame is **263 lines** (262 with VCE bit 2 clear: C3): 14 top blank, 242 active, 4 bottom blank,
3 sync. The layout is fixed; VDS/VSW/VDW/VCR only place graphics inside it. The *display counter*
equals VSW+VDS when graphics start, runs VDW more lines, then 3 overscan lines plus VCR lines, then
restarts, which is how a mis-set VCR draws the picture twice. The standard 256x224 mode is VDS `$17`,
VSW `$02`, VDW `$DF`, VCR `$0C`. VDS/VSW/VDW/VCR change only outside active display; HSR/HDR may
change on any line. The vblank flag is set on the first line after active display (even if that
line is off-screen) and **at the latest on line 261**; VDW `$1FF` still interrupts there. [hw]

## The display, horizontally, and the per-line memory schedule

A character cycle = 8 dots; the dot clock is master/4, /3 or /2 (5.37, 7.16, 10.7 MHz) from the
VCE ([vce.md](vce.md)); about 342 / 455 / 682 dots per line, some off-screen. Commonly used
settings (HDS/HSW/HDE/HDW/CLK) are tabulated in pcetech §9: 256 wide = `02 02 04 1F 00`, 320 =
`05 02 04 27 01`, 512 = `0B 02 04 3F 02`; the largest viewable pictures are 288/376/536 wide.

During active display the VDC makes one 16-bit VRAM access per dot clock in 8-dot cycles, divided
by MWR D1-0 (**[hw] table, mode 0, the one games use**): CPU, BAT, CPU, (unknown), CPU, CG0, CPU,
CG1; modes 1/2: BAT, CPU, CG0, CG1 (each over two dots); mode 3 (4 cycles per access): BAT then
CG0/CG1. So in mode 0 the CPU gets 4 of 8 slots; the status-port BSY bit is set when it must wait.
Sprite pattern words are fetched in blanking (SM = 1, 2 or 4 cycles per word group: manual table).

**No source here settles the CPU-visible schedule exactly (U1).** Mednafen, the long-standing
reference, is known (from its documentation and its observed timing, C4) to approximate it with a
statistical penalty rather than a slot model [emu]. The TurboGrafx16
MiSTer authors' `docs/logs 42.95MHz/VDC rendering.png` and `VDC sprite DMA.png` show
the slot schedule per 5/7/10 MHz mode (BG tile fetch: CPU, BAT, CPU, -, CPU, CG0, CPU, CG1; sprite
fetch SP0-SP3 per sprite; sprite DMA in the 5 MHz mode stepping the VRAM address every few dots; read off the picture, not verified) but the
signals include internal counters (`H_CNT`, `V_CNT`), so they are an **FPGA core's own capture**, not
a logic-analyser trace of a console: emulator-derived tier. (The "5/10/16-cycle" sprite timing in
the brief for this phase was not found as a named quantity anywhere; the SM = 1/2/4 table above is
the nearest published fact.)

## Output

9 bits per dot to the VCE: 4 pixel + 4 palette + 1 sprite/background (SPBG) bit; pixel 0 is
transparent. The VDC picks background vs sprite colour itself (the SuperGrafx's VPC can only reorder
what it receives: [sockets.md](sockets.md)). Outside the active area and when both layers are off the
**overscan colour (sprite palette 0, colour 0)** shows; inside, the **backdrop (background palette 0,
colour 0)**. Colour 0 of the other 15 palettes cannot be shown [hw].

## As built (M2)

The background, both DMAs and burst mode are built: [m2-record.md](m2-record.md) holds the
decisions (C7 resumes) and the pictures that judge them. The board draws a line when its display
width begins. Since the clean rewrite (2026-11-19, [restart.md](restart.md)) the line machine is
the one described in `vdc/sequencer.py`'s docstring: the line step at the end of the horizontal
sync, the display (HDS + 1) characters later, the vertical periods VSW + 1, VDS + 2, VDW + 1 and
VCR + 3 lines, RCR compared as the sync falls, the scroll taken 16 dots before the display
starts (fitted), the SAT transfer holding the VRAM three lines.

## What the board must model, and at what grain

- Per **character cycle (8 dots)** is the natural grid for the CPU window and the BAT/CG/sprite
  fetches; the line events are few (the sync's fall, its end, the display start, the vertical
  blanking's dot), so the board runs the VDC on a handful of dot-granular line events and computes
  the fetch schedule inside them.
- The first milestone with a VDC (M1) only needs timing, the status/IRQ lines and VRAM port; M2
  adds BAT/CG rendering; M3 sprites; **sprite and DMA timing details stay provisional (tier 4) until a
  tier 1-2 source is found** (they are marked undecidable without hardware, per the no-hardware rule).
- Instances, not module state: the SuperGrafx has two, PC-FX (post-1990, a possible later second
  consumer: it uses a HuC6270-family VDC) would pin this one.

## CPU accesses behind a DMA, and the status flags: what each source says (2026-10-29)

Done for the lockstep stops of [m5-lockstep-record.md](m5-lockstep-record.md); entries U30-U33 and
C26-C29 in the [brief](handoff-brief.md). Nothing here is decided by a tier 1-3 source; the board's
rule is stated first, then each source.

**A. What a CPU VRAM access does while the sprite-table (SATB) or VRAM-to-VRAM DMA runs.**

- *Board (as built)*: the first data access is accepted and BSY is set; the word is **served when the
  transfer ends**, never earlier (since 2026-10-29: the display-width event used to serve it at the
  next line start, which dropped BSY in the middle of the transfer; Bonk's Adventure, test
  `test_a_waiting_cpu_write_stays_busy_across_line_starts_until_the_satb_dma_ends`); a *second* data
  access (VWR or VRR MSB, MARR MSB) holds the CPU until then. A data-port read while a read is still pending (after a MARR write
  or an MSB read of VRR: the word waits for a CPU slot or a transfer) holds the CPU until the word
  is in the buffer (2026-10-29: it used to return the previous word; both emulators wait, the
  manual's read sequence implies it; `test_a_data_read_waits_for_the_word_a_pending_fetch_has_not_loaded_yet`).
- *Hudson manual (tier 3)*: silent on the CPU while a transfer runs. It says the SATB transfer is
  "256 words ... at the beginning of a vertical blanking period", and for BSY: "the VRAM is being
  accessed (read or written) in response to the CPU access".
- *pcetech (tier 2)*: silent too: "Both VRAM to VRAM DMA and VRAM to SAT DMA can run at the same
  time", "VRAM to VRAM DMA can only occur outside of the active display period"; BSY: "waiting for a
  CPU access slot during the active display area" (5, status) and "waiting to read or write data
  requested by the CPU when it accesses VRR/VWR".
- *Mednafen* (behaviour learned from its source before 2026-11-19, a fact kept with no code, and
  the lockstep's trace): the first access is left pending
  (BSY) and the CPU is not held; the next VWR MSB write, and every data-port read while BSY, hold
  it until the access is served, and the CPU is released at the first VDC or VCE event after the
  transfer's end rather than at the end itself: After Burner II's loop is held 1,940 master clocks
  for a transfer that ends 1,365 clocks after it starts (traced: transfer start at 119,222,
  release at 121,175). Very long waits within a frame are observed to end with the transfer
  complete and no time charged.
- *Mesen2* (behaviour learned from its source before 2026-11-19, kept as a fact): every access waits while either transfer
  runs, and a write to MAWR, MARR or VWR (LSB included) or a VRR read first waits for the pending
  access; after a queued access BSY stays visible for a few VDC clocks even in blanking.
- *MAME* (`huc6270.cpp`, BSD-3, read): no CPU wait, BSY is never set, the VRAM DMA is done at once
  (its own note: "the timing for this is incorrect") and the SATB copy happens with the vblank
  flag.

**A2. The display keeps running while the CPU waits (issue 0004, 2026-11-13).** The hold is the
VDC's `/BUSY` output on the CPU's `RDY` [wiki: VDC pinout, tier 4]: it stops the CPU, nothing else.
The VDC's line and frame come from the VCE's `/HSYN` and `/VSYN` [wiki: VCE and VDC pinouts], and no
source has the VCE wait for the CPU. So a wait that spans the start of the display period meets it,
and C7 applies to the transfer as to any other. Hudson's manual (tier 3) says the display start
cancels it ("no End Detect status", the remainder "will not be transferred"); MacDonald (tier 2) says
it is halted and resumes. Both emulators are observed to run the rest of the machine through the
wait (their display keeps its lines while the CPU is held). The
board used to run only the waiting VDC to the transfer's end, lines ahead of the board's line clock,
so a waited-on transfer always completed as if the display never started and `dma_resumes` changed
nothing for it. Now the board runs every device, the line clock included, event by event until the
access is served (`Board._serve_vram`): with the default the CPU stays held through the display
period until the paused transfer ends after it; with `dma_resumes=False` the display start cancels the
remainder and serves the access there (tests `test_a_cpu_waiting_on_a_dma_*`). How long the real
chip holds the CPU is still U30/C26.

**B. When the status bits are set.**

| Bit | Board (since 2026-11-19) | Mednafen / Beetle (learned before 2026-11-19) | Mesen2 (the same) | MAME (read) |
| --- | --- | --- | --- | --- |
| BSY | an access is pending (slot wait in the display, a DMA, never otherwise) | pending behind a DMA, and in a short window of each line (U33) | pending, including a few clocks after each access | never |
| VD | first line after the display, `vblank_dots` after the line step (U19) | the display start of that line | the display start of that line | at the line step that ends the display |
| DS | three lines after the vertical blanking begins [hw: pcetech 5.4] | about three lines at 5 MHz | about three lines at 5 MHz | 4 lines after the vblank flag |
| DV | 2 dots a word at VM 0 [mfr: MWR VM] | 2 dots a word | 2 dots a word | at once |
| OR | at the line step, for the line; also when the manual's fetch budget is short | at the scan for the next line | at the next line's display start | at the sprite scan, only if enabled |
| CR | when the beam reaches the colliding pixel (U35) | as the line is drawn | at the pixel | at the pixel |
| clear | reading the status clears bits 5-0, not BSY | same | same | same |

The lockstep compares every VDC and VCE read value with the ones Mednafen logged
(`scripts/lockstep.py --check-reads`): in all six games every read, status values and BSY and the
read buffer included, agrees up to the game's stop. The manual's other overflow causes ("some sprite
pattern data cannot be fetched ... during a horizontal blanking period", "the CGX of some sprites")
are the fetch budget of the manual's table (2.4.1 (6)), which `Vdc.fetch_sprites` applies since
2026-11-19: entries searched by HDW, patterns fetched by HDE + HSW + HDS and SM.
