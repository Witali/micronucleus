"""Read-only index of every available branch's USB assembly history.

Run with Python 3 and Git on Windows or Linux. Fetch desired remote refs
beforehand; this tool performs no network requests and changes no Git refs.
Generated reports stay under the Flash-only ignored build directory. Source
sizes are text sizes, never linked firmware size or protocol qualification.
"""
from collections import defaultdict
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REPO = Path(subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse',
                                    '--show-toplevel'], text=True).strip())
HERE = ROOT / 'build' / 'history-reuse'


def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args])


def candidate(path):
    return ((path.startswith('experimental/attiny88/') and path.endswith(('.S', '.inc')))
            or path in ('firmware/usbdrv/usbdrvasm16.inc', 'firmware/usbdrv/asmcommon.inc'))


def sources(revision):
    result = []
    for raw in git('ls-tree', '-rz', revision).split(b'\0'):
        if not raw:
            continue
        meta, filename = raw.split(b'\t', 1)
        path = filename.decode()
        if candidate(path):
            mode, kind, digest = meta.decode().split()
            assert kind == 'blob'
            result.append((path, digest))
    return result


def main():
    HERE.mkdir(parents=True, exist_ok=True)
    refs = []
    tip_sources = defaultdict(list)
    for line in git('for-each-ref', '--format=%(refname)%09%(objectname)',
                    'refs/heads', 'refs/remotes', 'refs/tags').decode().splitlines():
        ref, commit = line.split('\t')
        # Symbolic remote HEAD aliases add no independent branch history.
        symbolic = ''
        if ref.endswith('/HEAD'):
            result = subprocess.run(['git', '-C', str(REPO), 'symbolic-ref', '-q', ref],
                                    capture_output=True, text=True)
            assert result.returncode in (0, 1)
            symbolic = result.stdout.strip()
        refs.append(dict(ref=ref, commit=commit, symbolic_target=symbolic))
        for path, digest in sources(commit):
            tip_sources[digest].append(dict(ref=ref, path=path))
    revisions = git('log', '--all', '--format=%H', '--',
                    'experimental/attiny88', 'firmware/usbdrv').decode().splitlines()
    revisions = list(dict.fromkeys(revisions))
    all_sources = defaultdict(list)
    for number, revision in enumerate(revisions, 1):
        for path, digest in sources(revision):
            all_sources[digest].append(dict(commit=revision, path=path))
        if number % 100 == 0:
            print('Indexed relevant commits:', number, flush=True)
    handlers = []
    for digest, locations in all_sources.items():
        content = git('cat-file', 'blob', digest)
        text = content.decode('utf-8', errors='replace')
        if not re.search(r'(?m)^\s*(?:USB_handler|usbInterrupt|usbRxLoop)\s*:', text):
            continue
        normalized = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
        normalized = '\n'.join(line.strip() for line in normalized.splitlines() if line.strip())
        handlers.append(dict(blob=digest, source_sha256=hashlib.sha256(content).hexdigest(),
                             normalized_sha256=hashlib.sha256(normalized.encode()).hexdigest(),
                             source_bytes=len(content), source_lines=len(text.splitlines()),
                             occurrences=locations, tip_occurrences=tip_sources.get(digest, [])))
    interesting = ('ab6ab4f', 'afb9f9e', 'b6f32be', '91c3814', '7fc2e48', 'd8d035b',
                   '56203ee', 'b113478', 'af195e7', '3a8488b', 'e37c3f7', '5f6c58b')
    commits = []
    for abbreviation in interesting:
        commit = git('rev-parse', abbreviation).decode().strip()
        result = subprocess.run(['git', '-C', str(REPO), 'merge-base', '--is-ancestor', commit, 'HEAD'])
        assert result.returncode in (0, 1)
        commits.append(dict(commit=commit, present_in_current_ancestry=result.returncode == 0,
                            subject=git('show', '-s', '--format=%s', commit).decode().strip()))
    report = dict(head=git('rev-parse', 'HEAD').decode().strip(),
                  shallow=git('rev-parse', '--is-shallow-repository').decode().strip() == 'true',
                  reachable_commits=int(git('rev-list', '--count', '--all')),
                  relevant_commits=len(revisions), refs=refs,
                  unique_assembly_sources=len(all_sources), unique_handler_sources=len(handlers),
                  handlers=handlers, selected_history=commits)
    (HERE / 'inventory.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('head', 'shallow', 'reachable_commits',
          'relevant_commits', 'unique_assembly_sources', 'unique_handler_sources')}, indent=2))
    print('Ref counts:', {kind: sum(row['ref'].startswith('refs/' + kind + '/') for row in refs)
                          for kind in ('heads', 'remotes', 'tags')})
    print('Selected ancestry:', json.dumps(commits, indent=2))


if __name__ == '__main__':
    main()
