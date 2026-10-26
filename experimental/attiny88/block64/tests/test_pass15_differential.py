"""Differential AVR interpreter checks against the immutable Pass14 build.

These validate command logic, not the USB electrical interface. Both images
remain in distinct CPU instances with the correct symbol maps.
"""
from pathlib import Path
import random
import re
import subprocess
from avr_sim import BOOT, CPU, MEM_BUFFER, MEM_STATE, MEM_REMAIN, MEM_INDEX

ROOT = Path(__file__).resolve().parents[1]


def syms(obj):
    out={}
    for line in subprocess.check_output(['llvm-objdump','-t',str(obj)],text=True).splitlines():
        match=re.match(r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+(.+)$',line)
        if match:out[match.group(2)]=int(match.group(1),16)
    return out


def pair(eeprom=None):
    old=CPU(image=(ROOT/'reference/Pass14_full.bin').read_bytes(),EEPROM=eeprom)
    old.labels=syms(ROOT/'reference/Pass14_block64.o')
    new=CPU(image=(ROOT/'firmware/isp-full.bin').read_bytes(),EEPROM=eeprom)
    return old,new


def crc16(buf):
    crc=0xffff
    for byte in buf:
        crc^=byte
        for _ in range(8):crc=((crc>>1)^0xa001) if crc&1 else crc>>1
    return ((~crc)&0xffff).to_bytes(2,'little')


def data_out(cpu,data,pid,corrupt=False):
    cpu.mem[0x0116]=pid
    cpu.mem[0x0117:0x0117+len(data)]=data
    crc=bytearray(crc16(data))
    if corrupt:crc[0]^=1
    cpu.mem[0x0117+len(data):0x0119+len(data)]=crc
    cpu.r[24]=len(data)
    cpu.run_from('block_out_packet',stop_at=['L1df8'],count=1500,execute_ret=True)
    assert cpu.pc==cpu.labels['L1df8']


def memory_signature(cpu):
    return bytes(cpu.mem[0x0100:0x0101])+bytes(cpu.mem[0x0130:0x0180])


def test_erase_and_write_command_setup_equivalence():
    randomizer=random.Random(5213)
    examples=[(0,64,0),(0x40,64,0),(0x1940,64,0),(0x19c0,64,0),
              (63,64,0),(0,63,0),(0,64,1),(0x123,64,0),(65535,64,0)]
    examples += [(randomizer.randrange(65536),randomizer.randrange(0,70),randomizer.randrange(0,4)) for _ in range(140)]
    for adr,n,kind in examples:
        if kind==0 and ((adr+64<=0x19c0)!=(adr+64<=BOOT)):continue
        for op, label in ((0x11,'block_write_setup'),(0x14,'block_erase_setup')):
            a,b=pair()
            for c in (a,b):
                c.set_setup(op,adr,0 if op==0x14 else n,kind,0x40)
                c.run_from(label,stop_at=['L1df8'],count=700,execute_ret=True)
            assert memory_signature(a)==memory_signature(b),(op,adr,n,kind)


def test_data_out_repeats_crc_and_progress_match_previous_implementation():
    rng=random.Random(584301)
    for _ in range(75):
        kind=rng.randrange(2)
        adr=(rng.randrange(0,100)*64 if kind==0 else rng.randrange(0,64))
        n=64 if kind==0 else rng.randrange(1,65-adr)
        if adr+n>BOOT:continue
        a,b=pair()
        for c in (a,b):
            c.set_setup(0x11,adr,n,kind,0x40)
            c.run_from('block_write_setup',stop_at=['L1df8'],count=700,execute_ret=True)
        assert memory_signature(a)==memory_signature(b)
        remaining=n
        pid=0x4b
        while remaining:
            k=min(8,remaining)
            payload=bytes(rng.randrange(256) for _ in range(k))
            for corrupt in (True,False):
                for c in (a,b): data_out(c,payload,pid,corrupt=corrupt)
                assert memory_signature(a)==memory_signature(b),(adr,kind,pid,corrupt,remaining)
            # Host retransmit of already-ACKed packet must be ignored.
            for c in (a,b): data_out(c,payload,pid)
            assert memory_signature(a)==memory_signature(b)
            pid^=0x88
            remaining-=k
        assert a.mem[MEM_INDEX]==b.mem[MEM_INDEX]==n

def test_eeprom_read_setup_equivalent_over_all_lengths_and_offsets():
    rng=random.Random(6007)
    contents=bytes(rng.randrange(256) for _ in range(64))
    for a0 in (0,1,23,31,63):
        for n in (1,2,8,9,32,64):
            if a0+n>64:continue
            a,b=pair(contents)
            for c in (a,b):
                c.set_setup(0x10,a0,n,1,0xc0)
                c.run_from('block_read_setup',stop_at=['L1f22'],count=700,execute_ret=True)
            assert bytes(a.mem[MEM_BUFFER:MEM_BUFFER+n])==bytes(b.mem[MEM_BUFFER:MEM_BUFFER+n])
            assert (a.r[18],a.r[19],a.r[24])==(b.r[18],b.r[19],b.r[24])
