#!/usr/bin/env python3
"""Run actual assembled AVR words through the test interpreter and record cycles.
Not a wall-clock USB/SPM benchmark. Reference timings from original Pass12,
measured using the same corrected AVR timing model (ADIW/SBIW = 2 cycles).
"""
from __future__ import annotations
from pathlib import Path
import hashlib, json, sys
from layout import BOOT
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from avr_sim import CPU, MEM_BUFFER, MEM_STATE, MEM_ADDR_LO, MEM_ADDR_HI, MEM_PROGRESS, MEM_INDEX
ROM=(ROOT/'firmware/isp-full.bin').read_bytes()


def new(eeprom=None):return CPU(image=ROM,EEPROM=eeprom)

# Memory-only 64-byte EEPROM snapshot.
c=new(bytes(range(64)))
c.set_setup(0x10,0,64,1,0xc0)
c.run_from('block_read_setup',stop_at=['L1f22','block_reject'],count=4000,execute_ret=True)
assert bytes(c.mem[MEM_BUFFER:MEM_BUFFER+64])==bytes(range(64))
ee_read=c.cycles

# 64 byte EEPROM writes, counting the byte worker (not its main-loop caller).
c=new();c.mem[MEM_ADDR_LO]=0;c.mem[MEM_PROGRESS]=0;c.mem[MEM_INDEX]=64;c.mem[MEM_STATE]=5
c.mem[MEM_BUFFER:MEM_BUFFER+64]=bytes(range(64))
for _ in range(64):c.run_from('block_step_eeprom',count=100)
assert c.eeprom==bytes(range(64))
ee_write=c.cycles

# Flash page at end of a 256-byte region: ZL wraps after the final load.
c=new();a=(BOOT&~0xff)-64;c.mem[MEM_ADDR_LO]=a&255;c.mem[MEM_ADDR_HI]=a>>8
c.mem[MEM_BUFFER:MEM_BUFFER+64]=bytes(range(64))
c.run_from('block_commit_flash',count=2000,execute_ret=True)
assert c.flash[a:a+64]==bytes(range(64))
flash_write=c.cycles

# Normal main-loop idle path, until control request EP0 dispatcher.
c=new();c.mem[MEM_STATE]=0
c.run_from('L1d5e',stop_at=['L1d9c'],count=150,execute_ret=True)
assert c.pc==c.labels['L1d9c']
idle=c.cycles
old={
 'eeprom_read64':700,
 'eeprom_write64_worker':1920,
 'flash_64_program_logic_excluding_hardware_wait':500,
 'main_loop_idle_to_ep0':17,
}
new={
 'eeprom_read64':ee_read,
 'eeprom_write64_worker':ee_write,
 'flash_64_program_logic_excluding_hardware_wait':flash_write,
 'main_loop_idle_to_ep0':idle,
}
assert new=={'eeprom_read64':628,'eeprom_write64_worker':1856,
            'flash_64_program_logic_excluding_hardware_wait':470,
            'main_loop_idle_to_ep0':8},new
report={
 'baseline':'Pass12, same corrected software AVR model',
 'measurement':'instruction execution cycles only',
 'hardware_memory_programming_delay_included':False,
 'physical_usb_timing_verified':False,
 'base_cycles':old,'new_cycles':new,
 'saved_cycles':{k:old[k]-new[k] for k in old},
 'firmware_sha256':hashlib.sha256(ROM).hexdigest(),
}
(ROOT/'CYCLE_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,indent=2,ensure_ascii=False))
