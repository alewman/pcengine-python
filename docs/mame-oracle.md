# MAME 0.285 as a detector: the verified recipe for `pce`, `tg16`, `sgx` (and the CD)

MAME 0.285 (`/usr/games/mame`, source pinned at tag `mame0285`, `f379cd06`, sparse in
`reference/src/mame`) is a **detector** for this board, never a judge ([validation.md](validation.md)).
Everything here was run on 2026-10-23; `scripts/mame_trace.py` encodes it. It is a good detector for
the HuC6280 instruction stream and for "does this card start", a weak one for cycle timing of the
VDC and for the CD (its own source lists the CD as unfinished: [cd.md](cd.md)).

## Drivers, devices, ROM sets

`mame -listdevices pce`: `maincpu` = HuC6280 **@ 7.15 MHz**, `psg` @ 3.57 MHz, `huc6260` (VCE) @
21.47 MHz, `huc6270` (VDC), `screen` @ 21.47 MHz (raw: 1365 x 263 clocks, visible `64..1152`,
lines 18-260: `pce.cpp`), `cartslot`, `ctrl` (joypad, Avenue/Arcade Pad 6, mouse, multitap, pachinko),
and **the CD add-on is a device of the same driver** (`pce_cd`: `bram`, `cdda` @ 44.1 kHz, `cdrom`,
`msm5205` @ 1.53 MHz). `sgx` adds `huc6202` (VPC) and a second VDC (`huc6270_0`, `_1`); `tg16` is the
US console. **No ROM set is needed**: `mame -listroms pce/tg16/sgx` print "No ROMs required"; the
`--rompath` given by `mame_trace.py` is an empty directory. (Unlike `snes`, which needs the IPL.)
The CD needs the System Card as a `-cart` image.

**The `(USA)` images need the `tg16` driver.** Measured with four cards (`Aero Blasters`, `Bonk's
Adventure`, `Blazing Lazers`, `R-Type`, 6 s each): under `pce` every snapshot is one colour (black);
under `tg16` they show 13-21 colours. A different console, not a different ROM: the TurboGrafx-16's
I/O port reports "country = TurboGrafx-16" ([memory-map.md](memory-map.md)). `detectors_compare.py`
picks `tg16` for names containing `(USA)`.

## The recipe

```sh
python -I scripts/mame_trace.py pce tests/test_roms/CPU_Test/CPU_Test_10.pce --seconds 1
python -I scripts/mame_trace.py tg16 "/data/emu/roms-retrobat/pcengine/Bonk's Adventure (USA).7z" \
    --no-trace --seconds 20        # snapshot only: snap/tg16/0000.png at exit
python -I scripts/mame_trace.py sgx  "/data/emu/roms-retrobat/supergrafx/Battle Ace (Japan) (En).7z" --seconds 3
```

which runs, in a fresh `tests/mame_traces/<driver>-<stem>/` (the `.7z` is extracted there with `7z`):

```sh
mame pce -cart <card>.pce -rompath <empty> -homepath <out> -snapshot_directory snap \
  -video none -sound none -nothrottle -noreadconfig -skip_gameinfo \
  -debug -debugger none -log -seconds_to_run <n> -autoboot_script <out>/trace.lua
```

with the trace line (14 values; `logerror` drops values past 14, found on the Z80 boards):

```lua
dbg:command('trace cpu.trace,:maincpu,noloop,{logerror "C %X %X %X %X %X %X %d %d %d %d %X %X %X %X\\n",pc,a,x,y,s,p,totalcycles,beamy,beamx,frame,mpr1,mpr2,mpr3,mpr4}')
```

Output in `error.log`: `C PC A X Y S P totalcycles beamy beamx frame MPR1..MPR4`, one line per
instruction **before** it executes, `PC` the 16-bit logical address (the first lines of
`CPU_Test_10.pce` are `C E000 ...`, the reset vector). With `--mprs` the clock fields are replaced
by MPR0-MPR7.

## What the fields mean (measured)

- **`totalcycles` counts ticks of the 7.159 MHz clock**: at reset (low-speed mode) `SEI` advances
  it by 8 (2 CPU cycles at master/12 = 4 ticks each) and `CSH`, `TAM` ... in multiples of 4 until the
  program executes `CSH`; in high speed one cycle is one tick. To get master clocks, multiply by 3.
- `beamy`/`beamx`: MAME's screen position (`beamx` in master clocks up to 1365, so a 5.37 MHz dot is
  4 units); `frame` the frame counter. In the CPU test's first 2,148,938 instructions the last line
  reads `frame 59 beamy 259`: one second of emulated time.
- **Speed**: with the trace, **58.5 s of wall time per emulated second** on the CPU test (2.1 M
  instructions/s are logged); without `-debug` the CPU test costs 0.3-1.4 s per emulated second ("Average speed 358%" for
  5 s) and the CD ran at 496% untraced.
- **Snapshots** are 1088 x 242 for the CPU test: the screen is configured in master clocks so every
  dot is `clock divider` columns wide; there is **no single scale factor** (5 MHz: 4 columns per dot,
  7 MHz: 3, 10 MHz: 2). The picture starts about 32 columns in. MAME draws the 242 active lines
  from frame line 18; Mesen2 and Beetle PCE start earlier: `detectors_compare.py` measures an offset
  of about **5 rows between MAME and the other two** and 0 between Mesen2 and Beetle on typical
  games (see `tests/detectors/pce-sample-2026-10-23.txt`; `+24` entries are search-limit hits on
  flat pictures).

## Traps found

1. **`wpset` ranges are logical addresses on the HuC6280.** `wpset 1fe000,2000,r` (the hardware page,
   as a physical address) fired on every ROM fetch at logical `$E000-$FFFF` (range low 16 bits) and
   `wpaddr` printed the *physical* address of the access (`R 0 78 E000`): 2,072,408 lines in 1 s.
   **There is no per-register access log from MAME 0.285 here.** Lua `install_read_tap` /
   `install_write_tap` on `maincpu` `program` space (`0x1fe000-0x1fffff`) logged nothing for
   the hardware page (and one earlier variant segfaulted MAME). Register order must be recovered
   from the instruction trace by decoding stores (the board's lockstep does that on its own side).
2. **An unknown symbol drops the whole trace command silently** (as on the SNES board); the
   symbols the h6280 exposes are `PC S P A X Y IM TMR NMI IRQ1 IRQ2 IRQT MPR0..MPR7` and `totalcycles`
   (`h6280.cpp` `state_add`, l.242-258).
3. **`error.log` is not truncated by every launch and the old content survives a crashed one**: use
   a fresh directory per run (the script does).
4. **`pkill -f "mame pce"` kills the shell that runs it** if the pattern is in its own command line;
   use the PID.
5. **`-seconds_to_run` takes integers** (0.05 hung under `-debug`).
6. The CD: `mame pce -cart syscard3.pce -cdrom X.chd -rompath <empty>` boots the Super System Card
   screen (`PUSH RUN BUTTON!` after 60 s); the CD is a device of `pce`, `tg16` and `sgx` alike.
7. `grep` on `error.log` needs `-a` (UTF-8 BOM and binary bytes).

## Measured

| Run | Result |
| --- | --- |
| `CPU_Test_10.pce` (Covell), `pce`, 1 s, traced | 2,148,938 instructions, 58.5 s wall; snapshot shows grey raster stripes where the hardware photos and Mesen2/Beetle/Geargrafx show **magenta/black** (MAME colours that test differently: unresolved, a detector disagreement) |
| 35 library cards (5 SGX, 30 PCE/TG16), 5 s each | all start and draw; see [validation.md](validation.md) for the three-way comparison |
| Bonk III CHD + `syscard3.pce`, 60 s | System Card screen, "PUSH RUN BUTTON!" |

## What MAME does not give us

- the VDC's CPU access schedule (MAME's `huc6270.cpp` uses its own BSY model, 0x40 "set when the VDC
  accesses VRAM"; not checked line by line here), cycle-exact sprite timing, the VCE palette-access
  conflict;
- any register-access log (trap 1), so **MAME lockstep is by instruction stream and registers only**,
  as in the 6502 boards, with clock differences named per cause; a clock difference that is not
  one of the known causes is a finding;
- a trustworthy CD (its TODO list), an ADPCM half-event model, the fader.
