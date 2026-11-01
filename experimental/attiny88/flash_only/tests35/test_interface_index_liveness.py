"""In-place interface-index validation accepts only the zero 16-bit index."""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_ep0_standard import Quiet


def test():
    art = h.build()
    bind(art)
    low = art['symbols']['usb_standard_dispatch'] - art['boot']
    high = art['symbols']['usb_standard_endpoint_in'] - art['boot']
    matches = [offset for offset in range(low, high, 2)
               if int.from_bytes(art['body'][offset:offset+2], 'little') == 0x28ef]
    assert len(matches) == 1, 'expected interface OR R14,R15 before endpoint block'
    pc = art['boot'] + matches[0]
    cpu = h.CPU(art, Quiet())
    for index in range(65536):
        cpu.r[14:16] = [index & 255, index >> 8]
        before = cpu.r.copy()
        cpu.pc = pc
        cpu.steps = 0
        cpu.step()
        assert bool(cpu.flag(1)) == (index == 0)
        cpu.step()
        expected = cpu.labels['usb_standard_stall'] if index else pc+4
        assert cpu.pc == expected
        assert cpu.r[15:] == before[15:] and cpu.r[:14] == before[:14]
        assert cpu.r[14] == ((index & 255) | (index >> 8))
        assert not cpu.bus_events
    print('PASS all emitted interface-index predicates, branch and live registers:', 65536)


if __name__ == '__main__':
    test()
