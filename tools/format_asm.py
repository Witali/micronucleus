#!/usr/bin/env python3
"""Normalize leading assembly indentation in maintained first-party sources.

Only leading spaces/tabs change. Comments, quoted data, continuations, operand
spacing and line endings are preserved. Pinned references/vendor files are not
selected. Run with --check for a read-only style check.
"""
import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ('experimental/attiny88/compact/source/',
               'experimental/attiny88/flash_only/source/',
               'experimental/attiny88/flash_only/variants/combined_rx/',
               'experimental/attiny88/flash_only/eeprom_stage/',
               'experimental/attiny88/block64/source/',
               'experimental/attiny88/source/')
FIRMWARE_FILES = {'firmware/crt1.S', 'firmware/osccal.S', 'firmware/osccalASM.S'}
LABEL = re.compile(rb'(?:[0-9]+|[A-Za-z_.$\\][A-Za-z0-9_.$\\@]*):')


def maintained_files():
    names = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z']).decode().split('\0')
    return [ROOT / name for name in names if name and
            (name in FIRMWARE_FILES or
             (name.startswith(SOURCE_DIRS) and Path(name).suffix.lower() in ('.s', '.asm', '.inc')))]


def comment_state(line, inside):
    """Track C block comments without interpreting delimiters inside strings."""
    index, quote = 0, None
    while index < len(line):
        if inside:
            end = line.find(b'*/', index)
            if end < 0:
                return True
            index, inside = end + 2, False
        elif quote is not None:
            if line[index] == 92:
                index += 2
            elif line[index] == quote:
                quote, index = None, index + 1
            else:
                index += 1
        elif line[index:index + 2] == b'/*':
            inside, index = True, index + 2
        elif line[index:index + 2] == b'//' or line[index:index + 1] == b';':
            break
        elif line[index] in (34, 39):
            quote, index = line[index], index + 1
        else:
            index += 1
    return inside


def formatted(data):
    """Keep labels/CPP at column one, indent executable/pseudo statements four."""
    result, inside, continuation, disabled_depth = [], False, False, 0
    for line in data.splitlines(keepends=True):
        content = line.lstrip(b' \t')
        # Literal #if 0 blocks can contain C reference examples rather than ASM.
        directive = re.match(rb'#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)', content)
        disabled = bool(disabled_depth)
        if directive and not inside and not continuation:
            kind, value = directive.groups()
            if disabled_depth:
                if kind in (b'if', b'ifdef', b'ifndef'):
                    disabled_depth += 1
                elif kind == b'endif':
                    disabled_depth -= 1
                elif disabled_depth == 1 and kind in (b'else', b'elif'):
                    disabled_depth = 0
            elif kind == b'if' and re.fullmatch(rb'\s+0\s*(?:(?://|/\*).*)?', value):
                disabled_depth = 1
        preserved = (inside or continuation or disabled or not content.strip() or
                     content.startswith((b'/*', b'//', b';')))
        if preserved:
            result.append(line)
        elif content.startswith(b'#') or LABEL.match(content):
            result.append(content)
        else:
            result.append(b'    ' + content)
        inside = comment_state(line, inside)
        continuation = line.rstrip(b'\r\n \t').endswith(b'\\')
    output = b''.join(result)
    assert [line.lstrip(b' \t') for line in data.splitlines(keepends=True)] == [
        line.lstrip(b' \t') for line in output.splitlines(keepends=True)]
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    changed, selected = [], maintained_files()
    for path in selected:
        original = path.read_bytes()
        output = formatted(original)
        if output != original:
            changed.append(path.relative_to(ROOT).as_posix())
            if not args.check:
                path.write_bytes(output)
    if args.check and changed:
        print('\n'.join(changed))
    print(f'{"CHECK" if args.check else "FORMAT"}: {len(selected)} files; {len(changed)} need changes')
    return int(args.check and bool(changed))


if __name__ == '__main__':
    raise SystemExit(main())
