#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 build.py
python3 -m unittest discover -s tests -q
python3 tests/test_vusb_timing.py
python3 tests/emulator_diff_test.py
python3 tools/scan_repeats.py
