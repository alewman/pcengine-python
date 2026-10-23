# Validation: every oracle, its tier, what ran here

Tiers, highest first: **1 hardware-captured** (a published capture or photograph of a real
console) > **2 hardware-verified** (a person's tests on a real console, published as text) >
**3 manufacturer** (Hudson/NEC documents) > **4 research** (community documents, schematics,
pinouts) > **5 emulator-derived** (including FPGA cores: a reconstruction, not a die). A low tier
is a detector, never a judge. Aubrey has **no hardware and no capture rig**: nothing in this
project needs a console, and every question the sources leave open is marked undecidable
([handoff-brief.md](handoff-brief.md): U-list).

## Tier 1: hardware-captured

| Source | Pin | What it gives | Limits |
| --- | --- | --- | --- |
| **Chris Covell, PC-Engine CPU Timing Test** (`CPU_Test_10.pce`, 32 KiB, with 57 photographs/captures in the zip) | `tests/test_roms/CPU_Test.zip`, `http://www.chrismcovell.com/data/CPU_Test.zip`, sha256 `db65a32d...`; explanation page `reference/docs/covell-cpu-test.html` | A visual test: every scanline starts with a background-colour change and a single instruction loops until the beam wraps a line later, so **a correct cycle count draws a vertical split**. The zip shows the real console (a flash card in a PC Engine; later through an SSDS3 menu cart), a MiSTer core and Mednafen side by side for the 2-8 cycle groups, "X-cycle" block transfers (including VRAM block moves) and ROM vs RAM. Source (`source/*.asm`, HuC/PCEAS-style) is included | Photographs, not numbers: we read split positions off the images. Covell warns the result changes with **how the VDC "awakened" at power-up** (menu carts that initialise the VDC change VRAM-transfer timing) and that Mednafen's CPU timing matches the hardware but "its VSync interrupt triggers too late" |

That is the **only** tier-1 source found. (The search was a few web queries plus the references of
the pinned repositories: not exhaustive. No logic-analyser or die-level data for the HuC6270, HuC6260
or HuC6280 turned up; furrtek's YUV-ROM dump is cited by the PCEdev wiki and was not fetched.)

## Tier 2: hardware-verified research (author's tests, no captures)

| Source | Pin | Notes |
| --- | --- | --- |
| **Charles MacDonald, `pcetech.txt`** (2001-02) | `reference/docs/pcetech.txt`, sha256 `ce6e4325...` (Wayback of cgfm2.emuviews.com) | "Everything within has been tested and verified on a TurboGrafx-16 console ... my testing methods or interpretations ... could be flawed." CPU, timer, memory map, I/O port, VDC (§5), VCE (§6), CD (§8), PSG (§10). **Names the VDC "HuC6260" and the VCE "HuC6270" in its headings (C1)** |
| **MacDonald, `sgxtech.txt`** (2003-04) | `reference/docs/sgxtech.txt`, sha256 in `pinned_files.json` | "Most everything within has been tested and verified on a SuperGrafx console": memory map, I/O, connectors, the VPC |

Tier 2 is a single careful author; where two of his statements disagree (C6) or he contradicts a
manufacturer document (C7) it is recorded, not resolved.

## Tier 3: manufacturer

All from the TurboGrafx16 MiSTer repository's `docs/` (pinned `827d45f4`), scans/OCR of Hudson and
NEC documents: **HuC6270 VDC manual**, **HuC6260 VCE manual**, **HuC6280 hardware manual**, **HuC6280
software manual**, **HuC6280 PSG manual**, *Hu7 CD System* BIOS / Software / PSG-driver manuals, and the
**TurboGrafx-16 unit service manual** (NEC). OCR quality is poor (tables and register diagrams come out
broken) and the manuals describe the original chips: the VCE manual knows only dot-clock ratios 4 and 3
and no line-count bit ([vce.md](vce.md)); the VDC manual is silent on CPU slot timing beyond a
table. They are the judge for "what a register is for"; they are **not** a timing source.

## Tier 4: research

| Source | Pin | Note |
| --- | --- | --- |
| PCEdev wiki (pce.nesdev.org): memory map, pinouts, timing, 9 pages | `reference/docs/pcedev-wiki/` (live; hashes pinned) | community; one page carries spam; contradicts MacDonald on NMI (C2) |
| Schleussinger `vdcdox.txt` (rev 0.3, 1998), Bock's HuC6280 page, Videoman's docs | MiSTer `docs/` | old, partly superseded |
| "CD Unit SCH.pdf" | MiSTer `docs/` | **an Altium redraw dated 2020-06 titled "New Output"**: a community reverse-engineered schematic, not NEC's (metadata read with `pdfinfo`); useful as a netlist-level guide to the CD unit |
| `Super CD-ROM2 System V3.00 (J).ASM` | MiSTer `docs/` | a commented disassembly of the BIOS; community |
| pce-devel: `PCE_Controller_Info`, `PCE_Soundtest`, `PCE_Games_with_Bugs`, `PCECD_seek`, `TG16_Palette`, `icc_palettes` | `reference/src/*` | measurements and tests by the community; provenance per repository, **not read in this phase** except as listed |
| 240p Test Suite source (PCE: HuCard, CD, SCD) | `reference/src/240pTestSuite` | needs the HuC toolchain (`reference/src/huc`) to build; no stable URL for prebuilt ROMs; not built |

## Tier 5: emulator-derived (detectors)

| Emulator | Pin | Runs here headless? | Notes |
| --- | --- | --- | --- |
| **MAME 0.285** | `/usr/games/mame`, tag `mame0285` | **Yes**, no ROM set needed | [mame-oracle.md](mame-oracle.md); instruction trace; no register log; weak CD |
| **Mesen2 2.1.1** | `b9fa69dd` (sparse `Core/PCE`); `MesenCore.so` built by famicom-python | **Yes** through `scripts/mesen_run.py` (ctypes), after setting `PcEngineConfig` (below) | SingleStepTests' author calls Mesen "maybe the most accurate HuC6280 emulator ... passes timing tests other emulators don't. It needs more research" (README, quoted, unverified by us) |
| **Beetle PCE** (Mednafen's PCE core as libretro) | `b96c11e0`, built with `make` in 22 s (`mednafen_pce_libretro.so`) | **Yes** through `scripts/libretro_run.py` (ctypes libretro host, no SDL) | the long-standing accuracy reference by reputation; its VDC CPU-window is an **admitted approximation** (`vdc.cpp` l.1343-1352: "Assume a 50% hit rate on missing the CPU window") |
| **Geargrafx** | `57c257dd`, `make` in `platforms/libretro` (23 s) | **Yes**, same host | PCE/SGX/CD with a debugger |
| **mednafenPceDev** (Mednafen proper, pce-devel's fork) | `55dba394` | **Not built.** Mednafen drives SDL; no headless mode was found. Beetle PCE is the same core family and runs | |
| **ares** | `c76aaffa` (sparse `ares/pce`) | **Not built** (the full tree and its dependencies are large) | readable: per-cycle CPU, VDC `penalty cycle` only when not burst (C4) |
| **TurboGrafx16 MiSTer** `rtl/` | `827d45f4` | not runnable here (FPGA); its authors' `docs/logs 42.95MHz/*.png` are signal captures **of the FPGA core** (internal `H_CNT`/`V_CNT` appear): tier 5 | the Covell page reports this core running ROM code too fast |
| **SingleStepTests/huc6280** | `4ce378e0`, README only (the data is 185 MB) | not run: the CPU core's concern | "Mesen-generated": **emulator-derived, so a check that the core matches Mesen, not hardware**; it treats RAM as a flat 2 MiB with only MPR translation |

### Driving Mesen2 headless: two traps (found 2026-10-23)

The snes-python recipe returns **all-black frames** for PC Engine games:

1. The DLL has **no default palette**: Mesen2's UI sets `PcEngineConfig.Palette[512]`
   (`PceDefaultVideoFilter::InitLookupTable` reads it) and the headless DLL never does.
2. At maximum speed the PCE core **skips rendering frames** (`PceVpc::ProcessStartFrame`: speed 0 or
   >150 and <10 ms since the last render) unless `DisableFrameSkipping`.

`scripts/mesen_run.py` calls `SetPcEngineConfig` with the 8,080-byte struct built by hand (offsets
measured by compiling `offsetof` against the pinned header: `Palette` at 6032, `DisableFrameSkipping` at
6014, `RamPowerOnState` at 5968 set to all-zero for determinism, volumes 100). The frame size is 292 x 242
for the CPU test (the core reports a per-row clock divider and picks the width; `--width` overrides).

### Detectors against each other (`scripts/detectors_compare.py`, 2026-10-23)

35 library cards (every 6th PCE/TG16 title + the 5 SuperGrafx cards), 5 s each; the three pictures have
different geometry so only two crude statistics are given (colour-histogram distance `tv` at 3 bits per
channel, and the share of rows whose dominant colour agrees at the best vertical offset). Results in
`tests/detectors/pce-sample-2026-10-23.txt`.

- All 35 start and draw under all three. For 28 of 35 cards the rows agree (every pair >= 0.95) and
  MAME's colour mix is within 0.08 of both others.
- **The `tv` between Mesen2 and Beetle sits at 0.10-0.12 on 14 cards whose rows agree at 1.00**: a
  systematic colour-conversion artefact (Beetle delivers RGB565, Mesen2 got our linear 9-bit table;
  rounding to 3 bits differs), so `tv` between those two is **not meaningful at this precision**. Use
  `rows` for them and `tv` only against MAME (also RGB converted by MAME's own table: the same caveat
  applies in weaker form). Quantising through each emulator's own palette would remove it: not done.
- **Outliers on `rows` (research questions, not verdicts)**: `Samurai-Ghost (USA)` (0.63 / 0.68 / 0.29
  for MAME-Mesen2 / MAME-Beetle / Mesen2-Beetle), `Barbarian (ZX Spectrum port)` (MAME `tv` 0.49-0.56
  against 0.07 between the others), `Death Sword (PC port)`, `Mai Nurse`, `Battle Ace` (SuperGrafx),
  `Gunboat`, `Madou King Granzort` (rows 0.83-0.91 in some pair). Whether the games are simply at
  different moments after power-on (5 s of MAME vs 300 frames of the others) or the emulators differ
  was **not** established: these are the cards to examine with frame-by-frame lockstep.
- **The offset between MAME and the other two is about 5 rows** on typical games, 0 between Mesen2 and
  Beetle (a measurement of where each tool starts its picture).
- On the CPU test MAME draws grey stripes where the **hardware photographs** and Mesen2, Beetle and
  Geargrafx draw magenta and black. Three emulators agree with the photographs; MAME does not.

## Judges by milestone

In [handoff-brief.md](handoff-brief.md) "Milestones". Order of authority for a disputed behaviour:
(1) Covell's photographs, where a test covers it; (2) MacDonald's tests (and sgxtech); (3) Hudson's
manuals, for what a register is for; (4) two or more detectors agreeing; (5) one detector. A result
decided at level (4) or below is recorded as "provisional, tier 5" in the certification record.

## Local romsets (read in place, never copied)

- `/data/emu/roms-retrobat/pcengine/`: 179 `.7z` HuCards (+ `By Genre`, `Best Games` hard-link
  folders, `gamelist.xml`, `media`); `supergrafx/`: 5; `pcenginecd/`: 80 `.chd`.
- `/data/emu/source/myrient.erista.me/files/No-Intro/NEC - PC Engine - TurboGrafx-16/`: 462 images
  (includes `[BIOS]` System Cards); `... SuperGrafx/`: 5; `Redump/NEC - PC Engine CD & TurboGrafx CD/`:
  551 entries; `MAME/ROMs (non-merged)/`: none needed for `pce`.
- `/data/emu/share/batocera/bios/syscard3.pce` (Super CD-ROM² v3.0, SHA-1 `79f5ff55...`).

## What is not available

No die-level model or logic-analyser capture of any PC Engine chip was found; no hardware audio recording
of the PSG; no published test ROM for the VDC's sprite/DMA timing beyond Covell's CPU test (the
`rgalland/PCEngine_TestRoms` sources, "BG sizes, latching, sprite", have no captured results);
`PCE_Soundtest` and the controller notes were not evaluated. The 240p Test Suite is a video pattern
suite with no machine-readable pass criteria.
