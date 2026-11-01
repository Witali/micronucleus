"""Admit the real 17-page no-LED placement, including emitted runtime paths.

This is a development-image check. A deployment at this boundary requires a
recognized host profile; the installed profile and hardware stay unchanged.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_candidate import checked_build
from tests27.regression import check_standard, check_tx_bytes
from tests27.nvm_opcodes import check_nvm
from tests27.cooperative_usb import check as check_usb
from tests27.poll_window import check_quiet_poll, check_poll_capture
from tests27.tx_timing import check as check_tx


def check():
    artifact = checked_build('NONE', 0x1BC0)
    assert artifact['size'] <= 17 * 64 == 8192 - artifact['boot'], \
        ('17-page overflow', artifact['size'])
    check_standard(artifact, 'NONE')
    check_nvm(artifact)
    check_tx_bytes(artifact)
    check_usb(artifact)
    check_quiet_poll(artifact)
    check_poll_capture(artifact)
    check_tx(artifact)
    print('PASS real 17-page placement:', artifact['size'], 'bytes at 0x1BC0;',
          'SHA256', artifact['sha256'])


if __name__ == '__main__':
    check()
