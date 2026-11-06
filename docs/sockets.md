# Sockets: how CD-ROM², Super CD-ROM², the Arcade Card and the SuperGrafx plug into this board

Aubrey's shape rule (2026-10-23): follow the Sega console pattern. `pcengine-python` is the **base
board with documented sockets**; the CD family and (probably) the SuperGrafx are **separate
add-on boards** that pin it by git revision and nothing is copied: `pcenginecd-python` and
`supergrafx-python` (working names; `supergrafx-python` was created on 2026-11-05, local, see
[m6-status.md](m6-status.md); `pcenginecd-python` is **not created**). The pattern was read, read-only,
from `megadrive-python/docs/expansion-sockets.md` (nine sockets, built on branch
`expansion-sockets`, merged as PR #6 with 0 sweep rows moved), `segacd-python/docs/sockets.md` and
`sega32x-python/docs/handoff-brief.md`.

## What the Sega socket list teaches

The Mega Drive's sockets were designed *after* the board, then audited by both add-on Phase 0s,
which found the first draft short in six places. Each finding is a design rule here, from day one:

| Sega finding | Rule for this board |
| --- | --- |
| Claims are **address ranges**, not "a top byte": the `$A1` page is shared by five devices | Claims are **256-byte pages over the whole 21-bit space** (8192 pages); the hardware page `$FF` is shared by eight devices |
| "No cartridge" is a real state (`Cartridge(b"")` is not an empty slot): the RAM cart and `/CART` sense depend on it | An empty HuCard slot is a state: it answers `$FF`, **does not** ground `/CD`, and the I/O port's CD-sense bit follows the **expansion port** |
| Port/slot accesses must **carry their master-clock time**; a device runs itself up to it **inside** the access (the CD's gate array registers must see the sub-CPU at that clock) | Every claimed access is `read(address, mclk)` / `write(address, value, mclk)`; a device's `catch_up(mclk)` is callable inside an access |
| **One decode for every bus master**; three Z80 paths and the VDP DMA bypassed the sockets | One decode serves the CPU's data and fetch accesses, `ST0-ST2`, block transfers, the debugger's peek and the lockstep probe. There is **no second bus master** on a PC Engine (VDC DMA is VRAM-to-VRAM, CD-to-ADPCM DMA is inside the CD unit), so this is easier than Sega |
| Interrupt socket **dropped** (neither add-on interrupts the main CPU); `max()` was the wrong model | **The opposite here**: the CD unit and HuCards *do* interrupt the main CPU, on IRQ2 (and the VDC on IRQ1, a second VDC on the same line). Interrupt lines are **per-source levels**, wired-OR, never a max |
| Video timing and picture sockets needed by the 32X | Needed by the SuperGrafx: its VPC sits **between the VDC pixel bus and the VCE** |
| Sound: a list of sources, each with a **changeable rate** and gain; the FM and PSG were left out of the list to keep a bit-exact gate | The PSG is **board-owned and in the list from the start** (no bit-exact legacy to protect); the CD adds CD-DA (44.1 kHz) and ADPCM (variable) |
| Reset: three events (power, button, instruction); the CD is reset only at power-on | The PC Engine has no reset button and no reset instruction; the CD unit is reset by a **register write** (`$1804` bit 2), inside the add-on. Kinds: `POWER_ON` and `BUTTON` (Duo/Shuttle-class consoles; unverified) |
| The gate: with nothing attached the board is byte-for-byte unchanged (lockstep replays, 0 sweep rows moved) | The base board's gate is defined **before** any add-on: the lockstep traces and the sweep are recorded standalone; an add-on may not change them |
| The core lacked a bus cycle that waits for `/DTACK` (the sub-CPU), found late | The only waiter here is the CPU itself: the VDC's `/BUSY` is wired to the CPU's **RDY** [doc: wiki VDC/CPU pinouts]. The board holds the clock; the core needs no wait input |
| Retrofitting needed a board PR touching every bus path | Define the Protocols **and test-only fakes** in the base board's first milestone; implement only what the base uses; have each add-on's Phase 0 audit the list **before the base is tagged** (the Sega audit moved six decisions) |

## The sockets (proposed; every one a narrow `typing.Protocol`, transcribable to a Rust trait)

1. **HuCard slot**: `CardSlot` holding a `Card`: `claims() -> [(first_page, last_page)]`, read/write
   with `mclk`, `reset()`. Standard ROM mirroring, SF2/Populous/Tennokoe/Navi cards and a System Card
   are all `Card`s ([cartridge.md](cartridge.md)). `Card.grounds_cd` (the `/CD` line) is what lets a
   CD unit tell a card is in. A Super System Card is a card that **also claims banks `$68-$7F` as
   RAM** and the `$18C1-$18C6` id registers (the second finding: a card is not confined to the ROM
   window).
2. **Expansion port**: `PortDevice` (the EXT BUS: A0-A20, D0-D7, `/RD`, `/WR`, `/CEK`?, `/NMI`?,
   `/IRQ2`, `RDY`, audio in, `K7` = I/O bit 7, `/CD`, and the video bus VD0-8 + HSYNC/VSYNC/DCK/VCESEL
   [doc: wiki EXT BUS pinout]). `claims()`, IRQ2 source, audio source, and `present` for the I/O
   port. The video-bus pins are **not** a socket until a device that uses them is found (U15).
3. **One decode**: the base owns a 8192-entry page table; each page is `BASE_ROM`, `BASE_RAM`,
   `HARDWARE(n)` (n = which 256-byte block of the `$FF` page), `UNMAPPED`, or a device. A device claim
   *replaces* the page's handler (so a Super System Card's RAM overrides the ROM mirror, as the
   hardware does by bank). Unmapped = `$FF`, except in the I/O-buffer region ([memory-map.md](memory-map.md)).
4. **Bus timing**: access carries its master-clock time `mclk`; wait states go through
   `Board.hold(master_clocks)` (the board lengthens the cycle). The VDC/VCE one-cycle penalty is the
   base's own use of it.
5. **Clock domains**: `Clocked.catch_up(mclk)`; the CD drive and CD-DA keep their own rational
   ratio and remainder (the CD is asynchronous to the master); ADPCM also runs from the **CD unit's own crystal**: MAME clocks the MSM5205 from a 9.216 MHz
   `PCE_CD_CLOCK` / 6 with a /48 prescaler [emu, `nec/pce_cd.cpp`]; whether the real unit's crystal is
   9.216 MHz is not confirmed by a pinned manufacturer source (U8).
6. **Interrupts** (the Sega socket that was *dropped*): `IrqLine.set(source, level)` on `IRQ1`, `IRQ2`,
   `NMI` (if C2 resolves to "connected"); `TIQ` is internal. One bit per source; the line is the OR.
7. **Pixel path** (SuperGrafx): the VDC emits, per line, 9-bit values (4 pixel + 4 palette + 1
   sprite/background bit, [hw: sgxtech]) with transparency; the base hands them to `PixelPath` whose
   default is "VDC1 straight into the VCE". The VPC replaces it, mixing two VDC lines. Line, not dot,
   granularity (Sega's picture socket, the same minimum); the VPC's per-pixel window edges are
   computed inside the replacement.
8. **Video timing**: both VDCs run from the VCE's dot clock and the same sync; a second VDC needs
   the first's line/dot position ([emu: Mesen2 `PceVpc.cpp`, ares `vdp.cpp` clock the VDCs together]).
   One `VideoTiming` record per line, as Sega's socket 6.
9. **Audio sources**: `AudioSource(rate, gain, take_samples(mclk))`, list on the board; PSG first.
10. **Reset**: `reset(kind, mclk)`.
11. **Controller ports** (an empty socket in the Sega board; cheap here): `ControllerPort` with
    `read(sel, clr) -> nibble`, `write`, for 2-button/6-button/multitap/mouse devices; the SuperGrafx's
    S-EXP port shares the nibble through a 74HC157 mux and exposes output bits 2-7.
12. **Instances, not modules**: `Vdc`, `Psg`, `Vce` classes with no module state, so a second VDC
    is a second instance (the SuperGrafx) and PC-FX (a possible later consumer of the VDC) can pin it.

## Add-on versus mode

**CD-ROM², Super CD-ROM², Arcade Card: add-on, firmly.** It is a second box with its own clock
domain (drive/CD-DA), a BIOS the user brings, 64 KiB RAM + 2 KiB backup RAM + ADPCM RAM, a SCSI-class
controller and a drive; the System Card is a *HuCard* so it enters through socket 1, and the
Arcade Card (Pro: plugs into the CD unit; Duo: inside) uses the same interface with extra ports and
2 MiB of RAM. The CD unit is much lighter than a Sega CD: **no second CPU** (the drive's firmware is
not emulated; MAME, Mednafen and Geargrafx model the controller as a state machine, [emu]), so the
Sega CD's hardest sockets (sub-CPU `/DTACK` wait, two-CPU sync) have no counterpart. The Arcade Card
lives in the same repository, as a late milestone (open decision 6).

**SuperGrafx: add-on, with a measured fallback.** It is a different console (VPC, second VDC with its
own 64 KiB, 32 KiB RAM, a back-panel switch that re-decodes `$FF:0000-03FF`, the S-EXP port), but its
footprint on the base is **five of the sockets above** (claims for `$FF:0008-0017`, RAM size, IRQ1
OR, pixel path, VDC instances) and the library has 5 SuperGrafx cards (the MAME `sgx` software list has 5 entries;
so few titles exist that the mode costs little either way). Risk: the pixel-path socket is on the render hot path. Measure it in milestone 3
(the per-line `PixelPath` call must cost within noise with no add-on); if it does not, fold the
SuperGrafx into the base as a machine-table mode (the `sms-python` shape for SMS/GG/SG). The CD
board must not depend on that choice.

## What the CD (and each add-on) needs, and what is still unknown

| Need | Socket | Status |
| --- | --- | --- |
| `$FF:1800-$18FF` (CD), `$1A00-$1AFF` (Arcade Card), banks `$80-$87` (64 KiB), `$F7` backup RAM | 2 + 3 | claims by page; two devices (CD, Arcade Card) share the port, so the add-on owns an internal decode |
| IRQ2 from the CD interface and ADPCM | 6 | per-source bits; unknown which events raise it (U8) |
| `$1000` bit 7 (CD sense) low when present | 2 | the port, not a static flag (C6: polarity) |
| System Card in the slot, `/CD` grounded | 1 | card flag |
| Super System Card RAM `$68-$7F`, ID registers | 1 + 3 | a card that claims RAM |
| CD-DA (44.1 kHz) + ADPCM (rates `32 / (16 - n)` kHz [hw]) + the fader | 9 | changeable rates |
| Drive/controller time (seek, read, SCSI phases) | 5 | `catch_up`; CD seek-time data: `reference/src/pce-cd-seek` |
| `$FF:1804` bit 2 resets the CD hardware | 10 | register inside the add-on |
| BIOS | none | bring your own, by path ([handoff-brief.md](handoff-brief.md), open decision 7) |

The SuperGrafx needs: sockets 3 (VPC at `$FF:0008-000F`, VDC2 at `$0010-0017`, mirrors every
32 bytes in native mode), 7, 8, 12, 6 (VDC2's IRQ joins IRQ1, [hw: sgxtech, "VDC #2 interrupts"]),
RAM 32 KiB, `ST0-ST2` steered to VDC1 or VDC2 by the VPC [hw: sgxtech], the compat switch, S-EXP.
The Sega lesson to apply before freezing: have both add-ons' Phase 0s audit this list.

## SuperGrafx: what the socket audit found (2026-11-05, M6)

`supergrafx-python` was the first add-on built on these sockets. Of the five sockets docs/sockets.md
named for it, four worked as drawn (3 page claims over the VDC page, the machine row's RAM size, 7
`PixelPath` handed a list of rows, 12 `Vdc` instances without module state) and **one was a table
field nothing read**: `Machine.vdc_count`. The board built one VDC, stepped one VDC and ORed one
IRQ1. That is the Sega lesson again (the board owns the clock; a device that needs time goes
through it) and the fix is the same size as the finding: `Board.vdcs`, one instance per
`vdc_count`, all stepped/synced/read by the scheduler, IRQ1 their wired-OR
([issues/0001](issues/0001-second-vdc-not-run-by-the-board.md)). A second finding that is **not**
a socket: `ST0-ST2` are indistinguishable from stores to `$FF:0000/2/3` on the bus, and the VPC
must steer only them; the add-on reads the core's private `_opcode` until huc6280-python publishes
one.

## Add-on finding: the port device is caught up (2026-11-06, M7/M8)

`pcenginecd-python` found that the board never called `PortDevice.catch_up`, so a port device could not
raise IRQ2 on its own. `Board._run_to` now calls `self.port.catch_up(target)` after the VDCs and the
timer, every advance ([issues/0002](issues/0002-port-device-never-caught-up.md)); the add-on's scheduler
subclass is no longer needed.
