#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 build.py
python3 -m unittest discover -s tests -v
python3 tests/test_vusb_timing.py
python3 tests/test_crc_equivalence.py
