#!/usr/bin/env python3
"""EP0 standard control request emitted-opcode identity against Pass33."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from check_build import build
from tests.avr_exec import AVRExec

def test_standard():
    count=0
    for mode,boot in [('NONE',0x1c00),('ACTIVE_HIGH',0x1bc0),('ACTIVE_LOW',0x1bc0)]:
        cur=build('source/micronucleus_t88_compact.S',mode=mode,boot=boot)
        ref=build('reference_pass33/micronucleus_t88_compact.S',mode=mode,boot=boot)
        x,y=AVRExec(cur),AVRExec(ref)
        sc=cur['symbols'];sr=ref['symbols']
        assert len(range(sc['usb_standard_dispatch'],sc['ee_empty']+2,2))==len(range(sr['usb_standard_dispatch'],sr['ee_empty']+2,2))
        for i in range(0,sc['ee_empty']+2-sc['usb_standard_dispatch'],2):
            cpc=sc['usb_standard_dispatch']+i;rpc=sr['usb_standard_dispatch']+i
            op,sub,n=x.ins.get(cpc) or x.decode_missing(cpc)
            op2,sub2,n2=y.ins.get(rpc) or y.decode_missing(rpc)
            assert op==op2 and n==n2,(mode,i,op,sub,op2,sub2)
            if op in ('rjmp','rcall','breq','brne','brbc','brbs','brsh','brlo'):
                if op in ('brbc','brbs'):
                    assert sub.split(',')[0]==sub2.split(',')[0]
            else:
                assert sub==sub2,(mode,i,op,sub,sub2)
            count+=1
        # The complete low-speed USB descriptors are identical except the
        # mandatory bcdDevice revision identifying the different wire format.
        assert cur['body'][2:32]==ref['body'][2:32]  # reset RJMP changes when code size changes
        assert cur['body'][34:38]==ref['body'][34:38]
    print('PASS standard EP0 emitted instruction/control descriptors:',count,'AVR words')
if __name__=='__main__':test_standard()
