"""Execute the guarded benchmark's actual linked access/NVM instructions.

The NVM peripheral model checks address and enable-window behavior. It is
not an electrical test and does not establish measured programming speed.
"""
from pathlib import Path
import hashlib
import json
import os
import sys

import pytest

BASE = Path(__file__).resolve().parents[1]
PROJECT = BASE.parents[1]
sys.path.insert(0, str(PROJECT / 'tests'))
import avr_sim as sim


@pytest.fixture(scope='module')
def benchmark():
    path = Path(os.environ.get('MEMORY_BENCHMARK_MANIFEST', BASE / 'build/guarded-v2/manifest.json'))
    manifest = json.loads(path.read_text())
    body = (path.parent / manifest['body_file']).read_bytes()
    assert hashlib.sha256(body).hexdigest() == manifest['sha256_body']
    image = (path.parent / manifest['full_image_file']).read_bytes()
    patch = pytest.MonkeyPatch()
    patch.setattr(sim, 'BOOT', manifest['image_address'])
    patch.setattr(sim, 'syms', lambda: manifest['symbols'].copy())
    yield manifest, image
    patch.undo()


def cpu_for(benchmark, strict=False):
    _, image = benchmark
    return sim.CPU(image=image, strict_nvm=strict,
                   selfprgen_fuse_programmed=True if strict else None)


def setup_mutation(cpu, operation, address, length, memory=0, request_type=0x40):
    cpu.set_setup(operation, address, length, memory, request_type)
    cpu.run_from('block_vendor_dispatch', stop_at=['L1df8'], execute_ret=True, count=700)
    return cpu.mem[sim.MEM_STATE]


def test_layout_and_explicit_benchmark_identity(benchmark):
    manifest, image = benchmark
    assert image[0x0802:0x0808] == bytes([0x1f, 0xfc, 64, 64, 0x33, 0x83])
    assert manifest['image_address'] == 0x0800
    assert manifest['executable_end'] <= 0x1600
    assert manifest['symbols']['stream_crc_table_low'] == 0x1600
    assert manifest['symbols']['stream_crc_table_high'] == 0x1700
    assert manifest['flash_mutation_start'] == 0x1800
    assert manifest['flash_mutation_end_exclusive'] == 0x1a00
    assert manifest['protected_boot_address'] == 0x1b00
    assert manifest['run_request_enabled'] is False
    assert manifest['inactivity_application_jump_enabled'] is False
    assert image[0x1800:] == b'\xff' * (8192 - 0x1800)


def test_every_flash_page_write_and_erase_address(benchmark):
    # All 1024 possible aligned 16-bit addresses, including wraparound and
    # every part of the app, CRC tables, reset postscript and old loader.
    required = {0x07ff, 0x0800, 0x15c0, 0x1600, 0x17c0, 0x1800,
                0x19c0, 0x1a00, 0x1ac0, 0x1b00, 0xffff}
    addresses = set(range(0, 65536, 64)) | required | set(range(0x1800, 0x1a00))
    for operation in (0x11, 0x14):
        for address in sorted(addresses):
            cpu = cpu_for(benchmark)
            state = setup_mutation(cpu, operation, address, 64 if operation == 0x11 else 0)
            allowed = 0x1800 <= address < 0x1a00 and address % 64 == 0
            expected = sim.ST_RECEIVE if operation == 0x11 else sim.ST_FLASH_WAIT_PREP
            assert (state == expected) == allowed, (operation, hex(address), state)
            assert not cpu.spm_oplog and not cpu.eeprom_oplog


@pytest.mark.parametrize('length', [0, 1, 63, 65, 255, 256, 0xffff])
def test_partial_or_oversized_flash_write_rejected(benchmark, length):
    cpu = cpu_for(benchmark)
    assert setup_mutation(cpu, 0x11, 0x1800, length) == sim.ST_ERROR


@pytest.mark.parametrize('length', [1, 64, 255, 256, 0xffff])
def test_erase_requires_zero_usb_length(benchmark, length):
    cpu = cpu_for(benchmark)
    assert setup_mutation(cpu, 0x14, 0x1800, length) == sim.ST_ERROR


def test_every_eeprom_address_length_pair_and_erase_rejection(benchmark):
    for address in range(66):
        for length in range(66):
            cpu = cpu_for(benchmark)
            state = setup_mutation(cpu, 0x11, address, length, 1)
            allowed = 1 <= length <= 64 and address + length <= 64
            assert (state == sim.ST_RECEIVE) == allowed, (address, length, state)
    for address in (0, 1, 63, 64, 0xff, 0xffff):
        cpu = cpu_for(benchmark)
        assert setup_mutation(cpu, 0x14, address, 0, 1) == sim.ST_ERROR


@pytest.mark.parametrize('operation', [0x11, 0x14])
@pytest.mark.parametrize('memory', [2, 0x100, 0xffff])
def test_unknown_memory_types_rejected(benchmark, operation, memory):
    cpu = cpu_for(benchmark)
    assert setup_mutation(cpu, operation, 0x1800, 64 if operation == 0x11 else 0, memory) == sim.ST_ERROR


def test_run_and_wrong_request_direction_rejected(benchmark):
    for request_type in (0x00, 0x40, 0x80, 0xc0):
        cpu = cpu_for(benchmark)
        assert setup_mutation(cpu, 0x13, 0, 0, request_type=request_type) != sim.ST_RUN
    for operation in (0x11, 0x14):
        cpu = cpu_for(benchmark)
        assert setup_mutation(cpu, operation, 0x1800, 64 if operation == 0x11 else 0,
                              request_type=0xc0) == sim.ST_ERROR


def test_read_all_flash_and_eeprom_bounds(benchmark):
    for memory, end in ((0, 8192), (1, 64)):
        for address, length in ((0, 1), (0, 64), (end - 64, 64), (end - 1, 1),
                                (end, 1), (end - 63, 64), (0xffff, 64), (0, 0)):
            cpu = cpu_for(benchmark)
            cpu.set_setup(0x10, address, length, memory, 0xc0)
            cpu.run_from('block_validate_range', count=300, execute_ret=True)
            expected = 1 <= length <= 64 and address + length <= end
            assert cpu.flag(0) == expected, (memory, address, length)
            if expected:
                assert cpu.r[16] == memory
                assert cpu.r[22:25] == [address & 255, address >> 8, length]


def authorize_flash_worker(cpu, address, erase):
    cpu.mem[sim.MEM_STATE] = sim.ST_SPM_WAIT_SENT
    cpu.mem[0x12d] = 0x81  # Existing owner plus actual-status-ACK contract.
    cpu.mem[sim.MEM_PROGRESS] = int(erase)
    cpu.mem[sim.MEM_ADDR_LO] = address & 255
    cpu.mem[sim.MEM_ADDR_HI] = address >> 8
    cpu.r[28:30] = [0, 1]


def test_in_progress_nvm_and_unacknowledged_status_do_not_authorize_spm(benchmark):
    for operation in (0x11, 0x14):
        cpu = cpu_for(benchmark, strict=True)
        cpu.io[0x1f] = 2  # EEPE busy interlock, before any data/address update.
        assert setup_mutation(cpu, operation, 0x1800, 64 if operation == 0x11 else 0) == sim.ST_ERROR
        assert not cpu.spm_oplog and not cpu.eeprom_oplog
    for state, owner in ((sim.ST_FLASH_WAIT_PREP, 0x81),
                         (sim.ST_SPM_WAIT_SENT, 0), (sim.ST_SPM_WAIT_SENT, 1),
                         (sim.ST_SPM_WAIT_SENT, 0x82)):
        cpu = cpu_for(benchmark, strict=True)
        authorize_flash_worker(cpu, 0x1800, True)
        cpu.mem[sim.MEM_STATE], cpu.mem[0x12d] = state, owner
        cpu.run_from('block_spm_after_quiet', execute_ret=True, count=300)
        assert not cpu.spm_oplog and not cpu.nvm_events


def test_strict_spm_erases_and_writes_only_the_eight_scratch_pages(benchmark):
    cpu = cpu_for(benchmark, strict=True)
    before = bytes(cpu.flash)
    for address in range(0x1800, 0x1a00, 64):
        pattern = bytes((address + index * 37) & 255 for index in range(64))
        authorize_flash_worker(cpu, address, True)
        cpu.run_from('block_spm_after_quiet', execute_ret=True, count=2000)
        assert cpu.flash[address:address + 64] == b'\xff' * 64
        cpu.mem[0x140:0x180] = pattern
        authorize_flash_worker(cpu, address, False)
        cpu.run_from('block_spm_after_quiet', execute_ret=True, count=3000)
        assert cpu.flash[address:address + 64] == pattern
        assert cpu.r[1] == 0
    assert cpu.flash[:0x1800] == before[:0x1800]
    assert cpu.flash[0x1a00:] == before[0x1a00:]
    assert all(0x1800 <= entry[1] < 0x1a00 for entry in cpu.spm_oplog)


def test_final_spm_guard_stops_bad_internal_state_before_any_trigger(benchmark):
    for address in (0, 0x0800, 0x17c0, 0x1a00, 0x1ac0, 0x1b00, 0xffff):
        for erase in (True, False):
            cpu = cpu_for(benchmark, strict=True)
            authorize_flash_worker(cpu, address, erase)
            cpu.run_from('block_spm_after_quiet', stop_at=['benchmark_nvm_fault'],
                         execute_ret=True, count=400)
            assert cpu.pc == cpu.labels['benchmark_nvm_fault']
            assert not cpu.spm_oplog and not cpu.nvm_events


def test_eeprom_worker_has_timely_enable_and_final_address_guard(benchmark):
    cpu = cpu_for(benchmark, strict=True)
    expected = bytes((index * 19 + 7) & 255 for index in range(64))
    cpu.mem[sim.MEM_STATE] = sim.ST_WRITE_EEPROM
    cpu.mem[sim.MEM_ADDR_LO] = 0
    cpu.mem[sim.MEM_INDEX] = 64
    cpu.mem[0x140:0x180] = expected
    for _ in range(65):
        cpu.r[28:30] = [0, 1]
        cpu.r[18] = cpu.mem[sim.MEM_STATE]
        cpu.run_from('block_memory_service', execute_ret=True, count=400)
        cpu.advance_nvm_cycles(sim.MODEL_EEPROM_PROGRAM_CYCLES)
    assert bytes(cpu.eeprom) == expected
    assert len(cpu.eeprom_oplog) == 64
    assert cpu.r[1] == 0
    bad = cpu_for(benchmark, strict=True)
    bad.mem[sim.MEM_STATE] = sim.ST_WRITE_EEPROM
    bad.mem[sim.MEM_ADDR_LO] = 64
    bad.mem[sim.MEM_INDEX] = 1
    bad.r[18] = sim.ST_WRITE_EEPROM
    bad.run_from('block_memory_service', stop_at=['benchmark_nvm_fault'], execute_ret=True, count=400)
    assert bad.pc == bad.labels['benchmark_nvm_fault']
    assert not bad.eeprom_oplog and not bad.nvm_events


def test_usb_waveform_engine_is_unchanged_except_relocated_bookkeeping_jumps(benchmark):
    manifest, image = benchmark
    reference = BASE.parent / 'streaming_crc16/build/streaming-v2'
    old = json.loads((reference / 'manifest.json').read_text())
    old_image = (reference / old['full_image_file']).read_bytes()
    first, last = old['symbols']['usb_crc16_append'], old['symbols']['main']
    assert manifest['symbols']['usb_crc16_append'] == first
    assert manifest['symbols']['main'] == last
    address = first
    while address < last:
        sim.D.START, sim.D.raw = 0, old_image
        before = sim.D.decode(address)
        sim.D.START, sim.D.raw = 0, image
        after = sim.D.decode(address)
        assert (before.op, before.size) == (after.op, after.size)
        if before.target is None:
            assert before.operands == after.operands
        elif first <= before.target < last:
            assert before.target == after.target
        else:
            names = [name for name, value in old['symbols'].items()
                     if value == before.target and name in manifest['symbols']]
            assert any(manifest['symbols'][name] == after.target for name in names)
        address += before.size
    assert address == last
