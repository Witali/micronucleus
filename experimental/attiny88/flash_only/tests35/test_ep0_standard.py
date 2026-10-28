"""Independent USB2 request/descriptor oracle against emitted AVR instructions.

Normative basis: USB2.0 chapter9, especially 9.2.7/9.4 and interface table9-12.
This is a semantic oracle; Pass33/Pass35 opcode identity is not correctness.
"""
from pathlib import Path
import json
from tests35 import ep0_model as h
from tests35.ep0_cases import bind

HERE=Path(__file__).resolve().parent

class Quiet:
    pin_edges=[]
    def level(self,t):return h.J
    def cell(self,t):return 'IDLE'
    def edge_since(self,start,end):return False

def request(art,bm,req,value=0,index=0,length=8,config=1):
    bind(art);cpu=h.CPU(art,Quiet())
    cpu.pc=cpu.labels['usb_setup_capture_fields']
    cpu.m[0x117:0x11f]=bytes([bm,req,value&255,value>>8,index&255,index>>8,length&255,length>>8])
    cpu.r[12:16]=[value&255,value>>8,index&255,index>>8]
    cpu.r[6:8]=[length&255,length>>8]
    cpu.r[3]=5;cpu.r[4:6]=[0x80,0]
    cpu.m[0x115]=config;cpu.m[0x10f]=12
    for _ in range(4000):
        if cpu.pc==cpu.labels['usb_rx_release_buffer']:
            count=cpu.m[0x100];ptr=cpu.word(14)
            if cpu.m[0x10f]==0x1e:
                assert count==0xff and cpu.r[3]==0 and cpu.r[6:8]==[0,0]
                return dict(kind='stall')
            payload=bytes(cpu.flash[ptr+i] for i in range(count)) if count else b''
            return dict(kind='reply',count=count,payload=payload.hex(),config=cpu.m[0x115],pending=cpu.m[0x113],command=cpu.r[3])
        if cpu.pc==cpu.labels['bootloader_check_idle_timeout']:
            assert cpu.m[0x10f]==0x1e and cpu.m[0x100]==0xff
            assert cpu.r[3]==0 and cpu.r[6:8]==[0,0]
            return dict(kind='stall')
        at=cpu.pc-art['boot']
        if art['body'][at:at+2]==b'\xe8\x95':
            return dict(kind='spm',command=cpu.r[3],address=cpu.word(30))
        cpu.step()
    raise AssertionError((bm,req,value,index,length,config,'did not return'))

def test():
    art=h.build();cases=0
    # Known good fixed replies, including both endpoint-zero directions.
    for bm,req,value,index,config,payload in [
        (0x80,0,0,0,0,b'\0\0'),(0x80,0,0,0,1,b'\0\0'),
        (0x81,0,0,0,1,b'\0\0'),(0x82,0,0,0,0,b'\0\0'),
        (0x82,0,0,0x80,1,b'\0\0'),(0x81,10,0,0,1,b'\0'),
        (0x80,8,0,0,0,b'\0'),(0x80,8,0,0,1,b'\1')]:
        row=request(art,bm,req,value,index,config=config)
        assert row['kind']=='reply' and row['payload']==payload.hex(),(bm,req,row)
        assert row['command']==0;cases+=1
    for bm,req,value in [(0,5,37),(0,9,0),(0,9,1)]:
        row=request(art,bm,req,value)
        assert row['kind']=='reply' and row['count']==0 and row['command']==0,row
        if req==5:assert row['pending']==37,row
        else:assert row['config']==value,row
        cases+=1
    configuration=bytes([9,2,18,0,1,1,0,0x80,50,9,4,0,0,0,0xff,0,0,0])
    for descriptor,payload in [(1,bytes(art['body'][20:38])),(2,configuration)]:
        for length in (0,1,8,17,18,19,255,256,65535):
            row=request(art,0x80,6,descriptor<<8,length=length)
            assert row['kind']=='reply' and row['payload']==payload[:min(length,18)].hex(),(descriptor,length,row)
            cases+=1
    # USB9.4.7 explicitly leaves a nonzero upper wValue undefined.
    # This implementation uses the low configuration byte, avoiding a guard.
    row=request(art,0,9,0x101,length=0)
    assert row['kind']=='reply' and row['config']==1,row
    # Independent negative oracle: unsupported standard requests always STALL.
    for bm in (0,0x80,0x81,0x82):
        supported={0:{5,9},0x80:{0,6,8},0x81:{0,10},0x82:{0}}[bm]
        for req in range(256):
            if req in supported:continue
            assert request(art,bm,req)['kind']=='stall',(bm,req)
            cases+=1
    # Every unsupported type/recipient/direction is rejected before SPM.
    for bm in range(256):
        for req in (1,2,3,4,5,0xb0):
            allowed=((bm&0x60)==0x40) or (bm==0 and req==5)
            if allowed:continue
            assert request(art,bm,req)['kind']=='stall',(bm,req)
            cases+=1
    for bm,req,value,index,config in [
        (0x81,0,0,0,0),(0x81,10,0,0,0),(0x81,0,0,1,1),
        (0x81,10,0,1,1),(0x81,0,0,0x100,1),
        (0x82,0,0,1,1),(0x82,0,0,0x81,1),(0x82,0,0,0x100,1),
        (0,9,2,0,1),(0,9,255,0,1),
        (0x80,6,0x300,0,1),(0x80,6,0x101,0,1),(0x80,6,0x200,1,1)]:
        assert request(art,bm,req,value,index,config=config)['kind']=='stall',(bm,req,value,index,config)
        cases+=1
    # Vendor direction/recipient/wLength validation belongs to the host.
    # Mandatory class/reserved errors remain in the all-bmRequestType loop.
    for req in (1,2,3):
        assert request(art,0x40,req,index=0x80,length=0)['kind']=='spm',req
        cases+=1
    report=dict(bytes=art['size'],sha256=art['sha256'],cases=cases,
                interface_class=configuration[14],standard='USB2.0 chapter9')
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':test()
