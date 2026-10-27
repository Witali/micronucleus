"""Check RESET initialization and disconnect time from actual AVR words.

The two-instruction countdown is accelerated only after checking its exact
opcodes. All outer iterations and register/SRAM/IO effects are executed. This
is a digital initialization check, not a watchdog or USB electrical model.
"""


def check_startup(artifact):
    code, base, labels = artifact['body'], artifact['boot'], artifact['symbols']
    registers = [(37 * i + 91) & 255 for i in range(32)]
    memory = bytearray([0xA5] * 0x300)
    io = {0x34: 0x0B}  # MCUSR contains several simultaneous RESET causes.
    writes, clears, delays, watchdog_resets = [], [], [], []
    cycles, zero = 0, False
    pc = labels['startup']

    def word(address):
        return int.from_bytes(code[address - base:address - base + 2], 'little')

    def output(address, value):
        writes.append((cycles, address, value))
        io[address] = value

    for _ in range(2000):
        if pc == labels['bootloader_poll_begin']:
            break
        opcode, next_pc, duration = word(pc), pc + 2, 1
        destination = (opcode >> 4) & 31
        source = (opcode & 15) | ((opcode >> 5) & 16)
        immediate = ((opcode >> 4) & 0xF0) | (opcode & 15)
        if pc == labels['usb_disconnect_delay_inner']:
            # SBIW r24,1; BRNE -4: 2 + 2 cycles, last branch takes one.
            assert opcode == 0x9701 and word(pc + 2) == 0xF7F1
            count = registers[24] | registers[25] << 8
            assert count > 0
            delays.append(count)
            registers[24:26] = [0, 0]
            zero, duration, next_pc = True, 4 * count - 1, pc + 4
        elif opcode & 0xF000 == 0xE000:
            registers[16 + ((opcode >> 4) & 15)] = immediate
        elif opcode & 0xFC00 == 0x2400:
            registers[destination] ^= registers[source]
            zero = registers[destination] == 0
        elif opcode & 0xFC00 == 0x2C00:
            registers[destination] = registers[source]
        elif opcode & 0xFF00 == 0x0100:
            target, origin = 2 * ((opcode >> 4) & 15), 2 * (opcode & 15)
            registers[target:target + 2] = registers[origin:origin + 2]
        elif opcode & 0xF800 in (0xB000, 0xB800):
            address = ((opcode >> 5) & 0x30) | (opcode & 15)
            if opcode & 0x0800:
                output(address, registers[destination])
            else:
                registers[destination] = io.get(address, 0)
        elif opcode & 0xFE0F == 0x9200:
            output(word(pc + 2) - 0x20, registers[destination])
            next_pc, duration = pc + 4, 2
        elif opcode & 0xFE0F == 0x920A:
            address = (registers[28] | registers[29] << 8) - 1
            assert io.get(0x0A, 0) & 2, 'SRAM clear must occur during disconnect'
            registers[28:30] = [address & 255, address >> 8]
            memory[address] = registers[destination]
            clears.append(address)
            duration = 2
        elif opcode & 0xD208 in (0x8208, 0x8200):
            # Execute real Y/Z indirect stores, including memory-mapped IO.
            offset = (opcode & 7) | ((opcode >> 7) & 24) | ((opcode >> 8) & 32)
            pair = 28 if opcode & 8 else 30
            address = (registers[pair] | registers[pair + 1] << 8) + offset
            if address < 0x100:
                assert 0x20 <= address < 0x100
                output(address - 0x20, registers[destination])
            else:
                memory[address] = registers[destination]
            duration = 2
        elif opcode & 0xFF00 in (0x9800, 0x9A00):
            address, bit = (opcode >> 3) & 31, opcode & 7
            value = io.get(address, 0)
            output(address, value | (1 << bit) if opcode & 0x0200 else value & ~(1 << bit))
            duration = 2
        elif opcode & 0xF000 == 0x3000:
            zero = registers[16 + ((opcode >> 4) & 15)] == immediate
        elif opcode & 0xFC07 in (0xF001, 0xF401):
            taken = zero if opcode & 0x0400 == 0 else not zero
            if taken:
                displacement = (opcode >> 3) & 127
                if displacement & 64:
                    displacement -= 128
                next_pc += 2 * displacement
                duration = 2
        elif opcode == 0x95A8:
            watchdog_resets.append(cycles)
        else:
            raise AssertionError(('unexpected startup opcode', hex(pc), hex(opcode)))
        pc, cycles = next_pc, cycles + duration
    else:
        raise AssertionError('Startup failed to reach polling')

    assert len(delays) == 44 and len(set(delays)) == 1
    assert clears == list(range(0x12B, 0xFF, -1))
    expected = bytearray([0xA5] * 0x300)
    expected[0x100:0x12C] = bytes(44)
    expected[0x10F], expected[0x100] = 0x5A, 0xFF
    assert memory == expected, 'Clear/store escaped the exact USB context'
    assert registers[1] == registers[3] == registers[8] == 0
    assert registers[4:8] == [0] * 4 and registers[28:30] == [0, 1]
    assert io[0x1E] == 0x0B and io[0x34] == io[0x40] == 0
    watchdog = [(t, value) for t, address, value in writes if address == 0x40]
    assert len(watchdog) == 2 and watchdog[0][1] == 0x18 and watchdog[1][1] == 0
    assert watchdog[1][0] - watchdog[0][0] == 2
    captured = [t for t, address, value in writes if address == 0x1E and value == 0x0B]
    cleared = [t for t, address, value in writes if address == 0x34 and value == 0]
    assert len(captured) == len(cleared) == 1
    assert captured[0] < cleared[0] < watchdog[0][0]
    assert watchdog_resets and watchdog_resets[0] < watchdog[0][0]
    disconnect = [(t, value) for t, address, value in writes if address == 0x0A][:2]
    assert disconnect[0][1] & 2 and not disconnect[1][1] & 2
    assert watchdog[-1][0] < disconnect[0][0], 'Disable inherited watchdog before delay'
    duration = disconnect[1][0] - disconnect[0][0]
    assert 4_800_000 <= duration <= 4_832_000  # 300..302 ms at 16 MHz.
    enabled = [(t, value) for t, address, value in writes if address in (0x4D, 0x48)]
    assert len(enabled) == 2 and all(value == 4 for _, value in enabled)
    assert enabled[0][0] > disconnect[1][0]
    print('PASS', artifact['mode'], 'RESET state, exact 44-byte clear, watchdog order,',
          f'disconnect {duration / 16000:.6f} ms; USB enabled last')


if __name__ == '__main__':
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from build_candidate import checked_build, MODES
    for mode in MODES:
        check_startup(checked_build(mode))
