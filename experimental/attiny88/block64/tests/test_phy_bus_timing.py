"""Independent AVR-cycle RX/TX waveform checks for Block64 transactions.

USB 2.0 sections 7.1.18.1 and 7.1.19.1 measure from end-EOP SE0->J to
start-SOP J->K. The stricter detachable-cable limit is 6.5 low-speed bits;
7.5 applies only to captive cables. These are digital instruction-cycle
checks, not electrical USB certification or oscillator/voltage validation.
"""
from pathlib import Path
import importlib
import hashlib
import json
import random
import re
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT.parents[2] / 'docs/attiny88-block64-history/archives/Micronucleus_ATtiny88_Block64_ALL_CODE_AGENT_HANDOFF_2026-10-26.zip'
ARCHIVE_ROOT = 'Micronucleus_ATtiny88_Block64_COMPLETE_HANDOFF_2026-10-26/02_CURRENT_PASS15_EXPERIMENTAL/firmware/'
# Reuse a separate, older instruction interpreter, including PUSH/POP/BST/BLD.
# Its historical decoder import rewrites argv; keep that side effect local.
_saved_path, _saved_argv = sys.path[:], sys.argv[:]
try:
    sys.path.insert(0, str(ROOT.parent / 'tests'))
    Timed = importlib.import_module('test_vusb_timing').Timed
finally:
    sys.path[:] = _saved_path
    sys.argv[:] = _saved_argv


def symbols(text):
    result = {name: int(address, 16) for name, address in
              re.findall(r'^(\S+)\s+0x([0-9a-fA-F]+)$', text, re.M)}
    result.update(usb_control_process_received_packet=result['L1d9c'],
                  bootloader_poll_begin=result['L1d3a'],
                  bootloader_start_application=result['L1eac'])
    return result


@pytest.fixture(scope='module')
def builds(tmp_path_factory):
    meta = json.loads((ROOT / 'firmware/manifest.json').read_text())
    current_body = tmp_path_factory.mktemp('phy-current') / 'current.bin'
    body_bytes = (ROOT / 'firmware/bootloader.bin').read_bytes()
    assert hashlib.sha256(body_bytes).hexdigest() == meta['sha256_body']
    current_body.write_bytes(body_bytes)
    current = {'name': 'current', 'start': int(meta['bootloader_start'], 16),
               'bin': current_body, 'o': None,
               'symbols': symbols((ROOT / 'firmware/symbols.txt').read_text())}
    with zipfile.ZipFile(ARCHIVE) as archive:
        baseline_symbols = symbols(archive.read(ARCHIVE_ROOT + 'symbols.txt').decode())
        full = archive.read(ARCHIVE_ROOT + 'ISP_FULL_8192_19C0_PASS15.bin')
        body = full[0x19c0:0x19c0 + 1580]
    baseline_body = tmp_path_factory.mktemp('phy-baseline') / 'pass15.bin'
    baseline_body.write_bytes(body)
    baseline = {'name': 'pass15', 'start': 0x19c0, 'bin': baseline_body, 'o': None,
                'symbols': baseline_symbols}
    return baseline, current


def crc16(payload):
    value = 0xffff
    for byte in payload:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xa001 if value & 1 else 0)
    return ((~value) & 0xffff).to_bytes(2, 'little')


def token(pid, address=0, endpoint=0):
    field = address | endpoint << 7
    crc = 0x1f
    for bit in range(11):
        mix = (crc ^ (field >> bit)) & 1
        crc = (crc >> 1) ^ (0x14 if mix else 0)
    field |= ((~crc) & 0x1f) << 11
    return bytes([pid, field & 0xff, field >> 8])


def wire_levels(packet):
    """SYNC, stuffed LSB-first bytes and two SE0 bits followed by J."""
    bits = [(0x80 >> bit) & 1 for bit in range(8)]
    ones = 0
    for byte in packet:
        for bit in range(8):
            value = (byte >> bit) & 1
            bits.append(value)
            ones = ones + 1 if value else 0
            if ones == 6:
                bits.append(0)
                ones = 0
    state, levels = 2, []
    for bit in bits:
        if not bit:
            state ^= 6
        levels.append(state)
    return levels + [0, 0, 2]


class HostPins(dict):
    """A rational 32/3-cycle bit clock sampled at instruction entry."""
    def __init__(self, cpu, levels, start):
        super().__init__({0x09: 2, 0x0a: 0, 0x0b: 2, 0x1b: 0})
        self.cpu, self.levels, self.start = cpu, levels, start

    def get(self, address, default=0):
        if address == 0x09:
            index = ((self.cpu.t - self.start) * 3) // 32
            return self.levels[index] if 0 <= index < len(self.levels) else 2
        return super().get(address, default)


def make_cpu(build, memory=None, registers=None, entry='USB_handler'):
    cpu = Timed(build, {'memory': memory if memory is not None else bytearray(0x300),
                        'registers': registers if registers is not None else [0] * 32})
    cpu.pc = cpu.labels[entry]
    cpu.io.update({0x09: 2, 0x0a: 0, 0x0b: 2, 0x1b: 0})
    return cpu


def receive(build, packet, phase, *, prior_token=0xe1, tx_length=0x5a, address=0):
    memory = bytearray(0x300)
    memory[0x114] = prior_token
    memory[0x10f] = tx_length
    memory[0x10c] = address << 1
    payload = bytes(range(8 if tx_length == 0x5a else tx_length - 4))
    tx_packet = bytes([0x4b]) + payload + crc16(payload)
    memory[0x101:0x101 + len(tx_packet)] = tx_packet
    cpu = make_cpu(build, memory)
    levels = wire_levels(packet)
    cpu.io = HostPins(cpu, levels, phase)
    for _ in range(6000):
        if cpu.pc in (cpu.labels['L1be8'], cpu.labels['L1bf0']):
            break
        instruction = cpu.step()
        # This independent interpreter's generic SBI is not a W1C peripheral.
        if instruction.op == 'sbi' and instruction.operands.startswith('0x1b,'):
            cpu.io[0x1b] = 0
    else:
        raise AssertionError('Full RX/TX waveform exceeded its instruction bound')
    assert bytes(cpu.m[0x116:0x116 + len(packet)]) == packet
    sop = next((time for time, port, value in cpu.bus_events
                if port == 0x0b and value & 6 == 4), None)
    # Keep thirds of CPU cycles exact, avoiding float boundary decisions.
    eop_end_thirds = phase * 3 + (len(levels) - 1) * 32
    delay_thirds = None if sop is None else sop * 3 - eop_end_thirds
    return cpu, sop, delay_thirds


def assert_turnaround(delay_thirds):
    assert delay_thirds is not None
    # Two bits <= delay <= 6.5 bits at 16 MHz / 1.5 Mbps.
    assert 64 <= delay_thirds <= 208, delay_thirds


def relative_waveform(cpu, sop):
    # Packet waveform through the final release, independent of dispatcher delay.
    return [(time - sop, port, value) for time, port, value in cpu.bus_events
            if time >= sop]


def test_full_rx_sampler_data_ack_and_turnaround(builds):
    baseline, current = builds
    for phase in range(-15, 1):
        for length in range(9):
            modes = [(0x4b, (0x00, 0xff, 0x55, 0xaa, 0x3f, 0xfc, 0x7e, 0x81))]
            if length:
                modes.append((0xc3, (0x00, 0xff)))
            for pid, values in modes:
                for value in values:
                    payload = bytes([value]) * length
                    packet = bytes([pid]) + payload + crc16(payload)
                    old, old_sop, old_delay = receive(baseline, packet, phase)
                    new, new_sop, new_delay = receive(current, packet, phase)
                    assert_turnaround(old_delay)
                    assert_turnaround(new_delay)
                    assert relative_waveform(new, new_sop) == relative_waveform(old, old_sop)
                    if length:
                        assert new.m[0x112] == len(packet)
                        assert new.m[0x10d] == 0xe1
                    else:
                        assert new.m[0x112] == 3  # Validated status OUT is published for foreground completion.
                        assert new.m[0x10d] == 0xe1


def test_full_in_token_nak_and_data_response_turnaround(builds):
    baseline, current = builds
    for phase in range(-15, 1):
        for address in (0, 17, 127):
            for length in (0x5a, *range(4, 13)):
                packet = token(0x69, address)
                old, old_sop, old_delay = receive(baseline, packet, phase,
                                                tx_length=length, address=address)
                new, new_sop, new_delay = receive(current, packet, phase,
                                                tx_length=length, address=address)
                assert_turnaround(old_delay)
                assert_turnaround(new_delay)
                assert relative_waveform(new, new_sop) == relative_waveform(old, old_sop)


def test_random_tx_nrzi_stuffing_and_eop_match_archived_engine(builds):
    baseline, current = builds
    randomizer = random.Random(0x1688a)
    for _ in range(600):
        memory = bytearray(randomizer.getrandbits(8) for _ in range(0x300))
        registers = [randomizer.getrandbits(8) for _ in range(32)]
        registers[1] = 0
        registers[18] = 0x80
        registers[19] = randomizer.choice([2, 4, 5, 8, 12])
        registers[28:30] = [1, 1]
        registers[30:32] = [0, 1]
        waveforms = []
        for build in (baseline, current):
            cpu = make_cpu(build, memory, registers, entry='L1c56')
            for _ in range(5000):
                if cpu.pc == cpu.labels['L1be8']:
                    break
                instruction = cpu.step()
                if instruction.op == 'sbi' and instruction.operands.startswith('0x1b,'):
                    cpu.io[0x1b] = 0
            else:
                raise AssertionError('TX bit engine exceeded its instruction bound')
            waveforms.append((cpu.t, cpu.bus_events))
        assert waveforms[0] == waveforms[1]


def test_rx_sampler_and_tx_bits_have_only_reviewed_instruction_changes(builds):
    baseline, current = builds
    old_bytes, new_bytes = [build['bin'].read_bytes() for build in builds]
    for build, body in zip(builds, (old_bytes, new_bytes)):
        build['_body'] = body
    old = baseline['symbols']
    new = current['symbols']
    assert old_bytes[old['usb_crc16_append']-baseline['start']:old['USB_handler']-baseline['start']] == new_bytes[new['usb_crc16_append']-current['start']:new['USB_handler']-current['start']]
    decoder = Timed.step.__globals__['dec']

    def decode_range(build, begin, end, external_labels):
        decoder.START = build['start']
        decoder.raw = build['_body']
        pc, result = begin, []
        while pc < end:
            instruction = decoder.decode(pc)
            assert not instruction.unknown
            target = instruction.target
            if target is not None:
                if begin <= target < end:
                    target = ('internal', target-begin)
                else:
                    names = [name for name in external_labels
                             if target == build['symbols'][name]]
                    assert len(names) == 1, (instruction.op, hex(target))
                    target = ('external', names[0])
            result.append((pc, instruction, target))
            pc += instruction.size
        assert pc == end
        return result

    # New classifier/ACK code relocates the abort/commit destinations, but
    # sampler instructions and the destinations' identities must stay intact.
    samplers = [decode_range(build, build['symbols']['USB_handler'],
                             build['symbols']['L1baa'], ['L1bf0', 'L1be4', 'L1baa'])
                for build in builds]
    assert len(samplers[0]) == len(samplers[1])
    for (_, a, a_target), (_, b, b_target) in zip(*samplers):
        assert (a.op, a.operands, a_target) == (b.op, b.operands, b_target)

    transmitters = [decode_range(build, build['symbols']['L1c30'],
                                 build['symbols']['L1cc2'] + 12, ['L1be8'])
                    for build in builds]
    old_code, new_code = transmitters
    assert len(old_code) == len(new_code)
    for (old_pc, a, old_target), (new_pc, b, new_target) in zip(old_code, new_code):
        if a.op == 'std' and a.operands == 'Z+12, r17':
            # Address is committed only after status ACK. Preserve the old
            # two-cycle EOP preparation slot with an inert one-word jump.
            if b.op == 'rjmp':
                assert b.size == 2 and b.target == new_pc + 2
                continue
        assert (a.op, a.operands, old_target) == (b.op, b.operands, new_target)


ACK_WINDOW = 0x012c


def transmit_to_ack_window(build):
    memory, registers = bytearray(0x300), [0] * 32
    registers[31] = 1
    payload = bytes(range(8))
    memory[0x101:0x10c] = bytes([0x4b]) + payload + crc16(payload)
    memory[0x10f] = 12
    cpu = make_cpu(build, memory, registers, entry='L1c14')
    for _ in range(5000):
        if cpu.pc == cpu.labels['L1be8']:
            break
        instruction = cpu.step()
        if instruction.op == 'sbi' and instruction.operands.startswith('0x1b,'):
            cpu.io[0x1b] = 0
    else:
        raise AssertionError('IN transmission did not reach its ACK wait')
    end_j = [time for time, port, value in cpu.bus_events
             if port == 0x0b and value & 6 == 2][-1]
    assert cpu.m[ACK_WINDOW] == 1
    # Entered inside the handler: provide the saved R19 frame consumed at return.
    cpu.push_stack = [0x73]
    return cpu, end_j


class AckSOPFlag(dict):
    def __init__(self, cpu, end_j, arrival):
        super().__init__(cpu.io)
        self.cpu, self.end_j, self.arrival = cpu, end_j, arrival

    def get(self, address, default=0):
        if address == 0x1b:
            return 4 if self.arrival is not None and self.cpu.t-self.end_j >= self.arrival else 0
        return super().get(address, default)


def test_ack_sop_timeout_occurs_between_sixteen_and_eighteen_bits(builds):
    current = builds[1]
    accepted, rejected = [], []
    for arrival in (None, *range(22, 210)):
        cpu, end_j = transmit_to_ack_window(current)
        cpu.io = AckSOPFlag(cpu, end_j, arrival)
        for _ in range(1000):
            if cpu.pc in (cpu.labels['L1abe'], cpu.labels['L1bf0']):
                break
            cpu.step()
        else:
            raise AssertionError('ACK SOP wait did not terminate')
        if arrival is None:
            assert cpu.m[ACK_WINDOW] == 0
            assert 512 <= (cpu.t-end_j)*3 < 576
        elif cpu.m[ACK_WINDOW]:
            accepted.append(arrival)
        else:
            rejected.append(arrival)
    assert accepted == list(range(22, max(accepted)+1))
    assert min(rejected) == max(accepted)+1
    # A SOP at 170 cycles must remain eligible; by 192 cycles it must expire.
    assert 512 <= min(rejected)*3 < 576


class AckWaveformPins(dict):
    """Latch real host D+ edges until an emulated PCIFR W1C operation."""
    def __init__(self, cpu, end_j, arrival):
        super().__init__(cpu.io)
        self.cpu, self.start = cpu, end_j+arrival
        self.levels = wire_levels(bytes([0xd2]))
        self.cleared_thirds = cpu.t*3
        previous = 2
        self.edges = []
        for index, level in enumerate(self.levels):
            if (previous ^ level) & 4:
                self.edges.append(self.start*3+index*32)
            previous = level

    def get(self, address, default=0):
        if address == 0x09:
            index = ((self.cpu.t-self.start)*3)//32
            return self.levels[index] if 0 <= index < len(self.levels) else 2
        if address == 0x1b:
            return 4 if any(self.cleared_thirds < edge <= self.cpu.t*3
                            for edge in self.edges) else 0
        return super().get(address, default)

    def clear(self):
        self.cleared_thirds = self.cpu.t*3


def test_timely_ack_sop_can_finish_decoding_after_the_sop_deadline(builds):
    current = builds[1]
    for arrival in (22, 80, 160, 170, 192, 200):
        cpu, end_j = transmit_to_ack_window(current)
        cpu.io = AckWaveformPins(cpu, end_j, arrival)
        entered_ack = False
        for _ in range(6000):
            if cpu.pc == cpu.labels['usb_host_ack']:
                entered_ack = True
            if cpu.pc == cpu.labels['L1bf0']:
                break
            if entered_ack and cpu.pc == cpu.labels['L1be8']:
                break
            instruction = cpu.step()
            if instruction.op == 'sbi' and instruction.operands.startswith('0x1b,'):
                cpu.io.clear()
        else:
            raise AssertionError('Injected ACK did not complete or time out')
        assert cpu.m[ACK_WINDOW] == 0
        if arrival <= 170:
            assert entered_ack
            assert cpu.m[0x10f] == 0x5a
            assert cpu.t-end_j > 192  # Deadline applies to SOP, not ACK completion.
        else:
            assert cpu.m[0x10f] == 12
