"""Run the maintained USB regressions against one composed no-LED receiver.

This selects linked firmware bytes only. Test fixtures, GPIO execution, timing
bounds and expected protocol behavior are unchanged. No device is accessed.
"""
import argparse
import importlib
import json
import os
import time
import traceback

from tests35 import ep0_model as h
from tests35 import phy_model as p


CHECKS = (
    ('test_avr_model', 'test'),
    ('test_avr_cycles', 'test'),
    ('test_ep0_standard', 'test'),
    ('test_ep0_status', 'test'),
    ('test_out_response_timing', 'test'),
    ('test_stall_followup', 'test'),
    ('test_setup_pending_marker', 'test'),
    ('test_ep0_zero_direction', 'test'),
    ('test_ep0_reply_fragments', 'test'),
    ('test_tx_crc_payloads', 'test'),
    ('test_ep0_read_completion', 'test'),
    ('test_out_completion_lifetime', 'test'),
    ('test_vendor_host_contract', 'test'),
    ('test_sequential_wire', 'check'),
    ('test_tx_digital', 'test'),
    ('test_ep0_reset', 'test'),
    ('test_startup_state', 'test'),
    ('test_ep0_shadow', 'test'),
    ('test_ep0_ack_timeout', 'test'),
    ('test_ep0_token_timeout', 'test'),
    ('test_dribble_deadlines', 'test'),
    ('test_ep0_polling', 'test'),
    ('test_rx_late_entry', 'test'),
    ('test_ep0_failed_sync', 'test'),
    ('test_rx_resync', 'test'),
    ('test_token_crc5', 'test'),
    ('test_pid_admission', 'test'),
    ('test_token_framing_wire', 'test'),
    ('test_rx_context_restore', 'test'),
    ('test_ack_followup', 'test'),
    ('test_data_framing', 'test'),
    ('test_token_crossover_admission', 'test'),
    ('test_rx_jitter_spec', 'test'),
    ('test_rx_aperiodic', 'test'),
    ('test_rx_eop_matrix', 'test'),
)
RAW_CHECKS = ('test_receive', 'test_partial', 'test_stuff_errors', 'test_tokens_and_eop')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='variants/combined_rx')
    parser.add_argument('--boot', type=lambda value: int(value, 0), default=0x1a00)
    parser.add_argument('--exhaustive', action='store_true')
    args = parser.parse_args()
    if args.exhaustive:
        os.environ['USB_PHY_EXHAUSTIVE'] = '1'

    source_dir = (h.ROOT / args.source).resolve()
    if not source_dir.is_relative_to(h.ROOT):
        parser.error('--source must belong to the Flash-only directory')
    source = source_dir.relative_to(h.ROOT).as_posix()
    linked = h.build
    art = linked(source=source, mode='NONE', boot=args.boot)

    def selected(source='source', mode='NONE', boot=None):
        """Keep explicit reference builds independent of the selected candidate."""
        if source != 'source':
            return linked(source, mode, boot)
        if mode != 'NONE' or (boot is not None and boot != art['boot']):
            raise ValueError('This run checks the selected no-LED geometry only')
        return art

    h.build = p.build = selected
    output = h.ROOT / 'build' / source / 'receiver-verification.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    report = dict(source=source, boot=hex(art['boot']), bytes=art['size'],
                  sha256=art['sha256'],
                  exhaustive=os.environ.get('USB_PHY_EXHAUSTIVE') == '1', results=[])

    def execute(name, function):
        print('RUN', name, flush=True)
        started = time.monotonic()
        try:
            function()
            row = dict(check=name, passed=True)
        except Exception as error:
            traceback.print_exc()
            row = dict(check=name, passed=False, error=str(error))
        row['seconds'] = round(time.monotonic()-started, 3)
        report['results'].append(row)
        output.write_text(json.dumps(report, indent=2)+'\n')
        print('RESULT', json.dumps(row), flush=True)

    for module, function in CHECKS:
        imported = importlib.import_module('tests35.'+module)
        execute(module, getattr(imported, function))
    raw = importlib.import_module('tests35.test_usb_rx_waveforms')
    for name in RAW_CHECKS:
        execute('test_usb_rx_waveforms.'+name, lambda name=name: getattr(raw, name)(art))

    failed = sum(not row['passed'] for row in report['results'])
    print(f'{art["size"]} bytes; {len(report["results"])-failed}/{len(report["results"])} groups pass; report {output}')
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
