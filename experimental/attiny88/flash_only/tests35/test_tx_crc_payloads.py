"""Independent CRC16 oracle for emitted outgoing DATA packets."""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.test_ep0_standard import Quiet
from tests35.test_ep0_reply_fragments import advance,crc16

def test():
    art=h.build();count=0
    for length in range(9):
        for seed in range(256):
            bind(art);cpu=h.CPU(art,Quiet())
            payload=bytes((seed+37*i)&255 for i in range(length))
            cpu.flash.memory[0x80:0x80+length]=payload
            cpu.r[14:16]=[0x80,0];cpu.r[9]=0xc3
            cpu.m[0x100]=length;cpu.m[0x10f]=0x5a
            assert advance(cpu)=='packet'
            assert bytes(cpu.m[0x101:0x104+length])==b'\x4b'+payload+crc16(payload),(length,seed)
            assert cpu.word(14)==0x80+length and cpu.m[0x10f]==length+4
            count+=1
    print('PASS independent outgoing CRC16/PID/pointer/publication:',count,'payloads')

if __name__=='__main__':test()
