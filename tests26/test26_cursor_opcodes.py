"""Real AVR opcode tests of new auto-increment READ8 cursor, independently
of USB byte sampling (hardware USB verification is not included)."""
import sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R))
from check_build import build
from tests.avr_exec import AVRExec
SRC=R/'variants/strict_usb_optimized/micronucleus_t88_pass26.S'

def test():
    count=0
    for mode in ('NONE','ACTIVE_HIGH','ACTIVE_LOW'):
        boot=0x1B40 if mode=='NONE' else 0x1B00
        art=build(SRC,mode,boot)
        for kind in ('flash','eeprom'):
            starts=list(range(0,64,4))
            if kind=='flash':
                starts+=[0xfc,0x100,0x1fc,0x200,0x6b00,0x1fe0]
            for start in starts:
                if kind=='eeprom' and start>56: continue
                if start + 8>8192:continue
                x=AVRExec(art)
                x.r[4]=start&255
                x.r[5]=(start>>8)|(0x80 if kind=='eeprom' else 0)
                x.r[29]=1
                # Host's READ8 wValue is ignored. Set deliberately wrong bytes.
                x.ram[25]=0x77;x.ram[26]=0x01
                x.r[8]=0
                for j in range(2 if (start+16<=64 or kind=='flash') else 1):
                    current=start+j*8
                    out=x.run('memory_read',stop=['usb_reply_set_pointer','ee_empty'])
                    assert out=='stop' and x.pc==art['symbols']['usb_reply_set_pointer'],(mode,kind,start,x.steps[-4:])
                    assert x.r[18]|(x.r[19]<<8)==current,(mode,kind,start,current,x.r[18],x.r[19])
                    assert x.r[24]==8
                    assert x.r[2]==(0x80 if kind=='eeprom' else 0)
                    assert (x.r[4]|(x.r[5]<<8))==((current+8)|(0x8000 if kind=='eeprom' else 0))
                    count+=1
        # Busy must preserve cursor, never return a nominal READ8 packet.
        for pending,eepe in ((1,False),(0,True),(3,True)):
            x=AVRExec(art)
            x.r[4]=0x18;x.r[5]=0x80
            x.r[8]=pending;x.io[0x1f]=2 if eepe else 0
            x.run('memory_read',stop=['usb_reply_set_pointer','ee_empty'])
            assert x.pc==art['symbols']['ee_empty']
            assert x.r[4:6]==[0x18,0x80]
            count+=1
        print('PASS',mode,'cursor opcode paths,',art['size'],'bytes')
    print('PASS',count,'sequential Flash/EEPROM READ8+busy opcode checks')

if __name__=='__main__':test()
