"""Check PCIF W1C completion using OUT/SBI words from the linked firmware.

The event before/after cases do not depend on simultaneous clear/set priority.
The equal-clock case checks each explicitly selected model policy separately;
it does not claim that the datasheet specifies either electrical priority.
"""
from tests35 import ep0_model as h
from tests27 import waveform_model as wire


class Edge:
    """One physical D+ transition, without constructing a USB packet."""
    def __init__(self, when):
        self.when = when
        self.pin_edges = [when]

    def level(self, when):
        return wire.J if when < self.when else wire.K

    def cell(self, when):
        return 'before-edge' if when < self.when else 'after-edge'

    def edge_since(self, start, end):
        return start < self.when <= end


def instructions(art):
    """Select actual PCIF2 writes and a read from emitted executable words."""
    h.dec.START = art['boot']
    h.dec.raw = art['body']
    found = {}
    pc = art['symbols']['USB_handler']
    end = art['boot'] + len(art['body'])
    while pc < end:
        word = int.from_bytes(art['body'][pc-art['boot']:pc-art['boot']+2], 'little')
        ins = h.raw_decode(pc)
        assert not ins.unknown, ('unknown executable word', hex(pc), hex(word))
        if word & 0xf800 == 0xb800:
            address = ((word >> 5) & 0x30) | (word & 15)
            if address == 0x1b:
                found.setdefault('out', (pc, (word >> 4) & 31, word))
        elif word & 0xff00 == 0x9a00 and (word >> 3) & 31 == 0x1b and word & 7 == 2:
            found.setdefault('sbi', (pc, None, word))
        elif word & 0xff00 in (0x9900, 0x9b00) and (word >> 3) & 31 == 0x1b and word & 7 == 2:
            found.setdefault('read', (pc, None, word))
        pc += ins.size
    assert found.keys() >= {'out', 'sbi', 'read'}, ('missing emitted PCIF instructions', found)
    return found


def test():
    art = h.build()
    writes = instructions(art)
    previous_priority = wire.CLEAR_SET_WINS
    count = 0
    try:
        for synchronized in (False, True):
            io_type = wire.SynchronizedPinIO if synchronized else wire.PinIO
            for set_wins in (False, True):
                wire.CLEAR_SET_WINS = set_wins
                for name, duration in (('out', 1), ('sbi', 2)):
                    pc, register, word = writes[name]
                    for start in (100, 100 + 1/3, 100.677328003):
                        for delta in (-1, 0, 1):
                            clear = start + duration
                            # At phase n, this input edge creates one PCIF set
                            # event at n+3 in Figure 9-1's existing pipeline.
                            edge = clear + delta - (2.9 if synchronized else 0)
                            cpu = h.CPU(art, Edge(edge))
                            cpu.pc = pc
                            cpu.t = start
                            cpu.io = io_type(cpu, Edge(edge))
                            if register is not None:
                                cpu.r[register] = 4
                            ins = cpu.step()
                            context = (name, hex(word), synchronized, set_wins, start, delta)
                            assert ins.op == name, context
                            assert cpu.t == clear, ('instruction completion', context, cpu.t, clear)
                            assert cpu.io.cleared_at == clear, ('W1C completion', context, cpu.io.cleared_at, clear)
                            assert not hasattr(cpu, 'io_write_cycles'), ('instruction metadata leaked', context)
                            expected = 4 if delta > 0 or (delta == 0 and set_wins and synchronized) else 0
                            if synchronized:
                                assert cpu.io.flag_events == [clear+delta], ('fixture set event', context, cpu.io.flag_events)
                            # Execute the real bit-test after the event arrives.
                            cpu.t = clear + 2
                            cpu.pc = writes['read'][0]
                            assert cpu.io.get(0x1b, 0) == expected, ('retained event', context, expected)
                            before = cpu.pc
                            read = cpu.step()
                            skipped = bool(expected) == (read.op == 'sbis')
                            assert (cpu.pc > before+2) == skipped, ('emitted flag read', context, cpu.pc, before)
                            count += 1
        # An OUT of zero must not clear a previously latched PCIF2 event.
        for io_type in (wire.PinIO, wire.SynchronizedPinIO):
            cpu = h.CPU(art, Edge(90.1))
            cpu.t = 100
            cpu.pc, register, _ = writes['out']
            cpu.r[register] = 0
            cpu.io = io_type(cpu, Edge(90.1))
            previous_clear = cpu.io.cleared_at
            cpu.step()
            assert cpu.io.cleared_at == previous_clear
            assert cpu.io.get(0x1b, 0) == 4
            count += 1
        # Legacy direct fixture writes always retain their two-clock default,
        # including immediately after a real one-clock OUT or two-clock SBI.
        for io_type in (wire.PinIO, wire.SynchronizedPinIO):
            for name in ('out', 'sbi'):
                cpu = h.CPU(art, Edge(90.1))
                cpu.t = 100
                cpu.pc, register, _ = writes[name]
                if register is not None:
                    cpu.r[register] = 4
                cpu.io = io_type(cpu, Edge(90.1))
                cpu.step()
                assert not hasattr(cpu, 'io_write_cycles'), (name, 'instruction metadata leaked')
                completed = cpu.t
                cpu.io[0x1b] = 4
                assert cpu.io.cleared_at == completed+2, (name, 'direct fixture fallback', cpu.io.cleared_at, completed)
                count += 1
    finally:
        wire.CLEAR_SET_WINS = previous_priority
    assert count == 78, count
    print('PASS emitted PCIF OUT/SBI completion and retained events:', count,
          'cases; both same-clock policies tested separately')


if __name__ == '__main__':
    test()
