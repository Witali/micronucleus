"""Every RX outcome restores the cooperative caller's context pointer."""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind, Bits


def finish(cpu):
    for _ in range(10000):
        if cpu.pc==0xfffe:
            assert cpu.word(28)==0x100 and cpu.word(30)==0x100
            return
        cpu.step()
    raise AssertionError('RX handler did not return within its packet bound')


def test():
    artifact=h.build()
    packets=[h.token(0x69,endpoint=1),h.token(0x69,address=1),
             h.token(0x69)[:-1]+b'\0',bytes([0,0,0]),
             h.data_packet(b''),h.data_packet(bytes(7)),
             h.token(0x2d),h.token(0x69)]
    for packet in packets:
        bind(artifact)
        cpu=h.CPU(artifact,Bits(packet))
        cpu.r[8]=0x10
        cpu.m[0x10f]=0x5a
        finish(cpu)
        assert cpu.m[0x112]==0
    bind(artifact)
    cpu=h.CPU(artifact,Bits(h.data_packet(bytes(range(8)))))
    cpu.r[8]=0x10
    cpu.m[0x10f]=0x5a
    cpu.m[0x114]=0x2d
    finish(cpu)
    assert cpu.m[0x112]==11
    bind(artifact)
    cpu=h.CPU(artifact,Bits(b'\xd2'))
    cpu.r[2]=12
    cpu.m[0x10f]=12
    finish(cpu)
    assert cpu.r[2]==0 and cpu.m[0x10f]==0x5a
    print('PASS 10 RX context-restoration cases: ignored packets, token timeout, IN, DATA and ACK')


if __name__=='__main__':test()
