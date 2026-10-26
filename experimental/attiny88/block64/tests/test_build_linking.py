"""A relocatable object must never become a seemingly valid firmware image."""
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from avr_build import assemble


def test_missing_branch_target_prevents_binary_extraction(tmp_path):
    source = tmp_path / 'missing_target.S'
    source.write_text('.text\n.global bootloader_start\nbootloader_start:\n rjmp missing_target\n')
    image = tmp_path / 'firmware.bin'
    with pytest.raises(subprocess.CalledProcessError):
        assemble(source, tmp_path / 'firmware.o', image)
    assert not image.exists()
