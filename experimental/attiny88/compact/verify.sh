#!/bin/sh
# Deterministic, hardware-free source build and opcode/model tests.
set -eu
cd "$(dirname "$0")"
python3 build_release26.py
python3 audit_phy26.py
python3 tests25/test25_sync_model.py
python3 tests26/test26_phy_arithmetic.py
python3 tests26/test26_standard.py
python3 tests26/test26_descriptor.py
python3 tests26/test26_tx_bytes.py
python3 tests26/test26_nvm.py
python3 tests26/test26_combined_erase.py
python3 tests26/test26_cursor_opcodes.py
python3 tests26/test26_host_stream.py
python3 tests25/test25_host_planner.py
python3 tests25/test25_program_profiles.py
python3 -m compileall -q host tests tests25 tests26
printf '\nPASS: Pass26 reproducible AVR builds, opcodes and mock host. NEVER PROGRAMMED HARDWARE.\n'
