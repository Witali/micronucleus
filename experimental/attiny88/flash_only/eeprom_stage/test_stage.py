#!/usr/bin/env python3
"""Independent small AVR opcode model for the stand-alone EEPROM stage.

Tests emitted machine words, EEPROM handshakes, complete readback and WDT path;
not a full physical ATtiny88 simulator or USB electrical test.
"""
from pathlib import Path
import random,tempfile
from plan_two_stage import *

class StageCPU:
    def __init__(self,flash:bytes,initial:bytes,fault_at=None):
        assert len(initial)==64
        self.flash=flash
        self.eeprom=bytearray(initial)
        self.reg=[0]*32
        self.io={0x1f:0,0x20:0,0x21:0}
        self.pc=0;self.cycles=0;self.busy=0;self.EEMPE_until=-1
        self.zflag=False;self.writes=0;self.fault_at=fault_at;self.success=False;self.failed=False
        self.wdt_unlock=False
        self.steps=0

    def word(self,pc):
        return int.from_bytes(self.flash[pc:pc+2], 'little')

    def tick(self,cycs):
        self.cycles+=cycs
        if self.busy:
            self.busy=max(0,self.busy-cycs)
            if self.busy==0:self.io[0x1f]&=~2

    def rjmp(self,w):
        k=w&0xfff
        if k&0x800:k-=4096
        self.pc+=2+k*2

    def run(self,limit=40000):
        visited={}
        for step in range(limit):
            self.steps+=1
            w=self.word(self.pc)
            if self.pc==0x58:
                self.failed=True
                return False
            if self.pc==0x56:
                if self.success:return True
            if w&0xF000==0xC000:
                self.rjmp(w);self.tick(2);continue
            if w&0xF000==0xE000:
                d=16+((w>>4)&15)
                k=((w>>4)&0xf0)|(w&0x0f)
                self.reg[d]=k;self.pc+=2;self.tick(1);continue
            if w&0xFF00==0x9900: # SBIC
                addr=(w>>3)&31;bit=w&7
                skip=not bool((self.io.get(addr,0)&(1<<bit)))
                self.pc+=2+(2 if skip else 0)
                self.tick(1+int(skip));continue
            if w&0xFF00==0x9A00: # SBI
                addr=(w>>3)&31;bit=w&7
                if addr==0x1f and bit==0:  # EERE
                    if self.busy:raise AssertionError('EERE while EEPROM busy')
                    self.io[0x20]=self.eeprom[self.io[0x21]]
                if addr==0x1f and bit==2:self.EEMPE_until=self.cycles+4
                if addr==0x1f and bit==1:
                    if self.cycles>self.EEMPE_until:raise AssertionError('EEPROM EEPE after EEMPE window')
                    addr=self.io[0x21]
                    if not 0<=addr<64:raise AssertionError('Bad EEPROM address')
                    if addr!=self.fault_at:self.eeprom[addr]=self.io[0x20]
                    self.busy=8
                    self.writes+=1
                    self.io[addr if False else 0x1f]=self.io.get(0x1f,0)|2
                self.pc+=2;self.tick(2);continue
            if w&0xFE0F==0x9005: # LPM Rd, Z+
                d=(w>>4)&31;addr=self.reg[30]+256*self.reg[31]
                self.reg[d]=self.flash[addr]
                addr=(addr+1)&65535
                self.reg[30]=addr&255;self.reg[31]=addr>>8
                self.pc+=2;self.tick(3);continue
            if w&0xF800 in (0xB000,0xB800):
                addr=((w>>5)&0x30)|(w&0x0f);d=(w>>4)&31
                if w&0xF800==0xB000:
                    self.reg[d]=self.io.get(addr,0)
                else:
                    self.io[addr]=self.reg[d]
                self.pc+=2;self.tick(1);continue
            if w&0xFC00==0x1400:  # CP
                d=(w>>4)&31;r=(w&15)|((w>>5)&0x10)
                self.zflag=self.reg[d]==self.reg[r]
                self.pc+=2;self.tick(1);continue
            if w&0xFC07 in (0xF001,0xF401):
                is_breq=(w&0xFC07)==0xF001
                k=(w>>3)&0x7f
                if k&0x40:k-=128
                take=self.zflag if is_breq else not self.zflag
                self.pc+=2+(k*2 if take else 0)
                self.tick(2 if take else 1);continue
            if w&0xFE0F in (0x9403,0x940A):
                d=(w>>4)&31
                if w&0xFE0F==0x9403:self.reg[d]=(self.reg[d]+1)&255
                else:self.reg[d]=(self.reg[d]-1)&255
                self.zflag=self.reg[d]==0
                self.pc+=2;self.tick(1);continue
            if w&0xFC00==0x2400:  # EOR
                d=(w>>4)&31;r=(w&15)|((w>>5)&0x10)
                self.reg[d]^=self.reg[r];self.zflag=self.reg[d]==0
                self.pc+=2;self.tick(1);continue
            if w==0x95A8: # WDR
                self.pc+=2;self.tick(1);continue
            if w&0xFE0F==0x9200:  # STS16
                d=(w>>4)&31;addr=self.word(self.pc+2);value=self.reg[d]
                if addr!=0x60:raise AssertionError('Unexpected STS address')
                if value==0x18:self.wdt_unlock=True
                elif value==0x08:
                    if not self.wdt_unlock:raise AssertionError('No watchdog unlock')
                    self.success=True
                else:raise AssertionError('Unexpected watchdog control')
                self.pc+=4;self.tick(2);continue
            raise AssertionError(f'Unknown instruction at {self.pc:#04x}: {w:#06x}')
        raise TimeoutError(f'Helper did not exit within {limit} instructions')


def test():
    with tempfile.TemporaryDirectory() as temp:
        p=Path(temp)
        rng=random.Random(20261028)
        eeprom=bytes(rng.randrange(256) for _ in range(64))
        main=p/'app.bin'
        main.write_bytes(bytes([0x00,0xc0,0xff,0xff]))
        source=p/'stage.S'
        source.write_text(make_asm(eeprom))
        img=compile_stage(source)
        assert len(img)==160
        assert img[0:2]==b'\x00\xc0'
        assert img[0x60:0xA0]==eeprom
        tests=0; max_steps=0
        for i in range(256):
            previous=bytes(rng.randrange(256) for _ in range(64)) if i%7 else eeprom
            cpu=StageCPU(img,previous)
            assert cpu.run()
            assert bytes(cpu.eeprom)==eeprom
            assert cpu.writes==sum(a!=b for a,b in zip(eeprom,previous))
            max_steps=max(max_steps,cpu.steps);tests+=1
        for fault in (0,7,31,63):
            before=bytes((255 if idx==fault else x) for idx,x in enumerate(eeprom))
            if before[fault]==eeprom[fault]:before=before[:fault]+bytes([eeprom[fault]^255])+before[fault+1:]
            cpu=StageCPU(img,before,fault_at=fault)
            assert cpu.run() is False and cpu.failed and not cpu.success
            tests+=1
        for boot in (0x1B40,0x1B80,0x1C00):
            stage=patch_for_loader(dict(enumerate(img)),boot)
            assert stage.app_target_byte==2
            assert stage.image[boot-4:boot-2]==stage.app_postscript_word.to_bytes(2,'little')
            assert stage.image[0:2]==stage.boot_reset_word.to_bytes(2,'little')
            assert stage.image[0x60:0xA0]==eeprom
            assert len(stage.image)==boot
            tests+=1
        try:patch_for_loader({0:0,1:0xc0,0x1B7D:0},0x1B80)
        except ValueError:pass
        else:raise AssertionError('Protected application postscript accepted')
        tests+=1
        try:make_asm(b'X'*63)
        except ValueError:pass
        else:raise AssertionError('63-byte EEPROM input accepted')
        tests+=1
        print(f'PASS {tests} end-to-end opcode/mock EEPROM cases, helper {len(img)}B, worst {max_steps} instructions; all main app postscript layouts verified')

if __name__=='__main__':test()
