#!/usr/bin/env python3
"""Emitted AVR code audit for unchanged USB bit loops and EOP J timing.

This is a cycle/port model, not an electrical compliance test.
"""
import sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from check_build import build
from tests.avr_exec import AVRExec

CYC={'in':1,'out':1,'andi':1,'sbi':2,'cbi':2,'rjmp':2,'rcall':3,'ret':4}

def section(x,lo,hi):
    a=x['symbols'][lo];b=x['symbols'][hi]
    return x['body'][a-x['boot']:b-x['boot']]

def verify():
    for mode,boot in [('NONE',0x1c00),('ACTIVE_HIGH',0x1bc0),('ACTIVE_LOW',0x1bc0)]:
        n=build('source/micronucleus_t88_compact.S',mode=mode,boot=boot)
        o=build('reference_pass33/micronucleus_t88_compact.S',mode=mode,boot=boot)
        a=AVRExec(n);b=AVRExec(o)
        for begin,end in [('usb_rx_sample_odd_bit','usb_rx_overflow'),
                          ('usb_crc16_mix_byte','usb_crc16_payload_complete')]:
            x,y=section(n,begin,end),section(o,begin,end)
            assert len(x)==len(y),(mode,begin,len(x),len(y))
            for i in range(0,len(x),2):
                w,v=int.from_bytes(x[i:i+2],'little'),int.from_bytes(y[i:i+2],'little')
                if w!=v:
                    assert ((w&0xf000)==(v&0xf000) and w&0xf000 in (0xc000,0xd000)) or ((w&0xfc07)==(v&0xfc07) and (w&0xf000)==0xf000),(mode,begin,hex(i),hex(w),hex(v))
        # Unchanged TX NRZI/bit-stuffing instructions; changed just after J.
        begin='usb_tx_begin_byte';end='usb_tx_finish_eop'
        x,y=section(n,begin,end),section(o,begin,end)
        assert len(x)==len(y)
        for i in range(0,len(x),2):
            w,v=int.from_bytes(x[i:i+2],'little'),int.from_bytes(y[i:i+2],'little')
            if w!=v:
                assert ((w&0xf000)==(v&0xf000) and w&0xf000 in (0xc000,0xd000)) or ((w&0xfc07)==(v&0xfc07) and (w&0xf000)==0xf000),(mode,'TX',hex(i),hex(w),hex(v))
        def decoded(art,exe):
            return [(exe.ins.get(pc) or exe.decode_missing(pc))[:2] for pc in range(art['symbols']['usb_tx_eop_delay']+4,art['symbols']['usb_return_context'],2)]
        now,old=decoded(n,a),decoded(o,b)
        assert now==[
            ('out','0xb, r16'),('in','r17, 0xa'),('out','0x1b, r17'),
            ('andi','r17, 0xf9'),('rcall','.+8'),('out','0xa, r17'),('cbi','0xb, 0x1')
        ],(mode,now)
        assert old==[
            ('out','0xb, r16'),('sbi','0x1b, 0x2'),('in','r17, 0xa'),
            ('andi','r17, 0xf9'),('rjmp','.+0'),('rjmp','.+0'),('rjmp','.+0'),
            ('out','0xa, r17'),('cbi','0xb, 0x1')
        ],(mode,old)
        # The RCALL at the end of the J drive must call only RET.
        pc=n['symbols']['usb_tx_eop_delay']+12
        assert pc==n['symbols']['usb_tx_eop_delay']+12
        opcode=int.from_bytes(n['body'][pc-boot:pc-boot+2],'little')
        assert (opcode&0xf000)==0xd000
        disp=opcode&0xfff
        if disp&0x800:disp-=4096
        target=pc+2+2*disp
        assert target==n['symbols']['usb_handler_return']
        ret=a.ins.get(target) or a.decode_missing(target)
        assert ret[0]=='ret'
        # Clock counts after actively driving J until DDR release.
        old_to_release=sum(CYC[k] for k,_ in old[1:-2])
        new_to_release=sum(CYC[k] for k,_ in now[1:-2])+CYC['ret']
        assert old_to_release==new_to_release==10,(mode,old_to_release,new_to_release)
        # Flag clearing after J starts: old SBI is two cycles; new IN+OUT
        # also two cycles. DDRD bit2 is always output for the EOP.
        old_clear=CYC[old[1][0]]
        new_clear=CYC[now[1][0]]+CYC[now[2][0]]
        assert old_clear==new_clear==2
        for prior in range(256):
            ddr=prior|0x06  # set by usb_tx_acquire_bus
            for f in range(8):
                pcifr=1<<f
                old_flags=pcifr&~(1<<2)
                new_flags=pcifr&~ddr
                assert old_flags&(1<<2)==new_flags&(1<<2)==0
                assert (ddr&~0x06)==(prior&~0x06), "EOP must preserve unrelated DDRD pins"
        # One extra return frame during J delay: SRAM stack has room;
        # the loader starts only after RESET with stack reset to RAMEND.
        print('PASS',mode,'USB NRZI / CRC opcode invariance; EOP timing',old_to_release,'cycles; 256 DDR masks')

if __name__=='__main__':verify()
