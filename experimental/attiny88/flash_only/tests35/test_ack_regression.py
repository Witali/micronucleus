#!/usr/bin/env python3
"""Pass35 ACK eligibility versus durable TX state, emitted-AVR and finite waveform tests.

No hardware USB testing. The unsafe prototypes are deliberately kept out of release.
"""
from functools import lru_cache
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests35.wave import PERIOD
from tests35.foreground import one
from check_build import build
from tests.avr_exec import AVRExec
from tests34.test_pass33_ack import CPU

@lru_cache(maxsize=32)
def artifact(source, led, boot):
    return build(f'{source}/micronucleus_t88_compact.S', mode=led, boot=boot)

MODES = [('NONE', 0x1BC0, 1036, 0x0450),
         ('ACTIVE_HIGH', 0x1BC0, 1056, 0x0451),
         ('ACTIVE_LOW', 0x1BC0, 1054, 0x0452)]

STOPS = ('usb_tx_prepare_pending_reply', 'flash_erase_selected_page',
         'bootloader_clear_command', 'bootloader_start_application')

def dispatch(source, led, boot, marker, tx_length, pending, xlo=0, xhi=0):
    art = artifact(source, led, boot)
    cpu = AVRExec(art)
    cpu.r[1] = 0
    cpu.r[2] = marker
    cpu.r[3] = pending
    cpu.r[26], cpu.r[27] = xlo, xhi
    cpu.r[28], cpu.r[29] = 0, 1
    cpu.ram[15] = tx_length
    assert cpu.run('bootloader_dispatch_command', stop=STOPS, limit=55) == 'stop'
    matching = [label for label in STOPS if cpu.pc == art['symbols'][label]]
    assert len(matching) == 1, (source, led, pending, marker, tx_length, matching)
    return matching[0]

def test():
    cases = 0
    for led, boot, size, bcd in MODES:
        art = artifact('source', led, boot)
        assert len(art['body']) == size and boot + size <= 8192
        assert int.from_bytes(art['body'][32:34], 'little') == bcd
        # The persistent TX buffer, NOT R2 ACK-eligibility, controls whether
        # an SPM or RUN can safely start after transmitting a DATA packet.
        for marker in (0, 4, 8, 12):
            for tx_length in (0, 2, 4, 8, 12, 0x5a):
                outstanding = not bool(tx_length & 0x10)
                for command in (0, 2, 3, 4, 5):
                    result = dispatch('source', led, boot, marker, tx_length, command)
                    if outstanding:
                        expected = 'usb_tx_prepare_pending_reply'
                    elif command in (3, 5):
                        expected = 'flash_erase_selected_page'
                    elif command == 4:
                        expected = 'bootloader_start_application'
                    else:
                        expected = 'bootloader_clear_command'
                    assert result == expected, (led, marker, tx_length, command, result, expected)
                    cases += 1
        # No new ACK windows across unrelated/invalid traffic. At the same
        # time, the durable DATA cache MUST remain for retransmission.
        for marker in (4, 8, 12):
            for length in (0, 2, 12):
                cpu = CPU(art)
                cpu.r[23], cpu.r[2] = length, marker
                cpu.mem[0x100 + 15] = 12
                assert cpu.run('usb_rx_check_ack', ('usb_rx_store_token',), limit=75) == 'usb_rx_store_token'
                assert cpu.r[2] == 0 and cpu.mem[0x100 + 15] == 12, (led, marker, length)
                assert dispatch('source', led, boot, cpu.r[2], 12, 3) == 'usb_tx_prepare_pending_reply'
                cases += 1
            cpu = CPU(art)
            cpu.r[23], cpu.r[2] = 1, marker
            cpu.mem.update({0x100+15:12, 0x100+12:0x06, 0x100+19:0x2e})
            assert cpu.run('usb_rx_check_ack', ('usb_handler_packet_done',), limit=75) == 'usb_handler_packet_done'
            assert cpu.r[2] == 0 and cpu.mem[0x100+15] == 0x5a and cpu.mem[0x100+12] == 0x2e
            assert dispatch('source', led, boot, cpu.r[2], 0x5a, 3) == 'flash_erase_selected_page'
            cases += 1
            cpu = CPU(art)
            cpu.r[2], cpu.r[16] = marker, 0x69 # Non-ACK IN token.
            cpu.mem[0x100+15] = 12
            assert cpu.run('usb_rx_ignore_packet', ('usb_rx_store_token',), limit=75) == 'usb_rx_store_token'
            assert cpu.r[2] == 0 and cpu.mem[0x100+15] == 12
            cases += 1
        # Explicit counterexample: old Pass34 starts SPM while DATA unACKed.
        old = artifact('reference_pass34', led, boot)
        old_cpu = AVRExec(old)
        old_cpu.r[1], old_cpu.r[2], old_cpu.r[3] = 0, 12, 3
        old_cpu.r[26], old_cpu.r[27] = 20, 1
        old_cpu.run('bootloader_dispatch_command', stop=STOPS, limit=55)
        assert old_cpu.pc == old['symbols']['flash_erase_selected_page']
        cases += 1
    print('PASS linked AVR TX-state dispatch, ACK eligibility/retry, Pass34 counterexample:', cases)

    waves = 0
    for led, boot, _, _ in MODES:
        for pending in (0, 3, 5):
            for ipd in (2*PERIOD, 3*PERIOD, 4*PERIOD, 5*PERIOD, 7.5*PERIOD):
                for phase in (0, 1/3, 2/3):
                    s, result = one(led, boot, 'bootloader_process_pending_command', pending, ipd,
                                    phase=phase, source='source', halt=True)
                    assert result == 'ack' and s.spm_hit is None, (led, pending, ipd, phase, result, s.spm_hit, s.trace[-9:])
                    waves += 1
        for cmd in (3,5):
            s,result = one(led, boot, 'bootloader_process_pending_command', cmd, 2*PERIOD,
                           source='reference_pass34', halt=True)
            assert result == 'timeout' and s.spm_hit is not None, (led, cmd, result, s.spm_hit)
            waves += 1
    print('PASS finite digital ACK wave timings and Pass34 SPM counterexamples:', waves)

if __name__ == '__main__':
    test()
