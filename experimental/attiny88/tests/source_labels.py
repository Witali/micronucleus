"""Expose semantic names for symbols from unchanged historical references.

Only test-side symbol dictionaries gain aliases. Historical assembly and
firmware bytes remain intact; the maintained source defines semantic names.
"""
import csv
from pathlib import Path

with (Path(__file__).resolve().parent.parent/'source/label-map.csv').open(newline='') as stream:
    LABEL_NAMES = {row['historical_label']: row['label'] for row in csv.DictReader(stream)}


def with_semantic_names(symbols):
    result = dict(symbols)
    for historical, semantic in LABEL_NAMES.items():
        if historical in symbols:
            if semantic in symbols and symbols[semantic] != symbols[historical]:
                raise ValueError(f'Conflicting label addresses: {historical}, {semantic}')
            result[semantic] = symbols[historical]
    return result
