"""Pass14 consolidation checks (AVR instruction interpreter, no physical USB)."""
from pathlib import Path
import subprocess, re, hashlib
from avr_sim import CPU, BOOT, MEM_STATE, ST_FLASH_WAIT_PREP

ROOT=Path(__file__).resolve().parents[1]
BEFORE=ROOT/'reference/Pass13_baseline'

def read_symbols(obj):
    lines=subprocess.check_output(['llvm-objdump','-t',str(obj)],text=True).splitlines()
    out={}
    for l in lines:
        m=re.match(r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+(.+)$',l)
        if m:out[m.group(2)]=int(m.group(1),16)
    return out


def test_relief_and_usb_phy_identical():
    old=BEFORE/'block64.full.bin'
    new=ROOT/'build/block64.full.bin'
    a=read_symbols(BEFORE/'block64.o')
    b=read_symbols(ROOT/'build/block64.o')
    o=old.read_bytes();n=new.read_bytes()
    assert b['bootloader_start']==0x19C0
    assert len(n)-0x19c0==1578  # CRC pointer reuse after Pass15 (Pass14 was 1596).
    assert len(o)-0x1980==1610
    assert n[a['usb_crc16_append']-0x1980+0x19c0:b['USB_handler']] == o[a['usb_crc16_append']:a['USB_handler']]
    assert n[b['USB_handler']:b['main']]==o[a['USB_handler']:a['main']]
    assert 0x19c0-4-(0x1980-4)==64


def test_vendor_reject_in_real_setup_already_has_empty_response():
    raw=(ROOT/'firmware/ISP_FULL_8192_19C0_PASS15.bin').read_bytes()
    for initial_length in (0,1,8,64,255):
        c=CPU(image=raw)
        c.set_setup(0x20,addr=0,length=8,memtype=0,request_type=0xc0)
        c.mem[0x0100]=initial_length
        c.mem[0x0112]=11  # USB RX packet's 8 setup bytes + 3 low-level bytes
        c.mem[0x010d]=0x2d  # SETUP PID, not OUT
        c.run_from('L1d9c',stop_at=['L1df8'],count=3000,execute_ret=True)
        assert c.pc == c.labels['L1df8']
        assert c.mem[0x0100] == 0xff
        assert c.mem[MEM_STATE] == 2  # ST_ERROR


def test_shared_erase_and_write_spm_instruction_window():
    # Hardware rule: the SPM must be the immediate next opcode after OUT SPMCSR.
    raw=(ROOT/'firmware/ISP_FULL_8192_19C0_PASS15.bin').read_bytes()
    c=CPU(image=raw)
    start=c.labels['block_execute_spm']
    from avr_sim import D
    addr=start
    steps=[]
    for _ in range(5):
        inst=c.decode(addr)
        steps.append(inst.op)
        addr+=inst.size
    assert steps[:4]==['rcall','out','spm','std']


def test_no_legacy_vendor_commands_in_main_dispatch():
    text=(ROOT/'source/micronucleus_t88_block64.S').read_text()
    assert 'block_vendor_is_erase:' not in text
    assert text.count('block_execute_spm:')==1
    assert text.count('out     T88_IO_SPMCSR, r18')>=1
