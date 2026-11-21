<!-- SPDX-License-Identifier: MIT -->
# Third-party notices

pcengine-python is MIT licensed (LICENSE). It contains no code from the GPL and LGPL emulators its
documents cite (Mednafen, Beetle PCE, Mesen2, Geargrafx, the MiSTer core, MAME's GPL files): since
the clean rewrite of 2026-11-19 ([docs/restart.md](docs/restart.md)) they are run as closed boxes
only, never read, and `scripts/provenance_check.py` looks for copies and transcriptions
([docs/provenance.md](docs/provenance.md)).

Permissively licensed material is acknowledged here.

- **MAME's HuC6270 and HuC6260 devices**, `src/devices/video/huc6270.cpp` and `huc6260.cpp`,
  BSD-3-Clause, copyright Wilbert Pol, and **MAME's HuC6280**, `src/devices/cpu/h6280/h6280.cpp`,
  BSD-3-Clause, copyright Bryan McPhail. They were read as a description of the chips where
  Hudson's manuals and MacDonald's notes are silent, and the behaviour they describe informs
  `src/pcengine_python/vdc/sequencer.py`, `vdc/chip.py` (the vertical scroll counter, BYR on either
  byte) and the constants `HSYNC_CLOCKS` and `LINE_CLOCKS` in `machine.py`. No code was
  transcribed; the files name this source in their headers. The same BSD-3-Clause notice as below
  applies to anything taken from them.
- **MAME's PC Engine cartridge devices**, `src/devices/bus/pce/pce_slot.cpp` and `pce_rom.cpp`
  (the `pce_sf2`, `pce_populous` and `pce_tennokoe` boards), BSD-3-Clause, copyright Fabio Priuli.
  Read as a description of the cards: the mirroring of odd-sized images, the Street Fighter II
  mapper's decode, Populous's RAM window and the Tennokoe Bank's lock inform
  `src/pcengine_python/cards.py`, which names this source in its header. No code was transcribed.
  The BSD-3-Clause notice below applies to anything taken from them.

One small table has a permissively licensed origin:

- `src/pcengine_python/psg/chip.py`, the sixteen values of the optional `scale_table_quirk` volume
  table, are those of MAME's `src/devices/sound/c6280.cpp`, which is BSD-3-Clause, copyright
  Charles MacDonald. Redistribution of that file's material requires its notice: "Redistribution
  and use in source and binary forms, with or without modification, are permitted provided that
  the following conditions are met: 1. Redistributions of source code must retain the above
  copyright notice, this list of conditions and the following disclaimer. 2. Redistributions in
  binary form must reproduce the above copyright notice, this list of conditions and the following
  disclaimer in the documentation and/or other materials provided with the distribution. 3.
  Neither the name of the copyright holder nor the names of its contributors may be used to endorse
  or promote products derived from this software without specific prior written permission. THIS
  SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED
  WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
  FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
  PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF
  THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
