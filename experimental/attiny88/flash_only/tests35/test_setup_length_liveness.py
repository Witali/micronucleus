"""All 16-bit wLength values preserve reply limits after in-place zero testing.

A nonzero high byte makes every supported source shorter than wLength, so
changing its low byte cannot change the reply count or terminating-ZLP flag.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_ep0_standard import Quiet


def test():
    original = h.build()
    bind(original)
    art = dict(original, symbols=original['symbols'].copy())
    low = art['symbols']['usb_setup_capture_fields'] - art['boot']
    high = art['symbols']['usb_standard_dispatch'] - art['boot']
    words = [offset for offset in range(low, high, 2)
             if int.from_bytes(art['body'][offset:offset+2], 'little') == 0x2867]
    assert len(words) == 1, 'expected the emitted OR R6,R7 zero test'
    pc = art['boot'] + words[0]
    art['symbols'].update(length_or_probe=pc, length_or_done=pc+2)
    cpu = h.CPU(art, Quiet())
    cpu.raw_stack.clear()
    cpu.r[1] = 0
    cpu.r[28:32] = [0, 1, 0, 1]
    counts = (0, 1, 2, 8, 18)
    cases = 0
    for length in range(65536):
        # Each length is an independent bounded probe; reuse the decoded CPU.
        cpu.steps = 0
        low, high = length & 255, length >> 8
        cpu.r[6:8] = [low, high]
        cpu.pc = pc
        cpu.step()
        assert cpu.pc == pc + 2 and bool(cpu.flag(1)) == (length == 0)
        assert cpu.r[6:8] == [low | high, high]
        for source in counts:
            cpu.r[24] = source
            cpu.r[12] = 0x5a
            cpu.pc = cpu.labels['usb_reply_limit_length']
            for _ in range(30):
                if cpu.pc == cpu.labels['usb_reply_store_length']:
                    break
                cpu.step()
            else:
                raise AssertionError(('limiter did not return', source, length))
            assert cpu.r[24] == min(source, length), (source, length, cpu.r[24])
            assert cpu.r[12] == (255 if source < length else 0)
            assert not cpu.raw_stack and not cpu.bus_events
            cases += 1
    print('PASS setup zero classification and emitted limiter for all wLength:', 65536, cases)


if __name__ == '__main__':
    test()
