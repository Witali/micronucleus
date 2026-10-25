#!/usr/bin/env python3
"""Import and verify the pinned official ATtiny88 device files.

No download is performed here. --pack accepts the Microchip archive downloaded
from PACK_URL. --check verifies the checked-in original files offline.
"""
from pathlib import Path
import argparse
import hashlib
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT/'vendor/microchip/ATtiny_DFP-3.4.278'
PACK_URL = 'https://packs.download.microchip.com/Microchip.ATtiny_DFP.3.4.278.atpack'
PACK_SHA256 = '41f09d5825abaa764c9000f4488f8ba3fab152afe6229b359de4a5efe9a21eda'
FILES = {
    'avrasm/inc/tn88def.inc': ('tn88def.inc', '4c516f34d159f97fb1a253c91dec01d456d05cc4fa80f13c15728a08366bff7d'),
    'include/avr/iotn88.h': ('include/avr/iotn88.h', '63c792cc9961aca81bfb3602e0d1d3cf01a37f35a449a6b6e2e6c8b41cc1e892'),
    'LICENSE.txt': ('LICENSE.txt', '3bf0a101f2b2e44eda3b477f866bd24204c35fa1f841c865933028adf155336a'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, help='Official pinned .atpack archive')
    parser.add_argument('--check', action='store_true', help='Verify the checked-in files without rewriting them')
    args = parser.parse_args()
    if args.pack:
        assert not args.check, 'Use --pack to import or --check to verify'
        assert hashlib.sha256(args.pack.read_bytes()).hexdigest() == PACK_SHA256, 'Pack hash mismatch'
        with ZipFile(args.pack) as archive:
            contents = {member: archive.read(member) for member in FILES}
        # Validate all members before writing any file.
        for member, (_, checksum) in FILES.items():
            assert hashlib.sha256(contents[member]).hexdigest() == checksum, member
        for member, (name, _) in FILES.items():
            destination = VENDOR/name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(contents[member])
    for name, checksum in FILES.values():
        assert hashlib.sha256((VENDOR/name).read_bytes()).hexdigest() == checksum, name
    print('PASS: official Microchip ATtiny88 C header, AVRASM reference and license are byte-exact')


if __name__ == '__main__':
    main()
