"""Reset-cause preservation and watchdog-disable ordering on actual opcodes.

Microchip ATtiny48/88 datasheet section 8.5.2 requires MCUSR.WDRF to be
cleared before WDTCSR.WDE. A narrow write monitor enforces this rule and
the four-cycle watchdog configuration window; it does not model the full
watchdog peripheral or physical reset timing.
"""
from pathlib import Path

import pytest

from avr_sim import CPU


ROOT = Path(__file__).resolve().parents[1]
MCUSR = 0x34
GPIOR0 = 0x1E
WDTCSR = 0x60
WDRF = 1 << 3
WDE = 1 << 3
WDCE = 1 << 4


class WatchdogRAM(bytearray):
    """Observe CPU stores to WDTCSR without changing ordinary SRAM behavior."""

    def __init__(self, cpu):
        super().__init__(cpu.mem)
        self.cpu = cpu

    def __setitem__(self, address, value):
        if address == WDTCSR:
            self.cpu.watchdog_writes.append((self.cpu.cycles, value))
            if value == 0:
                assert not self.cpu.read_io(MCUSR) & WDRF, (
                    'WDRF still forces WDE when startup attempts to disable WDT'
                )
                assert self.cpu.read_io(GPIOR0) == self.cpu.reset_flags, (
                    'Reset causes were not captured before watchdog disable'
                )
                assert self.cpu.watchdog_writes[-2][1] == WDCE | WDE
                elapsed = self.cpu.cycles - self.cpu.watchdog_writes[-2][0]
                assert 0 < elapsed <= 4, 'Watchdog disable missed its timed window'
        return super().__setitem__(address, value)


class ResetCPU(CPU):
    def __init__(self, image, flags):
        super().__init__(image=image)
        self.reset_flags = flags
        self.watchdog_writes = []
        self.reset_writes = []
        self.io[MCUSR] = flags
        self.io[GPIOR0] = 0xA5
        self.mem[WDTCSR] = WDE if flags & WDRF else 0
        self.mem = WatchdogRAM(self)

    def write_io(self, address, value):
        if address in (MCUSR, GPIOR0):
            self.reset_writes.append((address, value))
        super().write_io(address, value)


@pytest.mark.parametrize('flags', range(16))
def test_reset_flags_saved_and_cleared_before_watchdog_disable(flags):
    image = (ROOT / 'firmware/isp-full.bin').read_bytes()
    cpu = ResetCPU(image, flags)
    # General-purpose registers and SRAM are undefined after power-on.
    cpu.r[:] = [(index * 37 + 11) & 0xFF for index in range(32)]
    cpu.mem[0x100:0x140] = b'\xA5' * 0x40
    cpu.run_from('startup', stop_at=['L1d02'], count=600, execute_ret=True)

    assert cpu.r[1] == 0
    assert cpu.reset_writes == [(GPIOR0, flags), (MCUSR, 0)]
    assert cpu.watchdog_writes[0][1] == WDCE | WDE
    assert cpu.watchdog_writes[1][1] == 0
    assert cpu.mem[WDTCSR] == 0
    assert cpu.read_io(MCUSR) == 0
    assert cpu.read_io(GPIOR0) == flags

    # Handover must retain the captured causes rather than copy cleared MCUSR.
    cpu.run_from('L1eac', stop_at=['app_jump'], count=30, execute_ret=True)
    assert cpu.reset_writes == [(GPIOR0, flags), (MCUSR, 0)]
    assert cpu.read_io(GPIOR0) == flags
    assert cpu.read_io(0x0A) == 0  # USB pins released before application entry.
    assert cpu.mem[0x68] == 0  # PCICR disabled.
    assert cpu.mem[0x6D] == 0  # PCMSK2 disabled.
