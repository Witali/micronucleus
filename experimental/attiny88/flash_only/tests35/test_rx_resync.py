"""Recover from an ordinary malformed packet into a separate legal SETUP.

Reuse existing bad-stuff DATA and illegal ACK-tail fixtures, then their real
EOP and a legal host gap. This checks digital-model recovery through the actual
foreground loop; it does not prove quarantine of arbitrary malformed streams.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import Bits, bind
from tests35.phy_model import bits_wave, from_bits
from tests35.test_ep0_token_timeout import Joined
from tests35.test_token_framing_wire import crc5

SETUP = bytes([0x80, 6, 0, 1, 0, 0, 18, 0])


def run(art, kind, rate, width, phase):
    period = 16_000_000 / rate
    if kind == 'stuff':
        packet = h.data_packet(bytes([255]) * 8, 0xc3)
        _, positions = bits_wave(packet)
        # Same malformed mandatory-stuff symbol as test_usb_rx_waveforms.
        malformed, _ = bits_wave(packet, stuff_error=positions[0])
        bad = from_bits(malformed.bits, rate, width)
        host_gap = 18 * period  # Host waits for the maximum response timeout.
    else:
        assert kind == 'ack_tail'
        # Same illegal zero ACK tail as test_usb_rx_waveforms.test_partial.
        bad = from_bits(Bits(b'\xd2').bits + [0], rate, width)
        host_gap = 2 * period  # An ACK expects no further response.
    token = Bits(h.token(0x2d), start=bad.boundaries[-2] + host_gap, rate=rate)
    data = Bits(h.data_packet(SETUP), start=token.boundaries[-2] + 2 * period,
                rate=rate)
    wire = Joined(Joined(bad, token), data)
    cpu = h.CPU(art, wire, 8 + phase)
    cpu.raw_stack.clear()
    cpu.pc = cpu.labels['bootloader_poll_begin']
    cpu.m[0x100] = 0xff
    cpu.m[0x10f] = 12 if kind == 'ack_tail' else 0x5a
    cpu.m[0x114] = 0 if kind == 'ack_tail' else 0x2d
    cpu.m[0x113] = 5 if kind == 'ack_tail' else 0
    cpu.r[8] = 0x10
    cpu.r[10] = crc5(5) << 3 if kind == 'ack_tail' else 0x10
    cpu.r[2] = 12 if kind == 'ack_tail' else 0
    cpu.r[3] = 0
    cpu.r[4:6] = [0x80, 0]
    cpu.r[11] = 0x80 if kind == 'ack_tail' else 0
    cpu.r[12:16] = [0x11, 0x22, 0x33, 0x44]
    reject_names = {value: name for name, value in cpu.labels.items()
                    if 'reject_stuff' in name}
    rejection, eops, tx, accepted_token = [], [], [], []
    cancellation = None
    setup_seen = False
    recovery_observed = None
    case = kind, rate, width, phase
    for _ in range(30_000):
        assert cpu.pc != cpu.labels['flash_do_spm'], ('unexpected NVM path', case)
        if cpu.pc in reject_names:
            rejection.append((cpu.t, reject_names[cpu.pc]))
        if cpu.pc == cpu.labels['usb_rx_end_packet']:
            eops.append(cpu.t)
        if cpu.pc == cpu.labels['usb_rx_ignore_packet'] and not tx:
            rejection.append((cpu.t, 'usb_rx_ignore_packet'))
            if recovery_observed is None:
                recovery_observed = any(sample[0] >= bad.boundaries[-2]
                                        and sample[2] == h.J
                                        for sample in cpu.io.samples)
        if cpu.pc == cpu.labels['usb_handler_packet_done'] and cancellation is None:
            assert cpu.r[2] == 0 and cpu.m[0x114] == 0, (
                'authorization survived error', case, cpu.r[2], cpu.m[0x114])
            assert cpu.r[3] == 0 and cpu.word(4) == 0x80, (
                'bad frame changed command/cursor', case)
            assert cpu.m[0x10c] == 0 and cpu.r[8] == 0x10, (
                'bad ACK committed address/cache', case)
            assert cpu.m[0x10f] == (12 if kind == 'ack_tail' else 0x5a), (
                'bad frame retired reply', case)
            cancellation = dict(time=cpu.t, ack_marker=cpu.r[2],
                                token=cpu.m[0x114], tx_length=cpu.m[0x10f])
        if cpu.pc == cpu.labels['usb_rx_handle_setup_or_out']:
            assert cpu.t >= token.start and cpu.r[23] == 3, case
            assert bytes(cpu.m[0x116:0x119]) == h.token(0x2d), (
                'separate SETUP token damaged', case)
            accepted_token.append(cpu.t)
        if cpu.pc == cpu.labels['usb_rx_setup_data']:
            assert bytes(cpu.m[0x116:0x121]) == h.data_packet(SETUP), case
            assert cpu.r[23] == 11 and cpu.t >= data.boundaries[-2], case
            setup_seen = True
        if cpu.pc == cpu.labels['usb_tx_acquire_bus']:
            assert cpu.t >= data.boundaries[-2] and setup_seen, (
                'response to malformed packet', case, cpu.t)
            assert cpu.r[19:21] == [2, 0xd2], (
                'unexpected response', case, cpu.r[19:21])
            tx.append(cpu.t)
        if tx and cpu.pc in (cpu.labels['bootloader_process_pending_command'],
                             cpu.labels['usb_setup_capture_fields']):
            assert cpu.io.get(10, 0) & 6 == 0, (
                'SETUP returned before ACK release', case)
            assert cpu.r[3] == 11 and cpu.r[12:16] + cpu.r[6:8] == list(SETUP[2:]), (
                'accepted SETUP shadow lost', case)
            assert cpu.m[0x10f] == 0x5a and cpu.r[2] == 0, (
                'new SETUP did not retire old reply/window', case)
            assert cancellation and accepted_token and len(tx) == 1, case
            assert not cpu.raw_stack, ('unbalanced foreground call stack', case)
            if kind == 'stuff':
                assert any('reject_stuff' in name for _, name in rejection), (
                    'stuff check was not exercised', case)
            else:
                assert eops and eops[0] <= rejection[0][0], (
                    'ACK tail did not reach EOF classification', case)
            return dict(kind=kind, rate=rate, eop_width=width, phase=phase,
                        malformed_eop=bad.boundaries[-3],
                        malformed_recovery_j=bad.boundaries[-2],
                        next_setup_sop=token.start, cancellation=cancellation,
                        first_rejection=rejection[0],
                        first_eof=eops[0] if eops else None,
                        recovery_j_observed_before_reject=recovery_observed,
                        setup_token=accepted_token[0],
                        setup_data_eop=data.boundaries[-2], ack=tx[0], returned=cpu.t)
        cpu.step()
        assert cpu.t <= data.end + 2000, (
            'separate SETUP not received', case, hex(cpu.pc), cpu.t, cancellation, tx)
    raise AssertionError(('recovery probe exceeded instruction bound', case))


def test():
    art = h.build()
    bind(art)
    rows = []
    for kind in ('stuff', 'ack_tail'):
        for rate in (1_499_250, 1_500_000, 1_500_750):
            for width in (10.72, 2 * 16_000_000 / rate, 24):
                for phase in (0, 0.25, 0.5, 0.75):
                    rows.append(run(art, kind, rate, width, phase))
    assert len(rows) == 72
    print('PASS ordinary real-EOP recovery into separate SETUP:', len(rows),
          'cases;', art['size'], 'bytes', art['sha256'])


if __name__ == '__main__':
    test()
