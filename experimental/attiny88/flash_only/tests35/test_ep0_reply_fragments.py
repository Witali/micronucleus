"""Independent packet/CRC/ZLP oracle for bounded EP0 Flash replies."""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind


class Quiet:
    pin_edges=[]
    def level(self,time):return h.J
    def cell(self,time):return 'IDLE'
    def edge_since(self,start,end):return False


def crc16(payload):
    value=0xffff
    for byte in payload:
        value^=byte
        for _ in range(8):value=(value>>1)^(0xa001 if value&1 else 0)
    return ((~value)&0xffff).to_bytes(2,'little')


def advance(cpu):
    cpu.pc=cpu.labels['usb_tx_prepare_pending_reply']
    published=False
    for _ in range(3000):
        if cpu.pc==cpu.labels['usb_tx_publish_packet_length']:published=True
        if cpu.pc==cpu.labels['bootloader_check_idle_timeout']:
            return 'packet' if published else 'idle'
        cpu.step()
    raise AssertionError('reply preparation did not reach its bounded checkpoint')


def check_art(artifact):
    packets=0
    for length in range(19):
        bind(artifact)
        cpu=h.CPU(artifact,Quiet())
        pointer=artifact['boot']+20
        payload=bytes(cpu.flash[pointer+i] for i in range(length))
        cpu.r[14:16]=[pointer&255,pointer>>8]
        cpu.r[9]=0xc3
        cpu.r[12]=0xff  # source shorter than requested wLength
        cpu.m[0x100]=length
        cpu.m[0x10f]=0x5a
        sizes=[];remaining=length
        while remaining>=8:sizes.append(8);remaining-=8
        sizes.append(remaining)
        used=0;pid=0xc3
        for count in sizes:
            assert advance(cpu)=='packet',(length,count,hex(cpu.pc),cpu.m[0x100],cpu.m[0x10f])
            pid^=0x88
            actual=bytes(cpu.m[0x101:0x104+count])
            block=payload[used:used+count]
            assert actual==bytes([pid])+block+crc16(block),(length,count,actual.hex())
            assert cpu.m[0x10f]==count+4
            used+=count
            assert cpu.word(14)==pointer+used
            # A prepared DATA reply remains immutable before its ACK.
            before=bytes(cpu.m[0x100:0x10c]),cpu.word(14)
            assert advance(cpu)=='idle'
            assert (bytes(cpu.m[0x100:0x10c]),cpu.word(14))==before
            cpu.m[0x10f]=0x5a
            packets+=1
        assert advance(cpu)=='idle'
        assert cpu.m[0x100]&0x80 and used==length
    return packets


def test():
    artifact=h.build()
    count=check_art(artifact)
    print('PASS',count,'reply packets across all19 supported lengths; exact PID/CRC/ZLP and immutable pending DATA')


if __name__=='__main__':test()
