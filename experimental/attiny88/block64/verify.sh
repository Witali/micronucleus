#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 tools/patch_block64.py
python3 tools/build.py
python3 -m pytest -q tests
