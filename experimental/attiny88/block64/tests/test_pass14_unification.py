"""Pass14 consolidation checks (AVR instruction interpreter, no physical USB)."""
from pathlib import Path
import subprocess, re, hashlib
from test_firmware import usb_crc
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
    assert b['bootloader_start']==BOOT
    assert len(n)-BOOT==1804  # Pointer reuse plus the shared SETUP/OUT CRC gate.
    assert len(o)-0x1980==1610
    assert n[b['usb_crc16_append']:b['USB_handler']] == o[a['usb_crc16_append']:a['USB_handler']]
    from usb_transaction_audit import audit_timed_instructions
    audit_timed_instructions(n, b)
    assert 8192-BOOT >= len(n)-BOOT


def test_vendor_reject_in_real_setup_already_has_empty_response():
    raw=(ROOT/'firmware/isp-full.bin').read_bytes()
    for initial_length in (0,1,8,64,255):
        c=CPU(image=raw)
        c.set_setup(0x20,addr=0,length=8,memtype=0,request_type=0xc0)
        c.mem[0x011f:0x0121]=usb_crc(c.mem[0x0117:0x011f])
        c.mem[0x0100]=initial_length
        c.mem[0x0112]=11  # USB RX packet's 8 setup bytes + 3 low-level bytes
        c.mem[0x010d]=0x2d  # SETUP PID, not OUT
        c.run_from('L1d9c',stop_at=['L1df8'],count=3000,execute_ret=True)
        assert c.pc == c.labels['L1df8']
        assert c.mem[0x0100] == 0xff
        assert c.mem[MEM_STATE] == 2  # ST_ERROR


def test_shared_erase_and_write_spm_instruction_window():
    # Hardware rule: the SPM must be the immediate next opcode after OUT SPMCSR.
    raw=(ROOT/'firmware/isp-full.bin').read_bytes()
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
