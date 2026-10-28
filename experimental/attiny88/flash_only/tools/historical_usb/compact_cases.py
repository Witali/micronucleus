"""Observations of original compact 3.0 token, retry and physical RX behavior."""
from model import h, wire_model as p, seed, receive, tx_ownership
from tests35.test_data_framing import ending_packets, final_ones
from tests35.test_usb_crossover import single_crossover


def token_control(artifact):
    """Record token admission and real SRAM-preserving retry/status traces."""
    rows = []
    for pid, name in ((0x69, 'IN'), (0xe1, 'OUT'), (0x2d, 'SETUP')):
        good = h.token(pid)
        variants = [('valid', good), ('bad_crc5', good[:2] + bytes([good[2] ^ 8])),
                    ('foreign_address1', h.token(pid, address=1))]
        for variant, packet in variants:
            result = receive(seed(artifact), packet, start=0)
            accepted = any(label in result['checkpoints'] for label in
                           ('usb_rx_handle_in', 'usb_rx_handle_setup_or_out'))
            rows.append(dict(token=name, variant=variant, packet=packet.hex(),
                             accepted=accepted, result=result))
    for endpoint in (1, 2, 15):
        packet = h.token(0x69, endpoint=endpoint)
        result = receive(seed(artifact), packet, start=0)
        rows.append(dict(token='IN', variant=f'endpoint{endpoint}', packet=packet.hex(),
                         accepted='usb_rx_handle_in' in result['checkpoints'], result=result))
    for variant, packet in (('PID_only_fresh_zero_RX', b'\x69'),
                            ('missing_crc', h.token(0x69)[:2]),
                            ('extra_byte', h.token(0x69) + b'\0')):
        result = receive(seed(artifact), packet, start=0)
        rows.append(dict(token='IN', variant=variant, packet=packet.hex(),
                         accepted='usb_rx_handle_in' in result['checkpoints'], result=result))

    # Prepared valid DATA must remain immutable until a real host ACK. Neither
    # of these input waves contains an ACK; preserve SRAM across the retry.
    cpu = seed(artifact)
    packet = h.data_packet(bytes(range(8)), 0x4b)
    cpu.m[0x101:0x101 + len(packet)] = packet
    cpu.m[0x10f] = 12
    first = receive(cpu, h.token(0x69), start=0)
    second = receive(cpu, h.token(0x69))
    retry = dict(host_ack_received=False, first=first, second_identical_in=second,
                 identical_data_retransmitted=second['sent'] == first['sent'])

    cpu = seed(artifact)
    cpu.m[0x113] = 37 * 2
    packet = h.data_packet(b'', 0x4b)
    cpu.m[0x101:0x101 + len(packet)] = packet
    cpu.m[0x10f] = 4
    status = receive(cpu, h.token(0x69), start=0)
    old_retry = receive(cpu, h.token(0x69))
    address = dict(requested=37, host_ack_received=False, status=status,
                   retry_at_old_address=old_retry)

    setup = bytes((0x80, 6, 0, 1, 0, 0, 18, 0))
    setup_rows = []
    for pid in (0xc3, 0x4b):
        cpu = seed(artifact)
        cpu.m[0x114] = 0x2d
        setup_rows.append(dict(pid=pid, result=receive(cpu, h.data_packet(setup, pid), start=0)))
    # Positive controls detect a broken adapter. Malformed-packet outcomes
    # remain observations, not permissions to weaken the modern USB oracle.
    assert all(row['accepted'] for row in rows if row['variant'] == 'valid')
    assert not any(row['accepted'] for row in rows if row['variant'] == 'foreign_address1')
    assert setup_rows[0]['result']['rx_length'] == 11
    return dict(token_cases=rows, lost_ack_retry=retry, set_address_before_ack=address,
                setup_data_pid=setup_rows)


def raw_probe(artifact, packet, wave=None, entry=8, pending=0x2d):
    cpu = seed(artifact)
    cpu.m[0x114] = pending
    result = receive(cpu, packet, start=0, wave=wave, entry=entry)
    result['tx_ownership'] = tx_ownership(result['bus'])
    return result


def raw_cases(artifact, full_tail_matrix=False):
    """Exercise stuffing, legal/illegal tails, EOP and conservative crossover."""
    rows = {}
    for length in range(5):
        packet = b'\xd2'
        wave = p.from_bits(p.bits_wave(packet)[0].bits + [1] * length)
        rows[f'ack_dribble_{length}'] = raw_probe(artifact, packet, wave)
    packet = h.data_packet(b'\xff' * 8)
    encoded, stuffed = p.bits_wave(packet)
    for name, bits in [('valid_data', encoded.bits),
                       ('extra_zero_data', encoded.bits + [0]),
                       ('truncated_crc_bit', encoded.bits[:-1])]:
        rows[name] = raw_probe(artifact, packet, p.from_bits(bits))
    for position in stuffed:
        rows[f'bad_stuff_at_{position}'] = raw_probe(artifact, packet, p.bits_wave(packet, position)[0])
    assert rows['valid_data']['snapshot']['decoded'] == packet.hex()
    assert rows['valid_data']['rx_length'] == 11

    eop = dict(cases=0, by_width={})
    for rate in (1499250, 1500000, 1500750):
        for width in (10.72, 64 / 3, 24):
            group = eop['by_width'].setdefault(str(width), dict(cases=0, missed=0, examples=[]))
            for pid in (0x69, 0xe1, 0x2d):
                for entry in (5, 8, 16, 24, 32, 38):
                    token = h.token(pid)
                    row = raw_probe(artifact, token, p.eop_wave(token, width, rate), entry)
                    group['cases'] += 1
                    eop['cases'] += 1
                    if row['snapshot'] is None:
                        group['missed'] += 1
                        if len(group['examples']) < 3:
                            group['examples'].append(dict(rate=rate, pid=pid, entry=entry, result=row))

    # At a real stuffed transition, <=210ns possible PIN=00 is a conservative
    # digital envelope. It is not an observed board threshold waveform.
    crossover = dict(cases=0, early_drives=[], receive_mismatches=0)
    for position in stuffed:
        for fraction in (0, 0.5, 1):
            for entry in (8, 24.75):
                pristine = p.bits_wave(packet)[0]
                wave = single_crossover(pristine, position, width=3.36, fraction=fraction)
                row = raw_probe(artifact, packet, wave, entry)
                crossover['cases'] += 1
                if any(when < wave.boundaries[-3] and io == 10 and value & 6
                       for when, io, value in row['bus']):
                    crossover['early_drives'].append(dict(position=position, fraction=fraction,
                                                         entry=entry, result=row))
                snapshot = row['snapshot']
                if snapshot is None or snapshot['decoded'] != packet.hex():
                    crossover['receive_mismatches'] += 1

    tails = None
    if full_tail_matrix:
        tails = dict(cases=0, legal=0, legal_not_published=0, legal_payload_mismatch=0,
                     illegal=0, illegal_published=0, examples=[])
        for setup, payload_length in ((True, 8), (False, 2), (False, 8)):
            for packet, payload in ending_packets(setup, payload_length):
                base = p.bits_wave(packet)[0].bits
                final_run = final_ones(base)
                for tail_length in range(8):
                    for pattern in range(1 << tail_length):
                        tail = [(pattern >> bit) & 1 for bit in range(tail_length)]
                        legal = pattern == (1 << tail_length) - 1 and final_run + tail_length <= 6
                        row = raw_probe(artifact, packet, p.from_bits(base + tail),
                                        pending=0x2d if setup else 0xe1)
                        published = row['rx_length'] != 0
                        tails['cases'] += 1
                        tails['legal' if legal else 'illegal'] += 1
                        if legal and not published:
                            tails['legal_not_published'] += 1
                        snapshot = row['snapshot']
                        if legal and snapshot is not None and (snapshot['count'] != len(packet) or
                            bytes.fromhex(snapshot['decoded'])[:len(payload) + 1] != packet[:len(payload) + 1]):
                            tails['legal_payload_mismatch'] += 1
                        if not legal and published:
                            tails['illegal_published'] += 1
                            if len(tails['examples']) < 8:
                                tails['examples'].append(dict(packet=packet.hex(), tail=tail, result=row))
    return dict(cases=rows, eop_matrix=eop, crossover=crossover, tail_matrix=tails)
