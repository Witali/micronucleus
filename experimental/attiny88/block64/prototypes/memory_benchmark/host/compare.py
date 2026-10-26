#!/usr/bin/env python3
"""Summarize two successful private benchmark reports without memory dumps."""
import argparse
import json
from pathlib import Path
import statistics


def summarize(report,operation):
    rows=[row for row in report['measurements'] if row['operation']==operation]
    if not rows:return None
    if any(not row['success'] for row in rows):raise ValueError('A selected measurement failed')
    sizes={row['bytes'] for row in rows}
    if len(sizes)!=1:raise ValueError('Measurement sizes differ within one operation')
    wall=[row['wall_seconds'] for row in rows]
    fields=('control_transactions','completion_transactions','control_payload_bytes',
            'usb_seconds','completion_usb_seconds','program_settle_seconds',
            'poll_sleep_seconds','host_other_seconds')
    return {'samples':len(rows),'bytes':rows[0]['bytes'],
            'wall_seconds':{'min':min(wall),'median':statistics.median(wall),
                            'mean':statistics.mean(wall),'max':max(wall)},
            'mean_verified_bytes_per_second':rows[0]['bytes']/statistics.mean(wall),
            **{name:statistics.mean(row.get(name,0) for row in rows) for name in fields}}


def compare(old,new,legacy_cli_erase_seconds=None):
    if not old.get('passed') or not new.get('passed'):
        raise ValueError('Both benchmark phases must pass before comparison')
    if old['identity']['protocol']!='legacy-2.8' or new['identity']['protocol']!='guarded-streaming-v2':
        raise ValueError('Reports do not have the expected old/new protocol order')
    if old.get('controlled_flash_payload_sha256')!=new.get('controlled_flash_payload_sha256'):
        raise ValueError('Controlled Flash payloads differ')
    if old.get('before_sha256',{}).get('eeprom')!=new.get('before_sha256',{}).get('eeprom'):
        raise ValueError('Original EEPROM contents differ between phases')
    pairs=[]
    operations=('flash.read.common','flash.read.controlled','eeprom.read','eeprom.write',
                'eeprom.erase_to_ff','flash.write.scratch','flash.write.page')
    for old_operation,new_operation in (
        *[(name,name) for name in operations],
        ('flash.read.common','flash.read.common.control8'),
        ('flash.read.controlled','flash.read.controlled.control8'),
        ('eeprom.read','eeprom.read.control1')):
        left,right=summarize(old,old_operation),summarize(new,new_operation)
        if left is None or right is None:continue
        if left['bytes']!=right['bytes']:raise ValueError('Compared operations process different byte counts')
        pairs.append({'old_operation':old_operation,'new_operation':new_operation,
            'old':left,'new':right,
            'wall_speedup_old_over_new':left['wall_seconds']['mean']/right['wall_seconds']['mean'],
            'common_flash_contents_identical':old['before_sha256']['flash_common']==new['before_sha256']['flash_common']
                if old_operation=='flash.read.common' else None})
    return {'comparisons':pairs,'new_scratch_erase':summarize(new,'flash.erase.scratch'),
        'legacy_cli_application_erase':None if legacy_cli_erase_seconds is None else {
            'wall_seconds':legacy_cli_erase_seconds,'scope':'whole application, external official CLI',
            'silicon_time_measured':False,'direct_scratch_erase_ratio':False},
        'notes':[
            'USB call time includes host scheduling, retries/NAKs and firmware busy stalls.',
            'Fixed program-settle waits are reported separately and are not silicon-time measurements.',
            'Verification is outside each write/erase timer; only passed phases are compared.',
            'Scratch-write aggregate rows contain page rows; do not sum both levels.',
            'Legacy Flash has one 512-byte round with eight page samples; new Flash has repeated erased-page rounds.',
            'Common full reads contain different application images; controlled 512-byte reads use identical payload bytes.',
            'Legacy whole-application erase and new eight-page erase have different scopes.',
            'Final original-application restoration and installed-loader integrity are verified by external orchestration.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('old_report',type=Path)
    parser.add_argument('new_report',type=Path)
    parser.add_argument('--legacy-cli-erase-seconds',type=float)
    args=parser.parse_args()
    if args.legacy_cli_erase_seconds is not None and args.legacy_cli_erase_seconds<0:
        parser.error('Erase interval must be nonnegative')
    result=compare(json.loads(args.old_report.read_text()),json.loads(args.new_report.read_text()),
                   args.legacy_cli_erase_seconds)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
