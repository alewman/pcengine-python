# CD-ROM², Super CD-ROM², the Arcade Card (a brief, for the add-on board)

> **A planning brief, kept as written (2026-10-23).** The add-on it plans is built:
> [pcenginecd-python](https://github.com/alewman/pcenginecd-python) (CD unit, ADPCM, Arcade Card),
> whose own records say what was found; where they differ from this brief, they are right.

Scope of this document: enough to plan `pcenginecd-python` and to
say what the base board must expose ([sockets.md](sockets.md)). The base board does
**not** include the CD. Tiers as in [validation.md](validation.md).

## What the hardware is

A CD-ROM² set is a base unit (the IFU-30 interface tray that plugs into the console's EXT BUS [hw: sgxtech],
plus the drive), a **System Card** (a HuCard holding the BIOS) and an optional Arcade Card.
The Duo/R/RX consoles integrate them. [hw: pcetech §8]

| Item | Fact | Source |
| --- | --- | --- |
| RAM | 64 KiB CD RAM at banks `$80-$87` (physical `$100000-$10FFFF`); the **Super System Card adds 192 KiB at `$68-$7F`**, 256 KiB in total | hw: pcetech §8, §8.1; emu: MAME `pce.cpp` |
| ADPCM RAM | 64 KiB, separate, reached through `$180A` with independent read and write pointers; nibble-addressed | hw: pcetech §8 |
| Backup RAM | 2 KiB at `$1EE000-$1EE7FF`, **locked at power-up** (reads `$FF`, writes ignored); a write with bit 7 set to `$1807` unlocks, a read of `$1803` locks; the System Card and Tennokoe Bank access it at low speed only | hw: pcetech §8 |
| Drive | a stand-alone single-speed CD drive; the controller is SCSI-compatible: `00` TEST UNIT READY, `03` REQUEST SENSE, `08` READ (LBA, 2048-byte blocks), vendor `D8/D9` play, `DA` pause, `DD` read Q, `DE` DINFO; MSF arguments in BCD | hw: pcetech §8 |
| Data path | a byte at a time through `$1801`/`$1808`; **no DMA to RAM**; DMA only one sector at a time into ADPCM RAM (AD_TRANS, AD_CPLAY) | hw |
| Registers | `$1800` status, `$1801` command/data, `$1802` control (writing values caused an IRQ2 in tests; which ones is unknown), `$1803` BRAM lock/status (bit 4 = play button, bit 2 = ADPCM half-empty), `$1804` bit 2 = reset the CD hardware, `$1805-6` CD-DA sample read (format unknown), `$1807` BRAM unlock, `$1808-9` ADPCM address, `$180A` data, `$180B` DMA control, `$180C` status, `$180D` address control, `$180E` playback rate `32 / (16 - n)` kHz, `$180F` fade timer (CD-DA: `8-9` fade ~8 s, `C-D` ~2 s) | hw: pcetech §8 |
| IRQ | the CD interface and ADPCM raise **IRQ2** | hw: pcetech §2.1 |
| ADPCM chip | an Oki MSM5205 in the schematic and in MAME (`1/48` prescaler, 4-bit); MAME clocks it from a 9.216 MHz `PCE_CD_CLOCK` / 6 | doc: community schematic (below); emu: `nec/pce_cd.cpp` |
| Arcade Card | 2 MiB RAM behind four 16-byte port groups `$1A00-$1AFF` (MAME: `m_port[(offset & 0x30) >> 4]`); the **Duo** version also decodes `$80-$87` as RAM; MAME's `pce.xml` marks the Pro's BIOS "baddump, TODO: same as scdsys?" | emu: `bus/pce/pce_acard.cpp`, `hash/pce.xml` |

## The System Card (BIOS)

The BIOS is a HuCard image (`syscard3.pce`, 256 KiB, Super CD-ROM² System v3.0 (Japan), SHA-1
`79f5ff55dd10187c7fd7b8daab0b3ffbd1f56a2c`, the same hash MAME's software list gives
`scdsys`). It is **bring-your-own**: found read-only in Aubrey's tree at
`/data/emu/share/batocera/bios/syscard3.pce` (also `/data/emu/images/x55/bios/`, and inside
`/data/emu/source/bios/PACK FULL BIOS BATOCERA ... .zip`), and every revision is in the No-Intro
set (`[BIOS] CD-ROM System (Japan) (En) (v1.0 / v2.0 / v2.1)`, `Super CD-ROM System (v3.0)`,
`TurboGrafx CD System Card (USA) (v2.0)`, `... Super System Card (USA) (v3.0)`, two Games Express
cards). It was copied to a scratch directory for the runs below and never into the repository.
**An open System Card replacement exists** (`mao2009/oss-pce-cd-bios`, last pushed 2026-10-23, pinned, not
evaluated: licence and maturity unknown) and could let CI run a CD without Hudson
code.

The BIOS entry points (`CD_BOOT $E0F3`, `CD_RESET`, `CD_READ`, `AD_TRANS`, ... a jump table at
`$E000`) are documented in Hudson's *Hu7 CD System BIOS/Software Manual* and in a community
commented disassembly (`Super CD-ROM2 System V3.00 (J).ASM`, derived from the ROM: read, never copied).
The Super System Card's `EX_MEMOPEN` reads registers `$18C1-$18C6` for identification
(`$18C5 == $55 && $18C6 == $AA`, or `$18C1 == $AA && $18C2 == $55` with `$18C3` as version) [hw:
pcetech §8.1].

## What runs here (2026-10-23, what ran, not what might)

| Emulator | CD result with `syscard3.pce` + `Bonk III - Bonk's Big Adventure (USA).chd` |
| --- | --- |
| Beetle PCE (Mednafen core, libretro host, `scripts/libretro_run.py`) | boots the **Super CD-ROM² System ver 3.00** screen; 4,800 frames (80 s) in 6.6 s wall; no "PUSH RUN BUTTON" text visible at that moment (no input is sent) |
| Geargrafx (libretro host) | same screen at 3,000 frames |
| MAME 0.285 `pce -cart syscard3.pce -cdrom X.chd` | boots, screen shows **"PUSH RUN BUTTON!"** at 60 s emulated (16 s wall) |
| Mesen2 | not tried on a CD |

No game was played to its title. MAME's own source says the CD is its weakest part: `pce_cd.cpp`
lists as TODO "rewrite SCSI", "verify CD read timing for edge cases marked in pcecd.xml with [SCSI]",
"ADPCM half events aren't honored (dbz, draculax)", "BRAM is unsafe on prolonged use ... tend to
corrupt itself when 8 saves are already in", "**Fader feature is sketchy and unchecked against real
HW**", "Audio CD player ... rewind/fast forward don't work properly". **Use MAME as a detector for
the instruction stream and register order only; the CD timing and audio have no referee yet** (U8,
U9). Which of Mednafen, Geargrafx and Mesen2 is closest to hardware for the CD is not established.

## Media and tooling

80 CHDs (CHD v5, CD LZMA/Deflate/FLAC compressed, hunk size 19,584 = 8 raw sectors of 2,448 bytes),
200-800 MiB each when expanded; `chdman` 0.285 is installed (`info`, `extractcd` to bin/cue). The
CHD header's SHA-1 matches MAME's `pcecd.xml` for only 9 of 80 (Aubrey's CHDs are repacked), so
discs are identified by title: 38 need the Super System Card (29 by title, 9 by hash), 26 the first
System Card, **3 the Arcade System Card**, 13 unknown ([cartridge.md](cartridge.md)). For the
board: read bin/cue extracted by `chdman` in the scratch area first; a pure-Python CHD reader needs a
FLAC decoder (not in the standard library) and is an open decision (8).

## Sockets this add-on exercises (summary; the table is in sockets.md)

Claims for `$80-$87`, `$F7`, `$FF:1800-$1FFF` and (Super System Card, from the **card slot**) `$68-$7F`
and `$18C1-$18C6`; IRQ2; I/O bit 7; the audio list (CD-DA at 44.1 kHz, ADPCM, with the fader);
`catch_up` for the drive and ADPCM clock; reset by register. **There is no second CPU**: the
drive's microcontroller is not emulated (the SCSI controller is a state machine in MAME, Mednafen and
Geargrafx), so none of the Sega CD's hardest sockets recur.

## Milestones (add-on) and judges

CD-1 boot to the System Card screen (judge: the BIOS executing, plus detector screens); CD-2 read
a data track, `CD_READ` (judge: the BIOS's own sector checks, Hudson BIOS manual); CD-3 first game
past its title (detector lockstep); CD-4 CD-DA + fader (no referee: undecidable, labelled
provisional); CD-5 ADPCM (detector audio only); CD-6 Arcade Card (3 library discs; the Duo/Pro
BIOS question U10 must be answered first).
