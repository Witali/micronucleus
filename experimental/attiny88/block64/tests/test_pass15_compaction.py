"""Pass15-specific behavior and code-generation invariants; software-only."""
import json
from pathlib import Path
import re
import subprocess
from avr_sim import CPU, MEM_ADDR_LO, MEM_ADDR_HI, MEM_STATE, MEM_STATUS, MEM_REMAIN

ROOT=Path(__file__).resolve().parents[1]
FW=ROOT/'firmware/isp-full.bin'


def symbols():
    s=subprocess.check_output(['llvm-objdump','-t',str(ROOT/'build/block64.o')],text=True)
    return {m.group(2):int(m.group(1),16) for m in re.finditer(r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+(.+)$',s,re.M)}


def test_compact_code_and_usb_engine_identity():
    from hashlib import sha256
    body=(ROOT/'firmware/bootloader.bin').read_bytes()
    assert len(body)==1588
    import sys
    sys.path.insert(0,str(ROOT/'tests'))
    from avr_sim import BOOT
    assert BOOT==0x19c0
    a=symbols()
    b=(ROOT/'build/block64.full.bin').read_bytes()
    assert len(b)-BOOT==1588
    assert len(b[a['usb_crc16_append']:a['USB_handler']])==44
    assert len(b[a['USB_handler']:a['main']])==508
    assert sha256((ROOT/'source/vusb_phy.inc').read_bytes()).hexdigest() == sha256((ROOT/'reference/Pass14_vusb_phy.inc').read_bytes()).hexdigest()


def test_shared_initializer_flash_erase_and_eeprom_receive():
    fw=FW.read_bytes()
    c=CPU(image=fw)
    c.set_setup(0x14,0x80,0,0,0x40)
    c.run_from('block_erase_setup',stop_at=['L1df8'],count=500,execute_ret=True)
    assert c.mem[MEM_STATE]==6 and c.mem[MEM_STATUS]==1
    assert c.mem[MEM_ADDR_LO]==0x80 and c.mem[MEM_ADDR_HI]==0
    assert c.mem[0x0100]==0  # USB ZLP for the ERASE control status
    c=CPU(image=fw)
    c.set_setup(0x11,12,19,1,0x40)
    c.run_from('block_write_setup',stop_at=['L1df8'],count=500,execute_ret=True)
    assert c.mem[MEM_STATE]==4 and c.mem[MEM_STATUS]==1
    assert c.mem[MEM_ADDR_LO]==12 and c.mem[MEM_ADDR_HI]==0
    assert c.mem[MEM_REMAIN]==19 and c.mem[0x0100]==0xff


def test_data_out_tail_dispatch_no_extra_stack_level():
    c=CPU(image=FW.read_bytes())
    c.r[28],c.r[29]=0,1
    c.mem[MEM_STATE]=0 # unexpected DATA OUT is safely ignored
    c.r[24]=8
    c.run_from('block_out_packet',stop_at=['L1df8'],count=100,execute_ret=True)
    assert c.pc==c.labels['L1df8']
    assert c.stack==[] # no longer an extra RCALL/RET frame


def test_page_zero_protection_still_applied():
    c=CPU(image=FW.read_bytes())
    c.r[28],c.r[29]=0,1
    c.mem[MEM_ADDR_LO]=0
    c.mem[MEM_ADDR_HI]=0
    c.mem[0x0140:0x0180]=bytes([0x42]*64)
    c.run_from('block_commit_flash',execute_ret=True,count=1300)
    opcode=0xc000|(((0x19c0//2)-1)&0xfff)
    assert c.flash[:2]==opcode.to_bytes(2,'little')
    assert c.flash[2:64]==bytes([0x42]*62)
