"""The HuC6280 PSG package (board-owned, import-boundary tested; Aubrey's rule: it may move out
if a second consumer ever wants it, never be copied).

`Psg` is the six-channel generator (psg/chip.py): register writes with master-clock times, an
event-driven step stream for the reference comparisons, and a host-rate box-averaged output for the
`AudioSource` list. Provisional, tier 5: no hardware audio reference exists (docs/m4-record.md).
"""

from pcengine_python.psg.chip import VARIANTS, Channel, Psg

__all__ = ["VARIANTS", "Channel", "Psg"]
