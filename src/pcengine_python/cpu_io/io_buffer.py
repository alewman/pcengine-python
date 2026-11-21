"""The I/O buffer: the last value read from or written to $0800-$17FF.

[hw: pcetech 3 note 1] Reads of some locations return buffer bits where the manual says
"unused"; games that read them see the buffer. The pcetech worked example is the first unit test
(tests/test_cpu_io.py).
"""

from __future__ import annotations


class IoBuffer:
    def __init__(self, value: int = 0) -> None:
        self.value = value

    def reset(self) -> None:
        self.value = 0
