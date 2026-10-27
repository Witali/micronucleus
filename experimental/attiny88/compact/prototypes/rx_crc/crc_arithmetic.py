"""Independent arithmetic proof and emitted-opcode CRC kernel measurements.

The fast-byte kernel is adapted from the official V-USB usbdrvasm.S fast CRC
routine by Slawomir Fras and Shay Green, GPL v2/v3, copyright Objective
Development and contributors. Only register allocation and the call wrapper
differ. It uses no lookup tables and no MUL instruction.
"""
from functools import lru_cache
import json
import random
from probe import OWN, build, Timed, dec


def normal_bit(state, bit):
    return (state >> 1) ^ (0xA001 if (state ^ bit) & 1 else 0)


def alternate_bit(state, bit):
    return (state >> 1) ^ (bit << 15) ^ (0xA001 if state & 1 else 0)


def advance(state, count=16):
    for _ in range(count):
        state = normal_bit(state, 0)
    return state


def unit_source(body):
    return ('.text\n.org 0x100\n.global bootloader_start\nbootloader_start:\n'
            'usb_control_process_received_packet:\nbootloader_poll_begin:\n'
            'bootloader_start_application:\n' + body + '\nret\n')


def machine(artifact):
    cpu = Timed(artifact, {'memory': bytearray(0x300), 'registers': [0] * 32})
    cpu.pc, cpu.calls = 0x100, [0xFFFF]
    cpu.r[0], cpu.r[24], cpu.r[25] = 0xA5, 0x5A, 0xC3
    cpu.r[26:28] = [0x34, 0x12]
    return cpu


def execute(cpu):
    while cpu.pc != 0xFFFF:
        cpu.step()
    assert cpu.r[0] == 0xA5 and cpu.r[1] == 0 and cpu.r[24:26] == [0x5A, 0xC3] and cpu.r[26:28] == [0x34, 0x12]


if __name__ == '__main__':
    # The alternative state inserts the incoming carry directly at bit15. Its
    # standard counterpart is A^16(state), so no input-bit XOR is needed.
    assert advance(0x1557) == 0xFFFF and advance(0xFFFF) == 0xB001
    for state in range(65536):
        mapped = advance(state)
        for bit in (0, 1):
            assert advance(alternate_bit(state, bit)) == normal_bit(mapped, bit)
    stream_meta, stream_manifest = build('crc_stream_kernel', unit_source('''ror r19
ror r2
brcc .Ldone
eor r2, r29
eor r19, r30
.Ldone:'''), boot=0x100)
    dec.decode = lru_cache(maxsize=16384)(getattr(dec.decode, '__wrapped__', dec.decode))
    streaming_cases, streaming_times = 0, set()
    # Exhaust all states and both bit values mathematically above. The emitted
    # kernel gets all feedback/input combinations plus random representative
    # register values, checked against the independently expressed recurrence.
    rng = random.Random(0xC16)
    for state in [0, 1, 2, 65535, 0x8000, 0xA001, 0x1557] + [rng.randrange(65536) for _ in range(1024)]:
        for bit in (0, 1):
            cpu = machine(stream_meta)
            cpu.r[2], cpu.r[19] = state & 255, state >> 8
            cpu.r[29], cpu.r[30] = 1, 0xA0
            cpu.setflag(0, bit)
            execute(cpu)
            assert cpu.r[2] | cpu.r[19] << 8 == alternate_bit(state, bit)
            streaming_times.add(cpu.t - 4)  # Exclude RET; no call in inline form.
            streaming_cases += 1

    fast_meta, fast_manifest = build('crc_fast_byte_kernel', unit_source('''eor r30, r2
mov r31, r30
swap r30
eor r30, r31
mov r2, r30
lsr r30
lsr r30
eor r30, r2
inc r30
andi r30, 2
cp r1, r30
ror r31
ror r30
mov r2, r30
eor r2, r19
mov r19, r31
lsr r31
ror r30
eor r19, r31
eor r2, r30'''), boot=0x100)
    dec.decode = lru_cache(maxsize=16384)(getattr(dec.decode, '__wrapped__', dec.decode))
    fast_cases, fast_times = 0, set()
    # A^8 is linear: validate all 256 mixed input values for every possible old
    # high byte, plus every old low byte with varied input. The first rectangle
    # spans all possible (old-high, old-low XOR data) states of a byte update.
    for high in range(256):
        for mixed in range(256):
            low, value = high ^ 0xA5, mixed ^ high ^ 0xA5
            state = low | high << 8
            expected = state
            for bit in range(8):
                expected = normal_bit(expected, (value >> bit) & 1)
            cpu = machine(fast_meta)
            cpu.r[2], cpu.r[19], cpu.r[30] = low, high, value
            execute(cpu)
            assert cpu.r[2] | cpu.r[19] << 8 == expected
            fast_times.add(cpu.t - 4)
            fast_cases += 1
    result = dict(transformed_state_exhaustive_cases=131072,
                  transformed_init='0x1557', transformed_good_residue='0xffff', standard_good_residue='0xb001',
                  streaming_kernel=dict(manifest=stream_manifest, emitted_cases=streaming_cases, cycles_without_ret=sorted(streaming_times), extra_decoded_carry_restore_cycles=1),
                  fast_byte_kernel=dict(manifest=fast_manifest, emitted_cases=fast_cases, cycles_without_ret=sorted(fast_times), extra_payload_copy_cycles=1))
    (OWN / 'crc-arithmetic-results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
