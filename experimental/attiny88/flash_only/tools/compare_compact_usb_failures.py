"""Compare mandatory failure contexts from two immutable full 67-group runs.

This is a regression comparison, not a USB qualification gate. Inherited
mandatory failures remain failures even when the comparison exits zero.
No firmware, model, fixture or expected protocol result is executed or edited.
"""
from pathlib import Path
import argparse
import hashlib
import json

GROUPS = (
    ('test_token_crossover_admission', 'adjacent-token'),
    ('test_rx_crossover_asymmetric', 'asymmetric-crossover'),
    ('test_rx_crossover_se1', 'se1-crossover'),
    ('test_rx_crossover_payloads', 'asymmetric-payloads'),
    ('test_rx_sync_crossover', 'sync-crossover'),
)
OBSERVATIONS = {'errors', 'response', 'events', 'tx_length', 'pending', 'true_eop'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def failure_map(rows):
    """Separate input identity from effects, response timing and error text."""
    result = {}
    for row in rows:
        context = {key: value for key, value in row.items() if key not in OBSERVATIONS}
        key = canonical(context)
        assert key not in result, ('Duplicate failure input', context)
        result[key] = row
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    pins = {Path(__file__).resolve(): sha(Path(__file__).resolve())}

    def read(path):
        pins[path] = sha(path)
        return json.loads(path.read_text())

    runs = []
    for directory in (args.baseline.resolve(), args.candidate.resolve()):
        frozen = read(directory / 'frozen-inputs.json')
        for relative, digest in frozen.items():
            path = (directory / relative).resolve()
            assert path.is_relative_to(directory), 'Frozen input escapes run directory'
            assert sha(path) == digest, ('Frozen input changed', relative)
            pins[path] = digest
        completion = read(directory / 'completion.json')
        integrity = read(directory / 'completed-integrity.json')
        report = read(directory / 'results.json')
        assert completion['all_inputs_unchanged'] and completion['groups'] == 67
        assert len(integrity['completed']) == len(report['results']) == 67
        assert report['exhaustive'] is True
        assert completion['sha256'] == integrity['sha256'] == report['sha256']
        failed = {row['check'] for row in report['results'] if not row['passed']}
        assert completion['exit_code'] == int(bool(failed))
        runs.append(dict(directory=directory, frozen=frozen, report=report, failed=failed))
    old, new = runs
    # These runs use the same independently frozen Python models/oracles and
    # fixture source snapshot; only their separately pinned linked artifact differs.
    snapshots = [{key: digest for key, digest in run['frozen'].items()
                  if key.startswith('frozen/')} for run in runs]
    assert snapshots[0] == snapshots[1], 'Independent frozen input snapshots differ'
    groups = []
    for check, stem in GROUPS:
        reports = []
        for run in runs:
            path = run['directory'] / 'frozen/attiny88/flash_only/build' / f"{stem}-{run['report']['sha256'][:16]}.json"
            result = read(path)
            assert result['sha256'] == run['report']['sha256']
            reports.append((path, result))
        before, after = [failure_map(result['failures']) for _, result in reports]
        common = before.keys() & after.keys()
        repaired, added = before.keys() - after.keys(), after.keys() - before.keys()
        changed = [key for key in common if canonical(before[key]) != canonical(after[key])]
        assert reports[0][1]['cases'] == reports[1][1]['cases'], ('Corpus size changed', check)
        groups.append(dict(check=check, cases=reports[0][1]['cases'],
            baseline_failures=len(before), candidate_failures=len(after),
            repaired=len(repaired), new_failures=len(added), shared=len(common),
            changed_shared_observations=len(changed),
            baseline_context_set_sha256=hashlib.sha256(canonical(sorted(before)).encode()).hexdigest(),
            candidate_context_set_sha256=hashlib.sha256(canonical(sorted(after)).encode()).hexdigest(),
            baseline_report_sha256=pins[reports[0][0]], candidate_report_sha256=pins[reports[1][0]],
            repaired_contexts=[json.loads(key) for key in sorted(repaired)],
            new_contexts=[json.loads(key) for key in sorted(added)],
            changed_shared_contexts=[json.loads(key) for key in sorted(changed)]))
    passed = not (new['failed'] - old['failed']) and all(
        not group['new_failures'] and not group['changed_shared_observations'] for group in groups)
    result = dict(baseline_body_sha256=old['report']['sha256'], candidate_body_sha256=new['report']['sha256'],
        baseline_bytes=old['report']['bytes'], candidate_bytes=new['report']['bytes'],
        exhaustive_groups=67, baseline_passed=67-len(old['failed']), candidate_passed=67-len(new['failed']),
        identical_frozen_inputs=len(snapshots[0]),
        new_failing_groups=sorted(new['failed']-old['failed']), comparison_passed=passed,
        groups=groups, tool_sha256=pins[Path(__file__).resolve()],
        scope='Finite failure-context regression comparison only. Inherited mandatory failures are not accepted or waived; no full USB qualification.')
    for path, digest in pins.items():
        assert sha(path) == digest, ('Input changed during comparison', str(path))
    args.output.write_text(json.dumps(result, indent=2)+'\n', newline='\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'groups'}, indent=2))
    for group in groups:
        print(group['check'], group['baseline_failures'], '->', group['candidate_failures'],
              'fixed', group['repaired'], 'new', group['new_failures'],
              'changed shared observations', group['changed_shared_observations'])
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
