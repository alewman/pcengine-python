"""The HuC6270 VDC package (instances, import-boundary tested).

It imports only `machine` constants from the rest of the board, so it can move to a core of its
own if PC-FX or a second consumer needs it: broken out, never copied.
"""

from pcengine_python.vdc.chip import Vdc
from pcengine_python.vdc.regs import VdcRegisters
from pcengine_python.vdc.sequencer import VPhase

__all__ = ["VPhase", "Vdc", "VdcRegisters"]
