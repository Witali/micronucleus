"""Historical metadata adapters over the maintained AVR/GPIO executor.

No firmware is rebuilt, repaired or replaced by a source-level protocol model.
The compact image is already tracked; an optional official build is supplied
as metadata with paths relative to that metadata file.
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
COMPACT = ROOT.parent / 'compact'
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tests35 import ep0_model as h
from tests35.ep0_cases import bind, Bits
from tests35 import phy_model as wire_model

COMPACT_SHA = 'e2a771412dfacf7a3ad7575d4ccb526791557c157633637ecf0c7fdbb9096df0'
UPSTREAM_SHA = 'ec361683baa476be66826c884f2f3759b63451225a35d40a5318d8d1f8ce24bf'


def compact_artifact():
    """Load the exact 1148-byte image recorded as installed at 0x1B80."""
    fixture = HERE / 'compact30_symbols.json'
    saved = json.loads(fixture.read_text())
    binary = COMPACT / 'firmware27/Pass27_off_body.bin'
    body = binary.read_bytes()
    if len(body) != 1148 or hashlib.sha256(body).hexdigest() != COMPACT_SHA:
        raise ValueError('The tracked compact 3.0 body does not match the installed SHA256')
    manifest = json.loads((COMPACT / 'firmware27/manifest.json').read_text())
    profile = next(row for row in manifest['builds'] if row['led'] == 'NONE')
    if profile['code_sha256'] != COMPACT_SHA or int(profile['boot_at'], 0) != 0x1b80:
        raise ValueError('The tracked public manifest disagrees with the historical fixture')
    if saved['body_sha256'] != COMPACT_SHA or saved['boot'] != 0x1b80:
        raise ValueError('Wrong historical symbol fixture')
    if saved['provenance']['source_sha256'] != manifest['source_sha256']:
        raise ValueError('Historical symbols were not derived from the manifest source set')
    # The executor needs an object-path field only for builds without symbols.
    # Here symbols are supplied explicitly; no ELF/toolchain process is needed.
    return dict(boot=saved['boot'], size=len(body), sha256=COMPACT_SHA,
                body=body, bin=binary, obj=fixture, symbols=saved['symbols'],
                provenance=saved['provenance'])


def upstream_artifact(metadata):
    """Accept only the pinned, independently prepared official no-LED build."""
    metadata = Path(metadata).resolve()
    saved = json.loads(metadata.read_text())
    binary = Path(saved['bin'])
    if not binary.is_absolute():
        binary = metadata.parent / binary
    body = binary.read_bytes()
    if saved['boot'] != 0x1a40 or len(body) != 1332 or hashlib.sha256(body).hexdigest() != UPSTREAM_SHA:
        raise ValueError('Upstream artifact must match the pinned 1332-byte v2.6 no-LED build')
    if saved.get('sha256') != UPSTREAM_SHA:
        raise ValueError('Upstream metadata SHA256 disagrees with its body')
    symbols = dict(saved['symbols'])
    # These names are required by the common constructor, never executed.
    symbols.update(usb_control_process_received_packet=symbols['USB_handler'],
                   bootloader_poll_begin=0xfffc, bootloader_start_application=0xfffa)
    return dict(boot=0x1a40, size=len(body), sha256=UPSTREAM_SHA,
                body=body, bin=binary, obj=metadata, symbols=symbols,
                provenance=saved.get('provenance', {}))


class CPU(h.CPU):
    """Keep the real historical register initialization, not modern CRC caches."""
    def __init__(self, artifact, wire, entry=8):
        super().__init__(artifact, wire, entry)
        self.r[8] = self.r[10] = 0


def seed(artifact, address=0):
    bind(artifact)
    cpu = CPU(artifact, h.Wave(b'', start=1_000_000))
    cpu.t = 0
    cpu.m[0x10f] = 0x5a
    cpu.m[0x100] = 0xff
    cpu.m[0x10c] = cpu.m[0x113] = address * 2
    return cpu


def receive(cpu, packet=None, start=None, wave=None, entry=8):
    """Execute one whole original compact handler, preserving retry SRAM."""
    start = cpu.t + 500 if start is None else start
    wave = wave or h.Wave(packet, start=start)
    cpu.raw_stack.clear()
    cpu.calls.append(0xfffe)
    cpu.pc = cpu.labels['USB_handler']
    cpu.t = wave.start + entry
    cpu.bus_events = []
    cpu.io = h.SynchronizedPinIO(cpu, wave)
    cpu.io.cleared_at = -1
    checkpoints = []
    sent = []
    snapshot = None
    targets = {cpu.labels[name]: name for name in
               ('usb_rx_handle_in', 'usb_rx_handle_setup_or_out', 'usb_rx_ignore_packet')}
    for _ in range(20000):
        if cpu.pc == 0xfffe:
            break
        if cpu.pc in targets:
            checkpoints.append(targets[cpu.pc])
        if snapshot is None and cpu.pc == cpu.labels['usb_rx_end_packet']:
            # This is the original countdown-derived count, which can include
            # a phantom partial byte. Expose it rather than importing a fix.
            count = (11 - cpu.r[23]) & 255
            snapshot = dict(time=cpu.t, count=count,
                            decoded=bytes(cpu.m[0x116:0x116 + count]).hex())
        if cpu.pc == cpu.labels['usb_tx_acquire_bus']:
            if cpu.r[19] == 2:
                sent.append(dict(kind='handshake', pid=cpu.r[20]))
            else:
                count = cpu.r[19] - 4
                sent.append(dict(kind='data', pid=cpu.m[0x101],
                                 payload=bytes(cpu.m[0x102:0x102 + count]).hex()))
        cpu.step()
    else:
        raise AssertionError('Historical compact handler did not return')
    first_k = next((when for when, io, value in cpu.bus_events
                    if io == 11 and value & 6 == h.K), None)
    return dict(checkpoints=checkpoints, sent=sent, snapshot=snapshot,
                current_token=cpu.m[0x114], rx_length=cpu.m[0x112],
                rx_token=cpu.m[0x10d], tx=cpu.m[0x10f], address=cpu.m[0x10c],
                response_cycles=None if first_k is None else first_k-wave.boundaries[-2],
                bus=cpu.bus_events, cycles=cpu.t)


def tx_ownership(bus):
    """Report source SE0 and driven-J durations separately from pull-up J."""
    driving = False
    se0 = recovered_j = release = None
    for when, io, value in bus:
        if io == 10:
            next_driving = value & 6 == 6
            if driving and not next_driving:
                release = when
            driving = next_driving
        elif io == 11 and driving:
            if value & 6 == 0 and se0 is None:
                se0 = when
            elif se0 is not None and value & 6 == h.J and recovered_j is None:
                recovered_j = when
    if None in (se0, recovered_j, release):
        return None
    return dict(se0_clocks=recovered_j-se0, driven_j_clocks=release-recovered_j)
