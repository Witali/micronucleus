"""Prove accepted SETUP fields survive ignored DATA and validate DATA stages."""
from pathlib import Path
import json
from tests35 import ep0_model as h
from tests35.ep0_cases import bind,Bits
from tests35.ep0_data import data_reply

HERE=Path(__file__).resolve().parent
SETUP=bytes([0x40,3,0x11,0x22,0x80,0,0,0])
INJECT=bytes([0x40,3,0xAA,0xBB,0x90,0,0,0])

def intercepted_write(art):
    bind(art);wave=Bits(h.data_packet(SETUP))
    cpu=h.CPU(art,wave);cpu.calls.pop();cpu.calls.append(cpu.labels['bootloader_process_pending_command'])
    cpu.m[0x114]=0x2D;cpu.m[0x10F]=0x5A;cpu.r[4:6]=[0x80,0]
    injected=False
    for _ in range(20000):
        if cpu.pc==cpu.labels['bootloader_check_write4'] and not injected:
            # An invalid address token during an earlier poll can already have
            # cleared CURRENT_TOKEN. An unpaired DATA still writes raw RX SRAM.
            cpu.m[0x114]=0
            attack=Bits(h.data_packet(INJECT),start=cpu.t)
            old=dict(cpu.io)
            cpu.io=h.SynchronizedPinIO(cpu,attack)
            cpu.io.update(old);cpu.io.cleared_at=cpu.t-1
            injected=True
        at=cpu.pc-art['boot']
        if art['body'][at:at+2]==b'\xe8\x95':
            assert injected
            return dict(address=cpu.word(30),word=cpu.word(0),
                        raw_value=bytes(cpu.m[0x119:0x11D]).hex(),peak=cpu.peak)
        cpu.step()
    raise AssertionError('WRITE2 was not reached')

def test():
    after=h.build()
    new=intercepted_write(after)
    assert (new['address'],new['word'])==(0x80,0x2211),new
    rows=[]
    for rate in (1499250,1500000,1500750):
        for entry in (5,8,16,24,32,38):
            row=data_reply(after,entry=entry,rate=rate)
            assert row['rx_length']==11 and row['current_token']==0,row
            assert row['response']<=6.5*(32/3),row
            rows.append(row)
    assert data_reply(after,pid=0x4B)['response'] is None
    for payload in (b'',bytes(1),bytes(7)):
        assert data_reply(after,payload=payload)['response'] is None
    # A fresh SETUP must be accepted even while a previous one was staged.
    assert data_reply(after,busy=11)['rx_length']==11
    assert data_reply(after,token=0)['response'] is None
    report=dict(bytes=after['size'],sha256=after['sha256'],
                shadowed=new,max_ack_response=max(row['response'] for row in rows),
                min_ack_response=min(row['response'] for row in rows),wave_cases=len(rows)+6)
    print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':test()
