"""Bounded original-v2.6 handler observations over a supplied pinned artifact.

This executes the original assembly handler and serializer, not the C request
dispatcher. In particular, publication of a short SETUP is not proof that its
memory command executes: usbdrv.c separately requires an eight-byte SETUP.
"""
from model import CPU, h, Bits, bind, wire_model as p, tx_ownership
from tests35.test_usb_crossover import single_crossover


def wire(packet, rate=1500000, width=None):
    return p.eop_wave(packet, 2 * 16000000 / rate if width is None else width, rate)


def execute(artifact, cpu, wave, entry=8):
    """Run original handler words to return and capture state plus GPIO timing."""
    cpu.pc = artifact['symbols']['USB_handler']
    cpu.t = wave.start + entry
    cpu.raw_stack.clear()
    cpu.calls.append(0xfffe)
    cpu.bus_events = []
    cpu.io = h.SynchronizedPinIO(cpu, wave)
    cpu.io.cleared_at = -1
    symbols = artifact['symbols']
    names = ('se0', 'handleIn', 'handleSetupOrOut', 'handleData', 'sendAckAndReti',
             'sendNakAndReti', 'usbSendAndReti', 'ignorePacket')
    checkpoints = {name: [] for name in names}
    watched = {symbols[name]: name for name in names}
    for _ in range(20000):
        if cpu.pc == 0xfffe:
            break
        if cpu.pc in watched:
            checkpoints[watched[cpu.pc]].append(dict(time=cpu.t, Y=cpu.word(28),
                                                     count=cpu.r[19], pair=cpu.r[22],
                                                     history=cpu.r[18]))
        cpu.step()
    else:
        raise AssertionError('Official historical handler did not return')
    if cpu.raw_stack:
        raise AssertionError('Official historical handler left an unbalanced stack')
    first_k = next((when for when, io, value in cpu.bus_events
                    if io == 11 and value & 6 == h.K), None)
    return dict(rx=bytes(cpu.m[symbols['usbRxBuf']:symbols['usbRxBuf'] + 11]).hex(),
                rxlen=cpu.m[symbols['usbRxLen']], rxtoken=cpu.m[symbols['usbRxToken']],
                current_token=cpu.m[symbols['usbCurrentTok']], txlen=cpu.m[symbols['usbTxLen']],
                address=cpu.m[symbols['usbDeviceAddr']], checkpoints=checkpoints,
                response_cycles=None if first_k is None else first_k-wave.boundaries[-2],
                bus=cpu.bus_events, tx_ownership=tx_ownership(cpu.bus_events), cycles=cpu.t)


def run(artifact, packet=None, wave=None, entry=8, rate=1500000, width=None,
        address=0, token=0, txlen=0x5a, txpacket=None, new_address=None):
    """Seed original SRAM globals without invoking its foreground C dispatcher."""
    bind(artifact)
    wave = wave or wire(packet, rate, width)
    cpu = CPU(artifact, wave, entry)
    symbols = artifact['symbols']
    cpu.m[symbols['usbDeviceAddr']] = address * 2
    cpu.m[symbols['usbNewDeviceAddr']] = address if new_address is None else new_address
    cpu.m[symbols['usbInputBufOffset']] = 0
    cpu.m[symbols['usbCurrentTok']] = token
    cpu.m[symbols['usbTxLen']] = txlen
    if txpacket is not None:
        cpu.m[symbols['usbTxBuf']:symbols['usbTxBuf'] + len(txpacket)] = txpacket
    return execute(artifact, cpu, wave, entry), cpu


def audit(artifact):
    """Collect the bounded token/DATA, retry, address and crossover comparisons."""
    rows = []

    def record(name, packet=None, **kwargs):
        row, cpu = run(artifact, packet, **kwargs)
        row['case'] = name
        rows.append(row)
        return row, cpu

    for endpoint in (0, 1, 2, 15):
        record(f'IN_endpoint_{endpoint}', h.token(0x69, endpoint=endpoint))
    token = h.token(0x69)
    for bit in (3, 7):
        record(f'IN_bad_CRC5_bit_{bit}', token[:2] + bytes([token[2] ^ (1 << bit)]))
    for incoming, active in ((7, 7), (0, 7), (7, 0)):
        record(f'address_{incoming}_active_{active}', h.token(0x69, address=incoming), address=active)
    for length in (1, 2, 3, 4):
        record(f'IN_token_length_{length}', (token + b'\0')[:length])
    setup = bytes((0x40, 1, 0, 0, 0x80, 0, 0, 0))
    data = h.data_packet(setup)
    record('valid_SETUP_DATA0', data, token=0x2d)
    record('SETUP_DATA1', h.data_packet(setup, 0x4b), token=0x2d)
    record('DATA_unpaired', data)
    record('DATA_one_CRC_byte', data[:-1], token=0x2d)
    record('DATA_bad_numeric_CRC16', data[:-1] + bytes([data[-1] ^ 0x80]), token=0x2d)
    for length in (1, 2, 3):
        record(f'OUT_status_length_{length}', h.data_packet(b'', 0x4b)[:length], token=0xe1)

    packet = h.data_packet(b'\xff' * 8)
    encoded, stuffed = p.bits_wave(packet)
    for position in (stuffed[0], stuffed[len(stuffed) // 2], stuffed[-1]):
        raw = encoded.bits.copy()
        raw[position] = 1
        record(f'bad_stuffed_zero_{position}', wave=p.from_bits(raw), token=0x2d)
    for length in range(7):
        record(f'DATA_one_dribble_{length}', wave=p.from_bits(encoded.bits + [1] * length), token=0x2d)
    for length in range(1, 6):
        record(f'DATA_illegal_zero_tail_{length}', wave=p.from_bits(encoded.bits + [0] * length), token=0x2d)
    for length in range(5):
        record(f'ACK_one_dribble_{length}', wave=p.from_bits(h.Wave(b'\xd2').bits + [1] * length))
    for pid in (0x69, 0x2d, 0xe1):
        for rate in (1499250, 1500750):
            for width in (10.72, 2 * 16000000 / rate, 24):
                record(f'EOP_{pid:02x}_{rate}_{width}', h.token(pid), width=width, rate=rate)

    first, cpu = record('IN_cached_ZLP_without_host_ACK', h.token(0x69),
                        txlen=4, txpacket=h.data_packet(b'', 0x4b))
    repeat_wave = wire(h.token(0x69))
    repeat_cpu = CPU(artifact, repeat_wave, 8)
    repeat_cpu.m[:] = cpu.m
    repeated = execute(artifact, repeat_cpu, repeat_wave)
    retry = dict(host_ack_received=False, first=first, second_identical_in=repeated)
    address, _ = run(artifact, h.token(0x69), txlen=4,
                     txpacket=h.data_packet(b'', 0x4b), new_address=5)

    # Keep the previously observed focused counterexample reproducible without
    # a broad unbounded search. The excursion is a possible digital envelope.
    pristine = h.Wave(packet, rate=1499250,
                      jitter=lambda index, line: -0.55 if line == h.J else 0.55)
    crossed = single_crossover(pristine, 69, width=3.36, fraction=0)
    crossing, _ = run(artifact, wave=crossed, entry=8, token=0x2d)
    crossover = dict(rate=1499250, entry=8, physical_crossing=69,
                     true_eop=pristine.boundaries[-3], result=crossing,
                     premature_drive=any(when < pristine.boundaries[-3] and io == 10 and value & 6
                                         for when, io, value in crossing['bus']))
    controls = {row['case']: row for row in rows}
    assert controls['IN_endpoint_0']['checkpoints']['handleIn']
    assert controls['address_7_active_7']['checkpoints']['handleIn']
    assert not controls['address_0_active_7']['bus'] and not controls['address_7_active_0']['bus']
    assert controls['valid_SETUP_DATA0']['rxlen'] == 11 and controls['DATA_unpaired']['rxlen'] == 0
    return dict(cases=len(rows), rows=rows, lost_ack_retry=retry,
                prepared_address_without_host_ack=address, crossover=crossover,
                c_setup_length_guard='usbdrv.c rejects SETUP payload length !=8; short assembly RX publication alone does not prove an application action',
                scope='Original assembly receiver/serializer only; foreground C request actions are not executed')
