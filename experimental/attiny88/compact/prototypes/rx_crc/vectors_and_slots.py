"""CRC field-scope vectors and best-case reusable delay-slot counts."""
import json
import random
from probe import OWN, Wave, build, freeze, receive, data_packet
from crc_arithmetic import alternate_bit, normal_bit

# Downloaded official primary sources were inspected in the original scratch
# experiment. Preserve their identities, not their external tables or files.
OFFICIAL_PRIOR_ART = [
    dict(file='vusb-usbdrvasm18-crc.inc',
         url='https://github.com/obdev/v-usb/blob/master/usbdrv/usbdrvasm18-crc.inc',
         sha256='fe25c95cdc4e503475f04bc8888dcedcb27596db18cb04aec4d073b659a677ff'),
    dict(file='vusb-usbdrvasm.S',
         url='https://github.com/obdev/v-usb/blob/master/usbdrv/usbdrvasm.S',
         sha256='ad37642c953091124fed7c5b060a52974c227cab1ad0c9e04e4e5f3a5acc5a79'),
]


def checksum(payload):
    state = 65535
    for value in payload:
        for bit in range(8):
            state = normal_bit(state, (value >> bit) & 1)
    return (state ^ 65535).to_bytes(2, 'little')


def decoded_data_bits(packet):
    wave = Wave(packet)
    bits, ones, discarded = [], 0, 0
    for bit in wave.bits:
        if ones == 6:
            assert bit == 0
            ones, discarded = 0, discarded + 1
        else:
            bits.append(bit)
            ones = ones + 1 if bit else 0
    rebuilt = bytes(sum(bits[index + bit] << bit for bit in range(8))
                    for index in range(0, len(bits), 8))
    assert rebuilt == bytes([0x80]) + packet
    return bits[16:], discarded  # Exclude SYNC and PID, retain received CRC16.


def residue(packet):
    bits, discarded = decoded_data_bits(packet)
    state = 0x1557
    for bit in bits:
        state = alternate_bit(state, bit)
    return state, discarded


if __name__ == '__main__':
    patterns = [bytes([value]) * length for length in range(9) for value in range(256)]
    patterns += [random.Random(1000 + value).randbytes(value % 9) for value in range(128)]
    vectors = stuffed = mutations = 0
    for pid in (0xC3, 0x4B):
        for payload in patterns:
            packet = bytes([pid]) + payload + checksum(payload)
            actual, discarded = residue(packet)
            assert actual == 65535, (packet.hex(), hex(actual))
            vectors += 1
            stuffed += discarded
    for pid in (0xC3, 0x4B):
        for length in range(9):
            for payload in (bytes(length), bytes([255]) * length,
                            bytes(range(length)), random.Random(121 + length).randbytes(length)):
                packet = bytes([pid]) + payload + checksum(payload)
                for bit in range(8 * (len(packet) - 1)):
                    damaged = bytearray(packet)
                    damaged[1 + bit // 8] ^= 1 << (bit % 8)
                    assert residue(bytes(damaged))[0] != 65535
                    mutations += 1

    meta, manifest = build('baseline', freeze())
    body = (OWN / 'baseline_body.bin').read_bytes()
    slot_rows = []
    for name, payload in [('zero8', bytes(8)), ('ff8', bytes([255]) * 8), ('ramp8', bytes(range(8)))]:
        result = receive(meta, data_packet(payload), trace=True)
        assert result['ok']
        stores = [item for item in result['history'] if item['op'] == 'st' and item['operands'] == 'Y+, r20']
        earliest = stores[1]['time']  # First complete payload byte available.
        available = []
        for item in result['history']:
            if item['time'] <= earliest:
                continue
            offset = item['pc'] - meta['start']
            word = int.from_bytes(body[offset:offset + 2], 'little')
            if word in (0x0000, 0xC000):
                available.append(dict(pc=hex(item['pc']), cycles=1 if word == 0 else 2,
                                      reason='NOP' if word == 0 else 'RJMP to next word'))
        slot_rows.append(dict(packet=name, after_first_payload_complete=earliest,
                              replaceable_delay_cycles=sum(item['cycles'] for item in available), slots=available,
                              required_fast_byte_arithmetic_cycles=8 * 20,
                              required_payload_copy_cycles=8))
    output = dict(valid_vectors=vectors, removed_stuffed_bits=stuffed,
                  bad_payload_or_crc_single_bit_mutations=mutations, good_alternate_residue='0xffff',
                  scope='Arithmetic/field-scope proof only; neither rejected integration is a working CRC receiver.',
                  baseline=manifest, delay_slots=slot_rows,
                  official_prior_art=OFFICIAL_PRIOR_ART)
    (OWN / 'vectors-and-slots.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output, indent=2))
