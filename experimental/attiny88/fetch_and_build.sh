#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
for tool in git make avr-gcc avr-size avr-objdump python3; do
    command -v "$tool" >/dev/null || { echo "Missing $tool" >&2; exit 1; }
done
# Reproducible pinned upstream source snapshot, as inspected in Oct 2026.
UPSTREAM_COMMIT=4dd1b49f39cd9d6fc736a720777ed62f4564e0e2
if [ ! -d upstream/.git ]; then
    git clone https://github.com/micronucleus/micronucleus.git upstream
fi
(cd upstream && git fetch origin "$UPSTREAM_COMMIT" && git checkout --detach "$UPSTREAM_COMMIT")
python3 tools/build_optimized.py upstream --output build_results
printf '\nBuild completed. Inspect build_results/build_manifest.json before flashing.\n'
