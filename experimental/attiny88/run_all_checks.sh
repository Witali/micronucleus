#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p report
python build.py
python tests/audit_static.py
python tests/test_vusb_timing.py
python tests/test_crc_equivalence.py
python tests/test_protocol_diff.py
python tests/spm_model.py > report/SPM_MODEL_LOG.txt
sha256sum firmware/* source/*.S > report/SHA256SUMS.txt
echo 'PASS: all software checks complete (not a physical USB certification).'
