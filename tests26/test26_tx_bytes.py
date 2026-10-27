"""Execute actual TX-copy and CRC instructions for Flash, EEPROM and SRAM.
Tests EEPROM source selector moved from bit1 to bit7 without altering USB responses.
"""
from pathlib import Path
import random, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from check_build import build
from tests.avr_exec23 import AVRExec

SRC=ROOT/'variants/strict_usb_optimized/micronucleus_t88_pass26.S'
OLD=ROOT/'variants/strict_usb_optimized/micronucleus_t88_pass22.S'


def execute_tx(art, source, offset, data):
    x=AVRExec(art)
    x.r[28]=0;x.r[29]=1;x.r[23]=len(data);x.r[24]=0
    x.r[2]={'flash':0,'sram':1,'eeprom':0x80 if art['source']==str(SRC) else 2}[source]
    x.ram.update({16:offset&255,17:offset>>8})
    for i,v in enumerate(data):
        if source=='flash':x.flash[offset+i]=v
        elif source=='eeprom':x.eeprom[offset+i]=v
        else:x.data_memory[offset+i]=v
    result=x.run('usb_tx_initialize_payload_crc',stop=('usb_tx_publish_packet_length',),limit=1200)
    assert result=='stop'
    payload=bytes(x.data_memory[0x102+i] for i in range(len(data)+2))
    assert payload[:len(data)]==bytes(data),(source,offset,data,payload)
    assert x.ram[16]==(offset+len(data))&255
    assert x.ram[17]==((offset+len(data))>>8)&255
    return payload


def test():
    rng=random.Random(0x2357)
    total=0
    for led in ('NONE','ACTIVE_HIGH','ACTIVE_LOW'):
        old=build(OLD,led,0x1b00)
        new=build(SRC,led,0x1b40 if led=='NONE' else 0x1b00)
        for source,offset in [('flash',0x142),('flash',0x1afe),('eeprom',16),('eeprom',56),('sram',0x010a)]:
            for k in range(0,9):
                if source=='eeprom' and offset+k>64:continue
                for v in (0,0xff,0x55,0xaa,None):
                    seq=[(v if v is not None else rng.randrange(256)) for i in range(k)]
                    a=execute_tx(old,source,offset,seq)
                    b=execute_tx(new,source,offset,seq)
                    assert a==b,(led,source,offset,seq,a,b)
                    total+=1
        print('PASS',led,'USB reply-copy/CRC equivalence')
    print('PASS',total,'actual-opcode TX byte + CRC comparisons')

if __name__=='__main__':test()
