"""OUT status, duplicate-toggle, STALL and queued-command lifetime regressions."""
from pathlib import Path
import json
from tests35 import ep0_model as h
from tests35.ep0_cases import bind,Bits,ack
from tests35.test_ep0_standard import Quiet

HERE=Path(__file__).resolve().parent

def out(art,payload=b'',pid=0x4b,direction=0x80,tx=12,command=0,packet=None):
    bind(art);wire=Bits(h.data_packet(payload,pid) if packet is None else packet)
    cpu=h.CPU(art,wire)
    cpu.r[11]=direction;cpu.r[3]=command
    cpu.m[0x10f]=tx;cpu.m[0x100]=7;cpu.m[0x114]=0xe1
    for _ in range(10000):
        if cpu.pc==0xfffe:break
        cpu.step()
    else:raise AssertionError('OUT did not return')
    return dict(tx=cpu.m[0x10f],remaining=cpu.m[0x100],command=cpu.r[3],rx_length=cpu.m[0x112],token=cpu.m[0x114])

def test():
    art=h.build();cases=0
    # Control-read OUT status verifies final DATA despite a lost IN ACK.
    for tx in (12,0x5a):
        row=out(art,tx=tx)
        assert row['remaining']&0x80 and row['tx']==0x5a,row
        assert row['command']==0 and row['rx_length']==0 and row['token']==0,row
        cases+=1
    # A repeated old toggle is ACKed/discarded and preserves pending data.
    row=out(art,pid=0xc3)
    assert row['tx']==12 and row['remaining']==7,row;cases+=1
    # A write has IN status: an unrelated OUT cannot stand in for its ACK.
    for command in (3,4,5,64):
        for pid in (0xc3,0x4b):
            row=out(art,direction=0,command=command,pid=pid)
            assert row['tx']==0x1e and row['remaining']&0x80 and row['command']==0,row
            cases+=1
    # USB8.5.3.1 permits a nonempty read status; missing CRC bytes remain ignored.
    for payload in (bytes(1),bytes(8)):
        row=out(art,payload=payload)
        assert row['tx']==0x5a and row['remaining']&0x80,row;cases+=1
    for packet in (b'\x4b',b'\x4b\x00'):
        row=out(art,packet=packet)
        assert row['tx']==12 and row['remaining']==7,row;cases+=1
    # Protocol STALL persists for both directions until a fresh SETUP.
    for direction in (0,0x80):
        row=out(art,tx=0x1e,direction=direction)
        assert row['tx']==0x1e and row['remaining']==7,row;cases+=1
    # ACK acceptance is independent of a persistent pending TX length.
    for marker,accepted in ((0,False),(12,True)):
        row=ack(art,marker=marker)
        assert row['accepted']==accepted,row;cases+=1
    report=dict(bytes=art['size'],sha256=art['sha256'],cases=cases)
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':test()
