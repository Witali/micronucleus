"""Actual assembled standard-request execution, with descriptor address relocation."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from check_build import build
from test_standard import disasm_q,execute
DIR=ROOT/'variants/strict_usb_optimized'


def test():
    n=0
    for mode in ('NONE','ACTIVE_HIGH','ACTIVE_LOW'):
        old=build(DIR/'micronucleus_t88_pass22.S',mode,boot=0x1ac0 if mode!='NONE' else 0x1b00)
        boot=0x1b40 if mode=='NONE' else 0x1b00
        new=build(DIR/'micronucleus_t88_pass26.S',mode,boot=boot)
        a=disasm_q(old['obj']); b=disasm_q(new['obj'])
        prior_offset=64 + (0 if boot==0x1ac0 else 0)  # address difference relative to old
        known_config=2
        known_device=known_config+18
        dev_off_new=(new['symbols']['USB_handler']-boot)-18
        assert dev_off_new==known_device,(boot,dev_off_new)
        body=new['body']
        assert body[known_device+12:known_device+14]=={'NONE':bytes((0x50,5)),'ACTIVE_HIGH':bytes((0x51,5)),'ACTIVE_LOW':bytes((0x52,5))}[mode]
        for req in range(256):
            for descriptor in (0,1,2,3,7,255):
                for config,value in ((0,0),(1,19),(255,100)):
                    l=execute(old,a,req,descriptor,config,value)
                    r=execute(new,b,req,descriptor,config,value)
                    if req==6 and descriptor in (1,2):
                        assert l[0]==r[0]=='usb_reply_set_pointer',(req,descriptor,l,r)
                        target=new['boot'] + (known_device if descriptor==1 else known_config)
                        assert r[1][0:2]==(target&255,(target>>8)&255),(req,descriptor,r,hex(target))
                        assert r[1][2]==18
                    elif req==6:
                        assert (l[0],l[1][2:],l[2])==(r[0],r[1][2:],r[2]),(mode,req,descriptor,config,value,l,r)
                    else:assert l==r,(mode,req,descriptor,config,value,l,r)
                    n+=1
        print('PASS',mode,'4608 standard request opcode cases')
    print('PASS',n,'standard request opcode cases')

if __name__=='__main__':test()
