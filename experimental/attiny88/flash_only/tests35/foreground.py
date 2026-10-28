from functools import lru_cache
#!/usr/bin/env python3
"""Trace elapsed cycles between TX EOP J and receiving legal host ACK.
Uses linked Pass34 binary and simple clocked PIN/PCIF simulation.
"""
from .wave import Sim,build,PERIOD

@lru_cache(maxsize=16)
def artifact(mode,boot,source):
 return build(f'{source}/micronucleus_t88_compact.S',mode=mode,boot=boot)

def one(mode,boot,caller,pending,ipd,phase=0,source="source",halt=False):
 a=artifact(mode,boot,source)
 s=Sim(a,sop=ipd,phase=phase)
 s.stop_on_context=False;s.simulate_spm_halt=halt
 sy=a['symbols'];s.pc=sy['usb_tx_eop_delay']+4;s.stack=[sy[caller]]
 s.r[1]=0;s.r[2]=12;s.r[3]=pending;s.r[4]=0x80;s.r[5]=0
 s.r[16]=2;s.r[17]=6;s.r[21]=0;s.r[23]=0xff
 s.r[26]=0x10;s.r[27]=1 # nonzero poll countdown
 s.io[0x0a]=6;s.io[0x0b]=2
 s.m[0x100+15]=12 # DATA already transmitted, awaiting ACK
 s.m[0x100+0]=0xff # no additional reply
 r=s.run(limit=1600)
 return s,r

if __name__=='__main__':
 for mode,boot in [('NONE',0x1c00),('ACTIVE_HIGH',0x1bc0),('ACTIVE_LOW',0x1bc0)]:
  for caller in ['bootloader_process_pending_command','usb_validate_setup']:
   for pending in (0,3,5):
    for ipd in (2*PERIOD,4*PERIOD,7*PERIOD):
     try:
      s,r=one(mode,boot,caller,pending,ipd)
      print(mode,caller,pending,round(ipd,1),r,'ack?',s.accepted,'SPM',s.spm_hit,'PHY entry', [round(x,1) for x in s.phy_entries[:3]],'after ACK SOP',[(x-ipd) for x in s.phy_entries[:3]],'time',round(s.t,1))
     except Exception as e:
      print('ERR',mode,caller,pending,ipd,type(e).__name__,str(e)[:170])
