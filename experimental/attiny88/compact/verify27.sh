#!/bin/sh
# Offline candidate regression. A fitting 1-KiB release is a separate gate.
set -eu
cd "$(dirname "$0")"
python3 tests27/regression.py
python3 tests27/cooperative_usb.py
python3 tests27/tx_timing.py
python3 build_candidate.py --all-led
python3 -m compileall -q build_candidate.py audit_phy27.py tests27
