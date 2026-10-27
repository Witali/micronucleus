#!/usr/bin/env python3
"""SHA-256 check of handoff source and firmware files (not physical USB)."""
from pathlib import Path
import hashlib,sys
root=Path(__file__).resolve().parent
bad=[];total=0
for line in (root/'MANIFEST_SHA256.txt').read_text().splitlines():
    if not line.strip():continue
    expected, rel=line.split('  ',1)
    p=root/rel
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:bad.append(rel)
    total+=1
if bad:
    print('FAILED files:',*bad,sep='\n - ')
    sys.exit(1)
print(f'PASS: {total} source, test, documentation and release file SHA-256 values')
