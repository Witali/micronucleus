"""Check complete legal IN exchanges through actual foreground paths.

Handler entry latency is measured, not treated as a USB packet requirement.
Every token must decode exactly and emit a correct response within the USB
turnaround bound, including when foreground SETUP publication delays entry.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind,Bits
from tests35.test_tx_digital import crc16,encoded
CPU=h.CPU

def incoming(art,setup,delay,rate=1_500_000,config=1,responses=None):
    bind(art);c=CPU(art,Bits(h.data_packet(setup),rate=rate))
    c.calls.pop();c.calls.append(c.labels['bootloader_process_pending_command'])
    c.m[0x114]=0x2d;c.m[0x10f]=0x5a;c.m[0x115]=config;c.r[4:6]=[0x80,0]
    j=None;entry=None;wire=None;decoded=False;packet=None;outputs=[]
    for _ in range(18000):
        if c.pc==c.labels['USB_handler'] and j is not None:entry=c.t-j-delay
        if c.pc==c.labels['usb_rx_handle_in'] and j is not None:
            assert c.r[23]==3 and bytes(c.m[0x116:0x119])==h.token(0x69),('corrupt accepted token',c.r[23],bytes(c.m[0x116:0x119]).hex())
            decoded=True
        if c.pc==c.labels['usb_tx_acquire_bus'] and decoded:
            if c.r[19]==2:
                assert c.r[20] in (0x5a,0x1e),('wrong IN handshake',c.r[20])
                packet=bytes([c.r[20]])
            else:
                assert 4<=c.r[19]<=12,('wrong IN DATA length',c.r[19])
                packet=bytes(c.m[0x101:0x100+c.r[19]])
                assert packet[0] in (0xc3,0x4b) and packet[-2:]==crc16(packet[1:-2]),('invalid cached DATA',packet.hex())
        pc=c.pc;ins=c.step()
        if packet is not None and ins.op=='out' and ins.operands.startswith('0xb,') and c.io.get(10,0)&6==6:
            outputs.append((c.t,c.io.get(11,0)&6))
        if j is None and ins.op=='out' and ins.operands.startswith('0xb,') and c.io.get(11,0)&6==h.J and pc==c.labels['usb_tx_eop_delay']+4:
            j=c.t
            wire=Bits(h.token(0x69),start=j+delay,rate=rate)
            old=dict(c.io);cleared=c.io.cleared_at
            c.io=h.SynchronizedPinIO(c,wire);c.io.update(old);c.io.cleared_at=cleared
        if packet is not None and c.pc==c.labels['usb_tx_bus_released']:
            # The independent encoder inserts every mandatory stuffed zero,
            # including a final one; compare the whole driven packet/EOP.
            levels,_=encoded(b'\x80'+packet)
            assert [line for _,line in outputs]==levels+[0,h.J],('wrong emitted response',packet.hex(),outputs)
            response=outputs[0][0]-wire.boundaries[-2]
            assert 2*(85/8)<=response<=6.5*min(85/8,wire.period),('IN response timing',response)
            if responses is not None:responses.append(response)
            return True,entry
        if packet is None and j is not None and c.t>j+delay+800:return False,entry
    raise AssertionError('foreground injection did not finish')

def test():
    art=h.build();entries=[];responses=[];cases=0
    requests=[(0x80,6,0x100,0,18,1),(0x80,6,0x200,0,18,1),
              (0x81,10,0,0,1,1),(0x81,10,0,0,1,0),
              (0x81,0,0,0,2,1),(0x81,0,0,0,2,0),(0x82,0,0,0x80,2,1),
              (0x82,12,0,0,2,1),  # Unsupported endpoint request takes STALL.
              (0,5,37,0,0,1),(0,9,1,0,0,1),(0,9,0,0,0,1),
              (0xc0,0xb0,0,0x80,8,1),(0x20,2,0,0x80,0,1)]
    for bm,req,value,index,length,config in requests:
        setup=bytes([bm,req,value&255,value>>8,index&255,index>>8,length&255,length>>8])
        for rate in (1_499_250,1_500_000,1_500_750):
            delays=[2*(16_000_000/rate)+offset for offset in range(81)]
            delays.extend(range(104,225,4))
            for delay in delays:
                ok,entry=incoming(art,setup,delay,rate,config,responses)
                assert ok and entry is not None,(setup.hex(),config,rate,delay,entry)
                entries.append(entry);cases+=1
    report=dict(cases=cases,entry_range=[min(entries),max(entries)],response_range=[min(responses),max(responses)])
    print('PASS foreground exact-IN/full-response:',report)
    return report

if __name__=='__main__':test()
