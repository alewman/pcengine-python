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
