<!-- SPDX-License-Identifier: MIT -->
# Provenance: nothing here is copied or transcribed from a GPL or LGPL project

The family reads emulators under the GPL (Mednafen and Beetle PCE, Mesen2, Geargrafx, the MiSTer
core, parts of MAME) as detectors: their sources are fetched into `reference/` (never committed),
read, cited by file and function, and run. The rule is that **none of their code enters these
repositories, copied or transcribed into Python**. A register map, a timing or a result table is a
fact about the machine or about what an emulator computes, and is used; the code that computes it is
not.

## The check

`scripts/provenance_check.py` compares every tracked text file of the repositories it is given with
every source file under the reference trees, for the traces a copy or a transcription leaves:
shared comment prose, expressions of the same shape with the same names and numbers (across
languages), shared numeric tables, and reference source lines quoted in documentation. A hit is a
place to read, not a verdict.

```sh
python3 -I scripts/provenance_check.py --repo . --repo ../huc6280-python \
    --repo ../supergrafx-python --repo ../pcenginecd-python \
    --reference reference --reference ../huc6280-python/reference \
    --licences scripts/pinned_repos.json --licences ../huc6280-python/scripts/pinned_repos.json \
    --report provenance-report.md
```

It cannot see a transcription that was also restructured and renamed throughout; the files that
say they follow an emulator stay a reading job. Run it before a release and after any change made
with an emulator's source open.

## The run of 2026-11-12 (four repositories, 4,900 reference files)

**One transcription found, and removed.** huc6280-python's decimal `ADC` and `SBC`
(`src/huc6280/_alu.py`, added 2026-11-10 and never tagged) followed Mednafen's macros line by line,
with its variable names, and had Mesen2's as the alternative; a test repeated them and the issue
quoted Mednafen's code. All three were rewritten from a description in words, the test now holds
digests of the result tables, and the results are bit-identical. The earlier commits remain in that
repository's public history.

**Read and judged to be facts or citations, not code:**

| Where | What matched | Judgment |
| --- | --- | --- |
| pcenginecd-python `seek.py` | the 14-zone table of Mesen2 and Geargrafx | all three take it from Dave Shadoff's `seektime.c`, **MIT**; acknowledged in that repository's NOTICE.md |
| `psg/chip.py` `scale_table_quirk` | sixteen numbers of MAME's and Mednafen's volume table | MAME's file is BSD-3-Clause; acknowledged in NOTICE.md |
| `vce.py`, `vdc/regs.py`, pcenginecd `syscard.py`, `adpcm.py`, `unit.py`, `arcade.py`, `scsi.py` | runs of register numbers, masks and identification bytes | what the hardware's registers are; our code around them has its own shape |
| supergrafx `vpc.py`, pcenginecd `scsi.py`, the docs' quotes of Mednafen and Mesen2 comments | eight to fifteen words of a comment, quoted with its source named | citations |
| huc6280-python `docs/timing.md` | the opcode grid's mnemonics | the instruction set |
| huc6280-python `tools/mednafen-trace.patch` | context lines of Mednafen | a patch to Mednafen: marked GPL-2.0-or-later, outside the package |

**What this does not settle.** Several behaviours have no source but the emulators (the Arcade
Card's registers, the VPC's window origin, the sprite fetch order): each is written as our own code
from what the emulators do, and is named as emulator-tier in the records. That is learning a fact
from a GPL program, not copying it, but it is the place a transcription would most easily happen,
and the place to look first when this is run again. This is an engineering check, not legal advice.

## Licence provenance (audit 2026-11-13)

This section judges the repository against the family charter as it now stands ("Licences and
provenance", rule 3): an MIT project takes nothing copied or transcribed from GPL or LGPL code, and
**the source of a GPL program is not opened while writing the code it would inform**; such programs
are run and measured as closed boxes. The practice recorded above (GPL emulators fetched into
`reference/`, read, cited by file and function) predates that rule and does not meet it. The audit
was done from this repository's own records (comments, docs, commit messages, `pinned_repos.json`);
no GPL source was opened for it. Verdicts: **clean** (own work from documents, hardware facts,
closed-box results or permissive sources), **cite** (clean once a source or notice is added),
**rewrite** (follows code we may not take), **unclear** (what would settle it is named).

### Reference trees and their licences

`scripts/pinned_repos.json` marks MAME "GPL-2.0+/BSD-3 per file". Every file of the sparse MAME
checkout (26 `.cpp`/`.h`: `huc6270`, `huc6260`, `huc6202`, `h6280`, `c6280`, `msm5205`,
`bus/pce/*`, `nec/pce*`) carries `license:BSD-3-Clause` in its first line (only that line was read
to establish this), so **the MAME PC Engine sources here are permissive** and may be read and cited,
with the notice kept for anything taken. ares is ISC. Shadoff's `PCECD_seek` and `PCE_Soundtest`,
`SingleStepTests/huc6280` and `oss-pce-cd-bios` carry MIT LICENSE files although the JSON says
"UNVERIFIED" (update owed). Mednafen / Beetle PCE (GPL-2.0+), Mesen2 (GPL-3.0), Geargrafx (GPL-3.0),
the MiSTer core's `rtl/` (GPL-2.0+) and the 240p Test Suite (GPL-2.0) are closed-box only from now
on.

**provenance_check re-run (2026-11-13), permissive trees only:**

```sh
python3 -I scripts/provenance_check.py --repo . --repo ../supergrafx-python \
    --repo ../pcenginecd-python --repo ../pcengine-rust --repo ../supergrafx-rust \
    --repo ../pcenginecd-rust --repo ../pcengine-rust-fast --repo ../play-pce \
    --reference reference/src/ares --reference reference/src/mame \
    --reference reference/src/pce-cd-seek --reference reference/src/pce-soundtest \
    --reference reference/src/single-step-huc6280 --reference reference/src/oss-pce-cd-bios \
    --licences scripts/pinned_repos.json --report <scratch>/report.md
```

304 of our files against 466 reference files, 16 file pairs with hits, all expected: the PSG volume
table (MAME `c6280.cpp`, BSD-3, already in NOTICE.md; ares has the same table), pcenginecd-python's
Super System Card id bytes (MAME `pce_scdsys.cpp`, BSD-3) and a SCSI table run (MAME `nec/pce_cd.cpp`,
BSD-3), register names in `docs/mame-oracle.md`, and generic Python idioms shared with
`oss-pce-cd-bios` test scripts (MIT). The 2026-11-12 run above, which did include the GPL trees,
stands as the record for them; it cannot see a restructured transcription, which is why the verdicts
below rest on what the code says about itself.

### Verdicts by module

| Module | Behaviour source (licence) | Verdict |
| --- | --- | --- |
| `vdc/sequencer.py` | Its docstring: "This is Mednafen's `huc6270/vdc.cpp` (HSync/VSync/IncRCR and the HPHASE machine), restated in master clocks"; `FINAL_DOTS` / `HSW_DOTS` from Mednafen identifiers (`Cycles_Between_RCRIRQ_And_HDWEnd`, the HSW phase counter); the BYR/BXR latch formula `(hds + 1) * 8 - 21` "[emu: Mednafen TimeFromHDSStartToBYRLatch / TimeFromBYRLatchToBXRLatch]"; state names `need_rcr_inc`, `need_vb_irq_test` (GPL-2.0+) | **rewrite** |
| `vdc/chip.py` | Port, registers, status, the mode-0 slot model: pcetech 5, Hudson HuC6270 manual (clean). The line-scroll state "[emu: Mednafen BG_YMoo, BG_YOffset, BG_XOffset]" (l.71) and `_step_bg_y`; `commit_unless_dma` "Mednafen's `CheckAndCommitPending`" (l.232); BYR on both bytes (l.306); the sprite budget formula, Mesen2's (l.166) (GPL) | **rewrite** (those parts, with the sequencer) |
| `vdc/dma.py` | Transfer semantics: pcetech 5.4, Hudson manual (clean). `display_ended` "the SAT transfer test of Mednafen's Run loop" (l.88), `force_complete` "as Mednafen does ... 'DMA completion forced'" (l.143), 1024 dots, 2 dots a word (Mednafen, Mesen2) | **unclear**: the values are closed-box measurable (the lockstep harness already runs Beetle PCE); the two Mednafen-placed functions go with the sequencer rewrite |
| `vdc/sprites.py` | pcetech 5.3, Hudson manual; `CLOCKS_PER_SPRITE` the manual's SM table; fetch-on-scan and the empty-sprite rule (U23) Mednafen/Mesen2 choices | **clean** (the U23 rule is a one-line behaviour, closed-box checkable) |
| `vdc/background.py`, `vdc/regs.py` | pcetech 5.1-5.2, Hudson manual | **clean** |
| `vce.py` | Hudson HuC6260 manual, pcetech 6; the linear palette is ours | **clean** |
| `machine.py` | pcetech 2.4/7, wiki. `HSYNC_CLOCKS = 237` with a quoted Mednafen line (`hblank_counter = hblank ? 237 : 1128`, vce.cpp l.561) | **unclear**: drop the quoted code; re-establish 237 by closed-box measurement or from MAME `huc6260.cpp` (BSD-3) |
| `cpu_io/timer.py` | pcetech 2.2, HuC6280 manual 2.7 (clean); `underflow_window_mclk = 15` read from Mesen2's code (`Scaler <= 5 * 3`) | **unclear** (one constant; closed-box measurable, Battle Royale is the probe) |
| `cpu_io/` (io_buffer, io_port, irq_ctl), `pads.py` | pcetech, Hudson manuals, pce-devel `PCE_Controller_Info` (community measurements, licence unverified: facts only) | **clean** |
| `cards.py` | MAME `pce_slot.cpp`, `pce_sf2`, `pce_populous`, `pce_tennokoe` (BSD-3); small Mednafen facts (2 MiB SF2 threshold, `POPULOUS` at `$1F26`, `$FF` RAM fill) | **cite**: name MAME's BSD-3 licence in the module; the Mednafen facts are facts (closed-box checkable) |
| `psg/chip.py` | Hudson PSG manual, pcetech 10; the optional `scale_table_quirk` table from MAME `c6280.cpp` (BSD-3, notice in NOTICE.md); the `mednafen` variant flags are behaviours confirmed by running the compiled referee step by step | **cite** (done: NOTICE.md); add an SPDX/notice line in the file when headers are added |
| `video.py`, `board.py`, `pagetable.py`, `hardware_page.py`, `system.py`, `sockets.py`, `state.py`, `mixer.py` | pcetech, our socket design; emulator mentions are tier notes | **clean** |
| `scripts/psg_referees/` (`mednafen_psg.cpp`, `mednafen_shim/`, `mame_c6280.cpp`, `mame_shim/`) | Harnesses compiled against the unchanged reference files; the Mednafen one reaches into its internals (`#define private public`, `psg.channel`, `blip_prev_samp`, `UpdateOutput`) | **cite**: the Mednafen harness and shim are a tool built on GPL code: mark them `GPL-2.0-or-later` (as huc6280-python's `tools/mednafen-trace.patch`), outside the package; never distribute the built binary without its source |
| other `scripts/` (libretro_run, mesen_run, mame_*, lockstep, mednafen_record, psg_compare, ...) | run emulators as closed boxes | **clean** |
| `tests/` and fixtures (`tests/detectors/*.txt` emulator outputs, `covell_hardware_splits.json` read off Covell's photographs, a PSG register log) | measurements | **clean** |
| docs: `vdc.md` (A1/A2: `CheckAndCommitPending` conditions, `DoWaitStates`, `WS_Hook(-1)`, `ProcessVramAccesses`, with line numbers), `vce.md` (Mednafen `lc263 = (V & 0x04)`, Mesen2 `ScanlineCount = ...`), `handoff-brief.md` U33 (`mystery_counter`, l.538, 635), `m5-lockstep-record.md`, `cartridge.md` (`huc.cpp` l.413-430), `issues/0004` | GPL code fragments and internals quoted with line numbers | **rewrite** (wording only: keep the behaviour and the emulator's name, drop the code and line references; ares and MAME quotes may stay) |

Counts: clean 11, cite 3, rewrite 3, unclear 3.

**What the rewrite means.** The VDC's line machine (`sequencer.py` and the scroll-latch and commit
parts of `chip.py`) is rebuilt by someone who has not read Mednafen's `vdc.cpp`, from pcetech 5 and
7, the Hudson manual, MAME's `huc6270.cpp` (BSD-3) and ares (ISC) as readable sources, Covell's
photographs, and closed-box measurements of Beetle PCE and Mesen2 (the lockstep and picture tools
exist); the M2/M3/M5 gates then decide whether anything moved. The Rust tiers inherit this.

### Verdicts after the clean rewrite (2026-11-19)

The **rewrite** and **unclear** items above were replaced under the rules of
[restart.md](restart.md): the tainted code moved unread into the git-ignored `scratch/withdrawn/`
and written again from Hudson's manuals, `pcetech.txt`, the PCEdev wiki and MAME's BSD-3 files
(acknowledged in NOTICE.md), with no GPL source opened; the GPL emulators only run as closed boxes.
The table above is kept as the audit's record.

| Item | Verdict now | How |
| --- | --- | --- |
| `vdc/sequencer.py` | **clean** (rewritten) | a new line machine from the manual (HSR/HDR/VPR/VDW/VCR/RCR/CR), pcetech 5.1/7 and MAME huc6270.cpp (BSD-3, read, not transcribed) |
| `vdc/chip.py` scroll state, `write`, `fetch_sprites`, `vsync`; `commit_unless_dma` | **clean** (rewritten; the commit guard is gone, not needed) | the manual's BYR/BXR/MWR/CR text and its sprite table 2.4.1 (6); MAME for BYR on either byte |
| `vdc/dma.py` `display_ended`, `force_complete`, 1024 dots, 2 dots a word | **clean** (rewritten) | the SAT transfer at the vertical blanking [mfr], held three lines [hw: pcetech 5.4]; a word = two accesses at the MWR access width [mfr]; `finish_without_display` replaces the forced completion |
| `machine.py` `HSYNC_CLOCKS = 237` | **clean** (cite) | MAME huc6260.cpp's comment (BSD-3), the quoted Mednafen line dropped |
| `cpu_io/timer.py` `underflow_window_mclk` | **clean**, now 3 | one PPS3 clock [mfr: HuC6280 manual 2.7], HYPOTHESIS; closed-box bound with Battle Royale (any window 1-60 gives the referees' picture, 0 does not) |
| docs (vdc, vce, brief U33, lockstep record, cartridge, memory-map, issue 0004) | **clean** (reworded) | no GPL code, internal names or line numbers; behaviour learned from those programs before 2026-11-19 kept as facts and said so |

Counts now: clean 20, cite 0, rewrite 0, unclear 0 (the three cite items closed 2026-11-19,
below; before that: clean 17, cite 3). The judges before and after are in [restart.md](restart.md):
the 18-title gate holds; the library sweep is 168 of 179 identical (170 before).

### The cite items, closed 2026-11-19

Comments, headers and documents only; no behaviour changed (pcengine-rust carries nothing).

| Item | Verdict now | What was done |
| --- | --- | --- |
| `cards.py` | **clean** | SPDX header naming MAME `bus/pce/pce_slot.cpp` and `pce_rom.cpp` (BSD-3-Clause, copyright Fabio Priuli; licence line checked); NOTICE.md entry added; two comments that named a Mednafen file and identifier reworded to the behaviour they describe |
| `psg/chip.py` | **clean** | SPDX header and a notice line naming MAME `sound/c6280.cpp` (BSD-3-Clause, copyright Charles MacDonald; licence line checked) for the `scale_table_quirk` table; the NOTICE.md entry was already there |
| `scripts/psg_referees/` | **clean** (a GPL tool, marked); its Mednafen half moved out 2026-11-21 ("GPL tools moved out", below) | `mednafen_psg.cpp`, `mednafen_shim/mednafen/mednafen.h` and `mednafen_shim/trio/trio.h` carry `SPDX-License-Identifier: GPL-2.0-or-later`; `mame_c6280.cpp`, `mame_shim/emu.h` and the two build scripts MIT; a README says the Mednafen referee is a GPL tool compiled against the reference tree, outside the MIT package, its binaries never distributed. The shim files were checked to be our own text without opening any Mednafen source: they are short (32 lines, and a one-line empty `trio.h`), consist of C integer type names, empty macros and empty save-state stubs written for the harness, their git blob hashes match none of the same-named files in the reference trees, and they arrived in the harness's own commit (62b3077) described as stand-ins. None is a copy of GPL text |

### History

No deleted files in any of the eight repositories; no C/C++ code found in the added lines of any
commit to `src/`, `tests/` or `docs/` (searched for C types, `->`, `::` with `;` or `{`). The
quoted fragments listed above are in the public history from the commits that wrote them. The one
transcription known in this family's history is the CPU core's decimal ADC/SBC (huc6280-python,
rewritten 2026-11-12, see above; the core's own audit covers it); this board pins `265df88`, after
the rewrite.

## GPL tools moved out (2026-11-21)

At the history reset (Aubrey's ruling 4 of 2026-11-20) the GPL tools left the repository and
its history: the Mednafen PSG referee (`scripts/psg_referees/mednafen_psg.cpp`,
`mednafen_shim/`, `build_mednafen.py`: compiled into a GPL program) and `scripts/mesen_run.py`
(a ctypes driver of Mesen2's GPL C API, which the family's rule counts as a GPL tool). They are
kept with the family's other GPL tools until the tool repositories take them;
`tests/test_psg_referees.py`, `scripts/detectors_compare.py` and `scripts/m2_refs.py` find them
through `EMU_TOOLS_GPL` at their documented paths (`scripts/emu_tools.py`; emu-tools
`docs/contract.md`, section 5) and run them as separate programs: since 2026-11-24
`detectors_compare.py` runs mesen2-runner (`tools/mesen2/run.py`, machine `pce`);
`m2_refs.py` keeps the old command line (`tools/pcengine-python/mesen_run.py`, now a shim over
the same runner) because `run.py` has no sprite switch yet; the Mednafen referee is built by
`tools/pcengine-python/psg_referees/build_mednafen.py`. The old `PCE_GPL_TOOLS` is no longer
read. The MAME referee (MIT harness over a BSD-3-Clause file) and
`scripts/libretro_run.py` (the libretro ABI, MIT) stay.

## Closed-box sources removed (2026-11-24)

Aubrey's rule of 2026-11-24: an MIT repository does not download or keep the source of
anything the family's `sources.md` marks closed box only, unless a program with no shipped
build is built from it. Pins removed from `scripts/pinned_repos.json`, trees moved aside
unopened, out of the repository (not deleted): Beetle PCE
(https://github.com/libretro/beetle-pce-libretro @ `b96c11e095b6a40a412d2da02766ae1c3f4fd539`,
GPL-2.0+), Geargrafx (https://github.com/drhelius/Geargrafx @
`57c257dda25f441fff3c63a63bbc4ba7cbb713e3`, GPL-3.0) and Mesen2
(https://github.com/SourMesen/Mesen2 @ `b9fa69ddc6d0a331fb103fdb5eef6904305703c2`, GPL-3.0);
TurboGrafx16_MiSTer's `rtl/` left its sparse list (its `docs/`, Hudson's manuals, stays). The
libretro cores built inside the Beetle and Geargrafx trees were copied out first to
`reference/build-beetle-pce/` and `reference/build-geargrafx/` (sha1 `e51f5697`, `38bae175`);
`m2_refs.py`, `detectors_compare.py` and `libretro_run.py` point there (shipped cores for a fresh
checkout).

**Kept, with a question for Aubrey:** mednafenPceDev (`55dba394`, GPL-2.0+), because the
Mednafen PSG referee in emu-tools-gpl compiles its `pce_psg.cpp` and no shipped build exists.

Passages rewritten: validation.md's Mesen2 traps (the known case: `PceVpc::ProcessStartFrame` and
`PceDefaultVideoFilter::InitLookupTable` dropped; the black frames and the skipped frames kept
as OBSERVED; the exact skip condition marked HYPOTHESIS), Beetle's quoted `vdc.cpp` comment with
line numbers (now HYPOTHESIS, no quote), psg.md's Mesen2 and Mednafen source paths, sockets.md's
Mesen2 file name. The configuration fields the driver sets (`PcEngineConfig.Palette`,
`DisableFrameSkipping`) are the library's exported interface and stay named.

