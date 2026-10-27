"""Check real five-millisecond bus polling and synchronized packet capture."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_candidate import checked_build
from tests27 import cooperative_usb as usb

def machine(artifact, stream):
    usb.configure(artifact)
    cpu = usb.CPU(usb.meta, {'memory': bytearray(0x300), 'registers': [0] * 32})
    cpu.flash = usb.FlashView(cpu.flash, cpu.base)
    cpu.r[21], cpu.r[29] = 0xA0, 1
    cpu.m[0x100], cpu.m[0x10F] = 0xFF, 0x5A
    cpu.pc = cpu.labels['bootloader_poll_begin']
    cpu.io = usb.PinIO(cpu, stream)
    cpu.io.cleared_at = -1
    return cpu

def check_quiet_poll(artifact):
    cpu = machine(artifact, usb.Stream())
    samples, checks = [], []
    for _ in range(100000):
        if cpu.pc == cpu.labels['bootloader_process_pending_command']:
            break
        if cpu.pc == cpu.labels['usb_poll_sample_bus']:
            samples.append(cpu.t)
        if cpu.pc == cpu.labels['usb_poll_check_packet_pending']:
            checks.append(cpu.t)
        cpu.executing_pc = cpu.pc
        cpu.step()
    else:
        raise AssertionError('Quiet-J poll failed to time out')
    assert cpu.word(26) == 0 and len(samples) == 80000 // 13
    assert set(b - a for a, b in zip(samples, samples[1:])) == {13}
    assert set(b - a for a, b in zip(checks, checks[1:])) == {13}
    assert 79980 <= cpu.t <= 80020, cpu.t
    duration = cpu.t
    # Sustained SE0 still clears both addresses on the hundredth sample.
    class Reset(usb.Stream):
        def level(self, _time):
            return 0
    cpu = machine(artifact, Reset())
    cpu.m[0x10C], cpu.m[0x113] = 0x5A, 0x7C
    count = 0
    for _ in range(2000):
        count += cpu.pc == cpu.labels['usb_poll_sample_bus']
        cpu.executing_pc = cpu.pc
        cpu.step()
        if cpu.m[0x10C] == cpu.m[0x113] == 0:
            break
    assert count == 100, count
    print('PASS', artifact['mode'], '13-cycle quiet-J polling,', duration,
          'cycles to timeout, sustained SE0 reset after exactly 100 samples', flush=True)
    return duration

def check_poll_capture(artifact):
    maximum = 0
    cases = 0
    # These tests cover every quarter-cycle relative entry phase over more
    # than one complete quiet-J iteration. The unchanged PHY has its broader
    # independent jitter admission; here the altered call edge is exercised.
    for rate in (1_499_250, 1_500_000, 1_500_750):
        for packet in (usb.token(0x2D), usb.data_packet(bytes(8)),
                       usb.data_packet(bytes([0xFF]) * 8)):
            for quarter in range(80):
                sop = quarter / 4
                stream = usb.Stream()
                stream.waves.append(usb.Wave(packet, start=sop, rate=rate))
                cpu = machine(artifact, stream)
                entered = None
                for _ in range(6000):
                    if cpu.pc == cpu.labels['USB_handler'] and entered is None:
                        entered = cpu.t
                    if cpu.pc == cpu.labels['usb_rx_end_packet']:
                        break
                    cpu.executing_pc = cpu.pc
                    cpu.step()
                else:
                    raise AssertionError(('No complete packet', rate, packet.hex(), sop))
                assert bytes(cpu.m[0x116:0x116 + len(packet)]) == packet, (rate, packet.hex(), sop)
                assert entered is not None and entered - sop <= 40
                maximum = max(maximum, entered - sop)
                cases += 1
    print('PASS', artifact['mode'], cases, 'actual main-poll packet captures;',
          'maximum physical SOP entry', maximum, 'cycles', flush=True)
    return cases, maximum

if __name__ == "__main__":
    for mode, boot in (("NONE", 0x1B80), ("ACTIVE_HIGH", 0x1B40), ("ACTIVE_LOW", 0x1B40)):
        artifact = checked_build(mode, boot)
        check_quiet_poll(artifact)
        check_poll_capture(artifact)
