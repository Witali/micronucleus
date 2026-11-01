"""Public write-dispatch validation and durable ACK gating after SWAP packing.

READ8 is routed before this write dispatcher and has separate wire regressions.
Only the current artifact uses these internal markers; frozen reference images
retain their original fixture encodings.
"""
from functools import lru_cache
from itertools import product
import re

from tests35 import ep0_model as h
import tests.avr_exec as executor


def markers():
    """Read the shared current-source encoding, rather than copy magic values."""
    header = (h.ROOT / 'source/compact_protocol.inc').read_text()
    return {name: int(re.search(r'^#define ' + name + r'\s+(0x[0-9a-fA-F]+|[0-9]+)\s*$',
                               header, re.MULTILINE).group(1), 0)
            for name in ('CMD_PENDING_WRITE4', 'CMD_PENDING_RUN')}


def dispatch(art, pending, tx_length, ack_marker, counter):
    cpu = executor.AVRExec(art)
    cpu.r[1] = 0
    cpu.r[2:4] = [ack_marker, pending]
    cpu.r[26:30] = [counter & 255, counter >> 8, 0, 1]
    cpu.ram[15] = tx_length
    stops = ('usb_tx_prepare_pending_reply', 'flash_erase_selected_page',
             'bootloader_clear_command', 'bootloader_start_application')
    assert cpu.run('bootloader_dispatch_command', stop=stops, limit=100) == 'stop'
    assert not cpu.spms
    return next(label for label in stops if cpu.pc == art['symbols'][label])


def write_command(art, opcode, address, pending):
    cpu = executor.AVRExec(art)
    cpu.r[1] = 0
    cpu.r[25] = opcode
    cpu.r[28:32] = [0, 1, 0, 1]
    cpu.r[4:6] = [0xad, 0xbc]
    cpu.r[14:16] = [address & 255, address >> 8]
    stops = ('usb_reply_empty', 'usb_reply_stall')
    assert cpu.run('bootloader_check_set_flash_address', stop=stops, limit=100) == 'stop'
    if opcode in (1, 2):
        assert cpu.pc == art['symbols']['usb_reply_empty']
        assert cpu.r[3] == opcode + 1 and cpu.r[4:6] == [address & 255, address >> 8]
        assert [operation[0] for operation in cpu.spms] == [17]
    else:
        assert cpu.r[4:6] == [0xad, 0xbc] and not cpu.spms
        if opcode in (3, 4):
            assert cpu.pc == art['symbols']['usb_reply_empty']
            assert cpu.r[3] == pending[opcode]
        else:
            assert cpu.pc == art['symbols']['usb_reply_stall'] and cpu.r[3] == 0


def test():
    art = h.build()
    encoding = markers()
    write, run = encoding['CMD_PENDING_WRITE4'], encoding['CMD_PENDING_RUN']
    assert write != run
    # Decode once per object. Restore the executor to avoid a test-order effect.
    previous = executor.decode
    executor.decode = lru_cache(maxsize=1)(previous)
    try:
        gate_cases = 0
        for pending, tx, marker, counter in product(
                (0, 2, 3, 5, write, run), (0, 2, 4, 8, 12, 0x5a, 0x1e),
                (0, 4, 8, 12), (0, 1, 256, 65535)):
            actual = dispatch(art, pending, tx, marker, counter)
            if not tx & 0x10:
                expected = 'usb_tx_prepare_pending_reply'
            elif pending in (3, 5):
                expected = 'flash_erase_selected_page'
            elif pending == run:
                expected = ('bootloader_start_application' if counter == 0
                            else 'usb_tx_prepare_pending_reply')
            else:
                expected = 'bootloader_clear_command'
            assert actual == expected, (pending, tx, marker, counter, actual, expected)
            gate_cases += 1
        command_cases = 0
        addresses = (0, 63, 64, art['boot'] - 64, art['boot'], 8191)
        for opcode, address in product(range(256), addresses):
            write_command(art, opcode, address, {3: write, 4: run})
            command_cases += 1
    finally:
        executor.decode = previous
    print('PASS current write-dispatch bytes and durable ACK/RUN gate:',
          command_cases, gate_cases)


if __name__ == '__main__':
    test()
