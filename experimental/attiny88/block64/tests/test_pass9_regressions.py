"""Additional tests for size-optimized Pass9 behavior and formerly missed faults."""
from __future__ import annotations
from pathlib import Path
import random, subprocess, pytest
from avr_sim import *
ROOT=Path(__file__).resolve().parent.parent
FW=ROOT/'firmware/ISP_FULL_8192_1980_PASS11.bin'


def fresh():
    return CPU(image=FW.read_bytes())


def test_avr_cpc_9bit_borrow_from_0xff():
    cpu=fresh()
    cpu.flagset(0,True)
    result=cpu.subtract(0x19,0xff,1,True)
    assert result==0x19  # 0x19 - 0xFF - 1 modulo 256
    assert cpu.flag(0)  # Borrow must remain set, NOT wrap to zero
    cpu.flagset(0,False)
    result=cpu.subtract(0x20,0xff,0,True)
    assert result==0x21 and cpu.flag(0)


def test_range_validation_with_high_address_random():
    cpu=fresh()
    rng=random.Random(828133)
    for memtype,end in [(0,BOOT),(1,64)]:
        cases=[]
        for n in (1,2,7,8,31,32,63,64):
            cases.extend((addr,n) for addr in (0,1,end-n,end-n+1,end-1,end,0xff00,0xfffe,0xffff))
        cases += [(rng.randrange(65536),rng.randint(1,64)) for _ in range(180)]
        for addr,length in cases:
            cpu.set_setup(0x10,addr,length,memtype)
            cpu.run_from('block_validate_range',count=150)
            assert cpu.flag(0)==(addr+length<=end),(memtype,hex(addr),length,cpu.flag(0))


def test_flash_and_eeprom_zero_size_or_big_length_rejected():
    cpu=fresh()
    for memtype in (0,1):
        for length in (0,65,255,256,65535):
            cpu.set_setup(0x10,0,length,memtype)
            cpu.run_from('block_validate_range',count=150)
            assert not cpu.flag(0),(memtype,length)


def test_eeprom_write_idle_gate_reuses_carry_safely():
    for state in range(8):
        for eepe in (0,1):
            cpu=fresh()
            cpu.r[28],cpu.r[29]=0,1
            cpu.mem[MEM_STATE]=state
            cpu.io[0x1f]=2 if eepe else 0
            cpu.run_from('block_check_idle_for_write',count=100)
            assert cpu.flag(0)==(state<3 and eepe==0),(state,eepe,cpu.flag(0))


def test_invalid_descriptor_type_has_resolved_fallback():
    cpu=fresh()
    cpu.set_setup(6,addr=0x0300,length=32,memtype=0,request_type=0x80)
    cpu.run_from('old_vendor_dispatch',stop_at=['L1de2'],count=150)
    assert cpu.r[24]==0  # unknown descriptor: zero-length response
    assert cpu.mem[0x0110]==0x0a and cpu.mem[0x0111]==0x81


def test_loader_code_has_no_unresolved_relocations():
    out=subprocess.check_output(['llvm-objdump','-r',str(ROOT/'build/block64.o')],text=True)
    assert 'R_AVR_' not in out
