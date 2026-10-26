#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 tools/build.py
python3 -m pytest -q tests
python3 tools/audit_release.py
