"""Legacy request1/3 cursor behavior from the exact public 1274-byte image.

No saved board dumps are used. The compiler and local historical Git commit
must be available, as for the other instruction-level firmware tests.
"""
from pathlib import Path
import sys

import pytest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'tools'))
import audit_legacy_cursor as legacy


@pytest.fixture(scope='module')
def historical(tmp_path_factory):
    manifest, body = legacy.build_historical(tmp_path_factory.mktemp('legacy-cursor'))
    with legacy.legacy_model(manifest, body) as create:
        yield manifest, body, create


def test_historical_rebuild_is_pinned_to_the_deployed_1274_bytes(historical):
    manifest, body, _ = historical
    assert manifest['historical_commit'] == legacy.COMMIT
    assert manifest['body_sha256'] == legacy.EXPECTED_SHA256
    assert len(body) == 1274


def test_disconnect_countdown_exit_initializes_the_persistent_cursor(historical):
    _, _, create = historical
    cpu = create()
    cpu.r[4], cpu.r[5], cpu.r[3] = 0xA5, 0x5A, 0x40
    cpu.r[24], cpu.r[25], cpu.r[18] = 1, 0, 1
    cpu.run_from('usb_disconnect_delay_inner',
                 stop_at=['bootloader_poll_begin'], count=60, execute_ret=True)
    assert legacy.cursor(cpu) == 0 and cpu.r[3] == 0 and cpu.r[1] == 0
    assert not cpu.spm_oplog


def test_first_set_address_is_ignored_and_one_prime_does_not_commit(historical):
    _, _, create = historical
    cpu = create()
    before = bytes(cpu.flash)
    assert legacy.command(cpu, 1, 64, legacy.SCRATCH_START) == 0
    assert not cpu.spm_oplog
    assert legacy.command(cpu, 3, 0x1234, 0x5678) == 4
    assert cpu.r[3] == 0
    assert [event[0] for event in cpu.spm_oplog] == ['load', 'load']
    assert bytes(cpu.flash) == before
    assert legacy.command(cpu, 1, 64, legacy.SCRATCH_START) == legacy.SCRATCH_START
    assert cpu.spm_buffer == b'\xff' * 64 and not cpu._spm_loaded_words


def test_request1_prime_request1_is_safe_for_all_supported_idle_cursors(historical):
    assert legacy.prove_cursor_selection(historical[2]) == 1729


def test_only_eight_previously_erased_scratch_pages_are_written(historical):
    assert legacy.prove_erased_page_writes(historical[2]) == 8


def test_omitting_prime_queues_page_zero_instead_of_requested_scratch(historical):
    _, _, create = historical
    cpu = create()
    assert legacy.command(cpu, 1, 64, legacy.SCRATCH_START) == 0
    legacy.queue_page(cpu, 0, bytes(range(64)))
    assert legacy.cursor(cpu) == 64 and cpu.r[3] == 0x40
    # Stop before executing the dangerous queued SPM. This assertion shows
    # why a mock that accepts the first request1 would miss the regression.
    assert not any(event[0] == 'write' for event in cpu.spm_oplog)


def test_legacy_has_no_erased_page_check_so_non_erased_writes_are_unsupported(historical):
    _, _, create = historical
    cpu = create()  # Synthetic A5 target is deliberately not erased.
    legacy.select_scratch(cpu, legacy.SCRATCH_START)
    legacy.queue_page(cpu, legacy.SCRATCH_START, bytes(range(64)))
    assert cpu.r[3] == 0x40  # The legacy firmware itself did not reject it.
    with pytest.raises(AssertionError, match='Flash Page Write requires an erased page'):
        legacy.execute_pending(cpu)


def test_a_pending_old_command_is_not_assumed_safe_to_retry(historical):
    _, _, create = historical
    cpu = create()
    cpu.r[3] = 0x40
    with pytest.raises(AssertionError, match='no pending old command'):
        legacy.select_scratch(cpu, legacy.SCRATCH_START)
