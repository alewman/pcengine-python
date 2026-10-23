# The HuC6260 VCE: palette, dot clocks, frame length, output

Tiers: **[mfr]** Hudson's *HuC6260 CMOS Video Color Encoder Manual* (13.8 KB of text,
`reference/src/turbografx-mister/docs/`), **[hw]** MacDonald `pcetech.txt` §6-§7 (he titles this
section "HuC6270 - Video Color Encoder": C1), **[doc]** PCEdev wiki (`VCE pinout`, `Timing`),
**[emu]** emulator source, **[fpga]** the TurboGrafx16 MiSTer `rtl/` (a reconstruction).

## What it does

The VCE is a 512 x 9-bit colour RAM + sync generator + DACs. It takes the VDC's 9-bit pixel bus
(VD8 = sprite/background, VD7-VD4 palette block, VD3-VD0 colour) and looks it up: entries
0-255 are the background, 256-511 sprites; **colour 0 of the 15 non-zero palettes in each half
cannot be displayed**. Each entry is `-------GGGRRRBBB`. [mfr, hw]

## Registers (`$FF:0400-07FF`, 8-byte mirror) [hw]

| Addr | Register | Notes |
| --- | --- | --- |
| `$0400` | control (write only) | D0-1 dot clock, D2 below (C3), D7 monochrome |
| `$0402/3` | colour table address (LSB/MSB) | 9 bits; either half writable alone |
| `$0404/5` | colour table data | `$0405` read returns bits 7-1 set; **the address increments after the MSB access** (read or write) and wraps at `$1FF`; writing `$0405` repeatedly changes only the MSB |
| `$0401, $0406, $0407` | unused: read `$FF` | |

**Hudson's manual documents only dot-clock divisions of 4 and 3** (`CR = 00` -> 4, `01` -> 3 "6 fsc /
1.5 fsc, 2 fsc") and says nothing about a divide-by-2 clock or a line-count bit; both come from
MacDonald and the emulators, so the 10 MHz mode and bit 2 are tier 2-3 facts, not manufacturer's.

- **Dot clocks** [hw, doc]: bits 1-0 = 00 5.37 MHz (master/4, 256 px wide games), 01 7.16 MHz
  (master/3, 320), 1x 10.7 MHz (master/2, 512). With bit 0 set at 10 MHz the artefacting at
  character edges is more prominent. A line is 1365 master clocks whatever the mode.
- **Bit 2 and the frame length, conflict C3.** MacDonald: "1 = blur edges of graphics (some games
  use this bit)", noting it looks like every other line is offset half a pixel when clear. Mednafen
  (`pce/vce.cpp` l.711 `lc263 = (V & 0x04)`, `358995` vs `357630` clocks per frame), ares
  (`vdp/vce.cpp` l.30 `io.extraLine = data.bit(2)`) and Mesen2 (`PceVce.cpp` l.62
  `ScanlineCount = (value & 0x04) ? 263 : 262`) all treat it as **263 lines when set, 262 when
  clear**; MAME leaves `m_height = LPF - (m_blur ? 1 : 0)` commented out and always draws 263.
  Likely the same fact seen two ways (alternating 262/263-line frames are what shifts alternate
  fields by half a line), but that reconciliation is **our inference, tier 4**. Which a console does
  at each setting is not published as a capture (U5).
- **Palette flicker / access conflict** [hw]: the colour RAM serves the CPU or the output, the CPU
  first. A CPU access to `$0404/5` during active display makes the VCE show the **previous pixel's
  colour** for as long as the CPU holds it (horizontal streaks; Coryoon's fades), including at the
  borders where the left border takes the previous line's right colour. How many dots a CPU access
  holds is not stated (U4).
- **Monochrome** (bit 7): colour burst off; the grayscale conversion formulas differ between
  emulators (Mesen2 uses `0.299 R + 0.587 G + 0.114 B`) and no source here is a measurement.
- **Extra cycle on CPU access**: [memory-map.md](memory-map.md), C4.
- **Test pins**: grounding `TEST1` makes palette reads return the on-die **YUV ROM** indexed by the
  address (`TEST2` picks the half) [doc: wiki VCE pinout, citing furrtek's dump]: the only published
  way to the composite encoding; not useful to the board, useful to colour-accuracy research.

## Output colours

An emulator frame needs 9-bit-to-RGB. There is **no standard**: Mesen2 ships "Default (by
Kitrinx)" (a composite-looking 512-entry table, `UI/Config/PcEngineConfig.cs`), Mednafen, MAME and
ares each carry their own conversion (not compared here), and pce-devel keeps `TG16_Palette`
and `icc_palettes` ("approximate what the hardware would output for a YUV signal") as research.
Consequence for validation: **compare pictures at the 3-bit-per-channel register values (the
palette index), never at RGB**; `scripts/detectors_compare.py` quantises to 3 bits for this.
The reference board should expose the 9-bit pixel stream and make RGB conversion a replaceable table.

## What the board needs from the VCE model

- the 9-bit pixel stream per line, tagged with the dot clock of each line (it can change mid-frame
  and the width of a line differs, 256/341/512 dots in the Mednafen frame; Mesen2 reports a frame
  divider per row and falls back to 4x scale when rows mix resolutions: `PceDefaultVideoFilter.h`);
- the palette-access conflict as a timing model, provisional (U4);
- line length 262/263 with the C3 reading made a switch the machine table can flip;
- `CK` to the VDC(s): the VDC's counters run from the VCE's dot clock; both SuperGrafx VDCs share it.
