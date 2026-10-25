#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 build.py
python3 tests/emulator_diff_test.py
python3 tests/spm_boundary_audit.py
python3 tests/audit_official.py
python3 tests/test_extra_cases.py
