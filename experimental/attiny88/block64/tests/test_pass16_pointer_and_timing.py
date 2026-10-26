"""Separate the safe WIP pointer reuse from its timing-changing PHY edit.

Execute archived and current AVR words; no board access or electrical USB
claims. The archive is immutable provenance, not an instruction source.
"""
from pathlib import Path
import random
import re
import zipfile

import pytest
import avr_sim
from avr_sim import CPU, MEM_BUFFER, MEM_EXPECT_PID, MEM_INDEX, MEM_REMAIN, MEM_STATE, MEM_TYPE, ST_RECEIVE


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT.parents[2] / 'docs/attiny88-block64-history/archives/Micronucleus_ATtiny88_Block64_ALL_CODE_AGENT_HANDOFF_2026-10-26.zip'
ARCHIVE_ROOT = 'Micronucleus_ATtiny88_Block64_COMPLETE_HANDOFF_2026-10-26/'


@pytest.fixture(scope='module')
def images():
    """Resolve each image's own symbols, without trusting copied version text."""
    result = {}
    with zipfile.ZipFile(ARCHIVE) as archive:
        for name, directory in [('pass15', '02_CURRENT_PASS15_EXPERIMENTAL'),
                                ('wip16', '03_UNVERIFIED_WIP_PASS16')]:
            prefix = ARCHIVE_ROOT + directory + '/firmware/'
            text = archive.read(prefix + 'symbols.txt').decode()
            labels = {name: int(address, 16) for name, address in
                      re.findall(r'^(\S+)\s+0x([0-9a-fA-F]+)$', text, re.M)}
            result[name] = (archive.read(prefix + 'ISP_FULL_8192_19C0_PASS15.bin'), labels)
    # Read the unpadded assembled image so future output-name changes do not
    # silently select a stale generated ISP artifact.
    raw = (ROOT / 'build/block64.full.bin').read_bytes()
    image = bytearray(b'\xff' * 8192)
    image[avr_sim.BOOT:len(raw)] = raw[avr_sim.BOOT:]
    result['current'] = (bytes(image), avr_sim.syms())
    return result


@pytest.fixture
def cpu_factory(images, monkeypatch):
    # CPU construction otherwise shells out for an unchanged symbol table
    # on every vector. Keep distinct maps for all three real images.
    monkeypatch.setattr(avr_sim, 'syms', lambda: images['current'][1])

    def make(name):
        image, labels = images[name]
        cpu = CPU(image=image)
        cpu.labels = dict(labels)
        return cpu

    return make


def crc16(payload):
    crc = 0xffff
    for byte in payload:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xa001 if crc & 1 else 0)
    return ((~crc) & 0xffff).to_bytes(2, 'little')


def accept(cpu, payload, corrupt, previous, kind):
    cpu.mem[MEM_STATE] = ST_RECEIVE
    cpu.mem[MEM_TYPE] = kind
    cpu.mem[MEM_REMAIN] = 64 - previous
    cpu.mem[MEM_INDEX] = previous
    cpu.mem[MEM_EXPECT_PID] = 0x4b
    cpu.mem[MEM_BUFFER:MEM_BUFFER + 64] = bytes(range(64))
    cpu.mem[0x0116] = 0x4b
    cpu.mem[0x0117:0x0117 + len(payload)] = payload
    trailer = bytearray(crc16(payload))
    if corrupt:
        trailer[0] ^= 0x40
    cpu.mem[0x0117 + len(payload):0x0119 + len(payload)] = trailer
    cpu.r[24] = len(payload)
    cpu.run_from('block_out_packet', stop_at=['L1df8'], count=1800, execute_ret=True)
    return (bytes(cpu.mem), tuple(cpu.r), cpu.sreg, tuple(cpu.stack),
            tuple(cpu.spm_oplog), bytes(cpu.eeprom), tuple(sorted(cpu.io.items())))


def test_crc_pointer_reuse_matches_original_for_every_constant_and_length(cpu_factory):
    """Cover every legal packet size and constant byte plus corrupt trailers."""
    cases = [(bytes([value]) * length, False, 0, 0)
             for length in range(1, 9) for value in range(256)]
    randomizer = random.Random(0x16c0)
    for _ in range(256):
        length = randomizer.randrange(1, 9)
        cases.append((bytes(randomizer.randrange(256) for _ in range(length)),
                      bool(randomizer.randrange(2)), randomizer.randrange(0, 8) * 8,
                      randomizer.randrange(2)))
    for payload, corrupt, previous, kind in cases:
        old = cpu_factory('pass15')
        new = cpu_factory('current')
        assert accept(new, payload, corrupt, previous, kind) == accept(old, payload, corrupt, previous, kind)
        # Pointer reuse saves one cycle; sharing the CRC gate with SETUP
        # adds a seven-cycle RCALL/RET outside the timed PHY path.
        assert new.cycles == old.cycles + 6, (len(payload), corrupt, previous, kind)


def flag_wait(cpu, arrival):
    """Timestamp I/O reads at instruction entry; PCIF2 stays set once raised."""
    cpu.r[28] = 10
    reads = []

    def read_io(address):
        assert address == 0x1b
        # The supplied CPU increments the first cycle before invoking I/O.
        at = cpu.cycles - 1
        reads.append(at)
        return 4 if arrival is not None and at >= arrival else 0

    cpu.read_io = read_io
    cpu.run_from('L1bda', stop_at=['L1be4'], count=100)
    return tuple(reads), cpu.cycles, cpu.r[28]


def test_phy_and_crc_remain_byte_identical_to_pass15(images):
    for start, end, count in [('usb_crc16_append', 'USB_handler', 44),
                              ('USB_handler', 'main', 508)]:
        old, labels = images['pass15']
        current, now = images['current']
        assert current[now[start]:now[end]] == old[labels[start]:labels[end]]
        assert now[end] - now[start] == count


def test_all_flag_arrival_phases_preserve_wait_timing_and_reject_wip(cpu_factory):
    """A smaller instruction sequence does not preserve the polling window."""
    for arrival in [None, *range(61)]:
        reference = flag_wait(cpu_factory('pass15'), arrival)
        assert flag_wait(cpu_factory('current'), arrival) == reference
        assert flag_wait(cpu_factory('wip16'), arrival) != reference

    assert flag_wait(cpu_factory('pass15'), None) == (tuple(range(0, 60, 6)), 59, 0)
    assert flag_wait(cpu_factory('wip16'), None) == (tuple(range(0, 50, 5)), 49, 0)
    assert flag_wait(cpu_factory('pass15'), 0) == ((0,), 4, 10)
    assert flag_wait(cpu_factory('wip16'), 0) == ((0,), 3, 10)
    for arrival in range(46, 55):
        assert flag_wait(cpu_factory('pass15'), arrival)[2] != 0
        assert flag_wait(cpu_factory('wip16'), arrival)[2] == 0
