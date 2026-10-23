# HuCards: the connector, the mappers, and what the library holds

## There is no header

A HuCard is a ROM on the CPU's physical bus: PA20 is its chip enable (so `$00-$7F` banks, 1 MiB),
there is no header to read and **no board identification** other than the image's size and a few
content cues. Aubrey's `.pce` and `.sgx` images carry no copier header either (a 512-byte header
is the only thing to strip: size mod 8192 = 512). This is unlike the SNES, where a header names the
chip: the census below classifies by **MAME's curated software lists** (CRC-32), which name the board
the MAME team gave each card, and says "unlisted" when the lists do not know the image.

The connector gives the card A0-A20, D0-D7, `/RD`, `/WR`, `/IRQ2`, `/CD` (grounded by a card), audio in
(mixed into both channels) and `HSM` (the CPU is in high-speed mode) [doc: wiki "HuCard pinout"].
**Data pin order differs by region** (ascending on the PC Engine, descending on the TurboGrafx-16):
a card converter swaps them, and the dumps in the library are in PC Engine order. US software
checks the I/O port's country bit and does not run on a PC Engine ([memory-map.md](memory-map.md);
measured under MAME).

## Mirroring of smaller ROMs

Two independent sources agree:

- **384 KiB** (`0x60000`): the first 256 KiB fills banks `$00-$3F` twice (mirrored), the last 128 KiB
  fills `$40-$7F` four times. MAME `pce_slot.cpp` `rom_map_setup` (128 KiB blocks: `0 1 0 1 2 2 2 2`);
  Mednafen `pce/huc.cpp` l.413-430 [emu, both].
- **512 KiB**: `$00-$3F` straight, `$40-$7F` = the **upper 256 KiB** mirrored twice (Mednafen l.431-446;
  MAME's generic path "fill remaining blocks with mirrors") [emu]. **256 KiB and smaller**: mirrored
  to fill the 1 MiB window; 192 KiB demos have their own table in MAME. 768 KiB and 1 MiB images:
  see the library below. None of this is stated by Hudson; **tier 3-4**, confirmed only by games
  running (the census images all boot in at least one detector).

## Mappers found in the sources

| Board | Mechanism | In MAME | In Mednafen | In the library |
| --- | --- | --- | --- | --- |
| plain | ROM mirrored as above | `pce_rom` | `HuCRead` | 152 listed (+ 26 unlisted, mostly plain) of 179 |
| **SF2 mapper** (Street Fighter II' Champion Edition, 2.5 MiB) | first 512 KiB fixed at `$00-$3F`; **physical `$080000-$0FFFFF` (banks `$40-$7F`) shows one of 4 further 512 KiB pages**, selected by a write to physical `$001FF0-$001FF3` (low 2 bits of the address) | `pce_sf2`, `bank_w` | `HuCSF2Write` `(A & 0x1FF0) == 0x1FF0`, latch = `A & 0xF` (16 pages: the extended homebrew form, up to 8.5 MiB) | **none** (0 of 179; 1 of 462 in the full No-Intro set) |
| **Populous** | 32 KiB battery RAM at banks `$40-$43`; Mednafen detects the string `POPULOUS` at ROM offset `$1F26` | `pce_populous` | `IsPopulous` | 1 (`Populous (Japan) (En).7z`) |
| **Tennokoe Bank** | four backup-RAM banks on a card at banks `$40-$43` with a lock register at `$0F0000`-range | `pce_tennokoe` | (via BRAM) | 0 (1 in No-Intro) |
| **System Card** (HuCard, 256 KiB) | boot ROM for the CD unit; the Super System Card adds RAM (below) | `pce_cdsys3j/u` | `syscard` | BYOR |
| **Arcade Card** (Pro / Duo) | 2 MiB RAM via ports `$1A00-$1AFF`; Duo: `$80-$87` RAM, MAME marks the Pro's ROM "baddump, TODO same as scdsys?" | `pce_acard_pro/duo` | `arcade_card.cpp` | 3 CD titles need it |
| Mednafen only | **GPS Navi** mapper, **McGenJin** (flash + ADPCM), **Tsushin** (the Tsuushin keyboard + RAM), TED | none | `HuCNaviRead`, `mcgenjin.cpp`, `tsushin.cpp` | 0 known |

## What the library holds (2026-10-23, `scripts/count_carts.py`, read in place)

`/data/emu/roms-retrobat/pcengine/`: **179 HuCards** (`.7z`, one image each; the `By Genre` and `Best
Games` subdirectories are hard links of the same files, so a file count of 184 or 2,981 is wrong);
`supergrafx/`: **5**; `pcenginecd/`: **80 CHDs** (84 directory entries include `gamelist.xml`,
`media`, two folders). The 8 "supergrafx files" of the brief are 5 images + folders + the XML.

| HuCards (179) | | Sizes (179) | |
| --- | ---: | --- | ---: |
| listed in MAME `tg16` (US) | 93 | 256 KiB | 58 |
| listed in MAME `pce` (JP) | 59 | 384 KiB | 33 |
| Populous | 1 | 512 KiB | 64 |
| SF2 mapper | **0** | 1 MiB | 3 |
| unlisted (25 aftermarket/homebrew, 1 US dump of Bonk's Revenge) | 26 | 18 other sizes (72-872 KiB, 4 of them 768 KiB; mostly homebrew) | 18 |

| SuperGrafx (5) | CD (80) | |
| --- | --- | ---: |
| `1941 Counter Attack`, `Aldynes`, `Battle Ace`, `Daimakaimura`, `Madou King Granzort`: all plain cards, 3 x 1 MiB + 2 x 512 KiB | needs the Super System Card (title match to `pcecd.xml`, 29; hash match 9) | 38 |
| | needs the (first) System Card | 26 |
| | needs the **Arcade** System Card | 3 |
| | unlisted | 13 |
| | sizes | 2 under 100 MiB, 78 of 200-799 MiB |

The full No-Intro set on disk (`/data/emu/source/myrient.erista.me/files/No-Intro/NEC - PC Engine -
TurboGrafx-16`, 462 images) has **1 SF2, 1 Populous, 1 Tennokoe, 2 system cards**, 98 x 384 KiB,
156 x 256 KiB, 172 x 512 KiB, 12 x 1 MiB, 13 x 768 KiB and 57 unlisted (mostly Wii U Virtual Console
re-releases); `tests/detectors/census-nointro-pce.txt`. **So the first-build scope for HuCards is
"plain ROM + mirroring", which covers 152 of the 179 library cards (listed) and 400 of the 462 set; Populous
(battery RAM) is the second mapper, SF2 the third.** Unlisted library images are 25 aftermarket
programs (mostly 128 KiB-1 MiB homebrew, several Barbarian ports) whose boards are unknown: they are
tested by running, not classified.

## Interface

A `Card` is socket 1 of [sockets.md](sockets.md): `claims()` over 256-byte pages, `read(address,
mclk)`, `write(address, value, mclk)`; the standard ROM, SF2 (a claim on bank `$00` offset `$1FF0`
plus `$40-$7F` read), Populous and Tennokoe are four `Card`s; so is a System Card and, in the CD
add-on, the Super System Card (which also claims RAM). Cards are **bring-your-own**: the `.gitignore`
refuses `*.pce`, `*.sgx`, `*.chd`, `*.7z`; the board takes a path.
