"""Small drivers shared by the board-level tests."""

from pcengine_python.machine import HARDWARE_BASE, LINE_CLOCKS

VDC_ADDR = HARDWARE_BASE
VCE = HARDWARE_BASE + 0x0400


def vdc_reg(cpu, register, value16):
    """What `ST0 #reg; ST1 #lsb; ST2 #msb` does: select, then LSB, then MSB at $0002/$0003."""
    cpu.write(VDC_ADDR + 0, register)
    cpu.write(VDC_ADDR + 2, value16 & 0xFF)
    cpu.write(VDC_ADDR + 3, value16 >> 8)


def vdc_status(cpu):
    return cpu.read(VDC_ADDR)


def standard_display(cpu, *, cr=0x00C8):
    """The 256x224 mode of pcetech 7: VDS $17, VSW $02, VDW $DF, VCR $0C."""
    vdc_reg(cpu, 0x0A, 0x0202)  # HSR: HDS 2, HSW 2
    vdc_reg(cpu, 0x0B, 0x041F)  # HDR: HDE 4, HDW $1F
    vdc_reg(cpu, 0x0C, 0x1702)  # VPR: VDS $17, VSW $02
    vdc_reg(cpu, 0x0D, 0x00DF)  # VDW
    vdc_reg(cpu, 0x0E, 0x000C)  # VCR
    vdc_reg(cpu, 0x05, cr)


def line_of(board, mclk):
    """The (frame, line) a master-clock time falls in, counting from power-on with 263-line
    frames (valid while the VCE keeps 263 lines)."""
    absolute = mclk // LINE_CLOCKS
    return divmod(absolute, 263)
