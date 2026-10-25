#!/usr/bin/env python3
"""Machine-code audit of the four intentional size reductions inside V-USB.

Confirms that the changed V-USB machine instruction sequence consists of
exactly three cycle-neutral PCIFR flag clear rewrites and one cycle-neutral
SRAM store rewrite. It also checks that no skipped instruction or branch
entered the middle of a removed two-instruction sequence, that the pointer Z
is valid at the STD, and that R17 is dead after the three LDI removals.

This is NOT a substitute for physical USB electrical testing.
"""
from __future__ import annotations
import re
import subprocess
import sys
import unittest
from pathlib import Path
from collections import deque
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
import avr_decoder as dec
BASE=0x1B40
NEW=0x1AC0


def symtab(p):
    res={}
    for line in subprocess.check_output(['llvm-objdump','-t',str(p)],text=True).splitlines():
        m=re.match(r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+(.+)$',line)
        if m:res[m[2]]=int(m[1],16)
    return res


def segment(binfile,obj,offset):
    sy=symtab(obj)
    dec.START=offset
    dec.raw=binfile.read_bytes()
    start,end=sy['USB_handler'],sy['usb_program_page']
    items=[];p=start
    while p<end:
        ins=dec.decode(p)
        if ins.unknown:raise AssertionError(('unknown AVR instruction',hex(p)))
        items.append(ins);p+=ins.size
    assert p==end
    return items,sy


def operand(ins):
    return re.sub(r'\s+','',ins.operands).lower()


class UsbPatchAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original,cls.os=segment(ROOT/'reference/Pass3_1216.bin',ROOT/'build/reference_pass3.o',BASE)
        cls.optimized,cls.ns=segment(ROOT/'firmware/BOOTLOADER_BODY_1AC0_PLUS.bin',ROOT/'build/plus_1ac0.o',NEW)

    def test_exactly_four_substitutions(self):
        expected=[]; refaddr_to_expected_index={}; removed=set(); changes=[]
        i=0
        while i<len(self.original):
            a=self.original[i]
            refaddr_to_expected_index[a.address]=len(expected)
            if (i+1<len(self.original) and a.op=='ldi' and operand(a)=='r17,0x04'
                    and self.original[i+1].op=='out' and operand(self.original[i+1])=='0x1b,r17'):
                b=self.original[i+1]
                removed.add(b.address)
                changes.append(('PCIFR',a.address,b.address))
                expected.append(('sbi','0x1b,2',a.target))
                i+=2
                continue
            if a.op=='sts' and operand(a)=='0x0114,r16':
                changes.append(('SRAM',a.address))
                expected.append(('std','z+20,r16',a.target))
            else:
                expected.append((a.op,operand(a),a.target))
            i+=1
        self.assertEqual([v[0] for v in changes],['PCIFR','PCIFR','SRAM','PCIFR'])
        self.assertEqual(sum(x.size for x in self.original)-sum(x.size for x in self.optimized),8)
        self.assertEqual(len(expected),len(self.optimized))
        # Branching into a removed OUT would make our substitution unsafe.
        for o in self.original:
            self.assertNotIn(o.target,removed)
        # Skip semantics are preserved: no skip opcode before a removed LDI.
        skip_ops={'sbic','sbis','sbrc','sbrs','cpse'}
        for kind,*a in changes:
            oldpos=a[0]
            pos=next(j for j,x in enumerate(self.original) if x.address==oldpos)
            self.assertNotIn(self.original[pos-1].op,skip_ops)
        # Each remaining instruction matches; relative branch targets point to
        # the exact same logical instruction after relayout, not just a similar opcode.
        opt_index={x.address:i for i,x in enumerate(self.optimized)}
        for index,((expop,exparg,exptgt),actual) in enumerate(zip(expected,self.optimized)):
            self.assertEqual(actual.op,expop,(index,hex(actual.address)))
            if exptgt is None:
                self.assertEqual(operand(actual),exparg,(index,hex(actual.address)))
            else:
                self.assertIn(exptgt,refaddr_to_expected_index,(index,hex(exptgt)))
                self.assertEqual(opt_index[actual.target],refaddr_to_expected_index[exptgt],
                                 (index,hex(actual.address),'branch changed target'))
        # LDI+OUT and SBI each consume exactly 2 cycles on classical AVR;
        # both STS (16-bit direct address) and STD (displacement) consume 2 cycles.
        self.assertEqual(len(changes),4)

    def test_z_initialized_on_every_path_to_new_std(self):
        dec.START=NEW
        dec.raw=(ROOT/'firmware/BOOTLOADER_BODY_1AC0_PLUS.bin').read_bytes()
        sy=self.ns
        q=deque([(sy['USB_handler'],None,None)])
        seen=set();seen_target=set()
        while q:
            pc,zlo,zhi=q.popleft()
            if (pc,zlo,zhi) in seen:continue
            seen.add((pc,zlo,zhi))
            if pc==sy['L1be4']:
                seen_target.add((zlo,zhi))
                continue
            if pc<sy['USB_handler'] or pc>=sy['usb_program_page']:
                continue
            ins=dec.decode(pc);arg=operand(ins)
            ops=arg.split(',') if arg else []
            if ins.op=='ldi':
                if ops[0]=='r30':zlo=int(ops[1],0)
                if ops[0]=='r31':zhi=int(ops[1],0)
            elif ins.op in ('mov','movw','ldd','lds','in','pop','eor','add','adc',
                             'sub','subi','sbci','ori','andi','sbiw','adiw','com','inc',
                             'dec','ld','lpm','ror','lsr') and ops:
                if ops[0]=='r30':zlo=None
                if ops[0]=='r31':zhi=None
                if ins.op in ('sbiw','adiw') and ops[0]=='r30':zhi=None
            if ins.op in ('ret','reti'):continue
            successors=[pc+ins.size]
            if ins.op=='rjmp':successors=[ins.target]
            elif ins.op in ('brbc','brbs'):successors.append(ins.target)
            elif ins.op in ('cpse','sbrc','sbrs','sbis','sbic'):
                following=pc+ins.size
                successors.append(following+dec.decode(following).size)
            for nxt in successors:q.append((nxt,zlo,zhi))
        self.assertEqual(seen_target,{(0,1)})

    def test_removed_r17_initializations_are_dead(self):
        dec.START=NEW
        dec.raw=(ROOT/'firmware/BOOTLOADER_BODY_1AC0_PLUS.bin').read_bytes()
        for name in ('L1ba2','L1baa','L1cb2'):
            q=deque([self.ns[name]+2]);seen=set();reached_writes=[]
            while q:
                pc=q.popleft()
                if pc in seen:continue
                seen.add(pc)
                if pc<self.ns['USB_handler'] or pc>=self.ns['usb_program_page']:
                    continue
                ins=dec.decode(pc);args=operand(ins).split(',')
                regs=re.findall(r'r\d+',operand(ins))
                # load destination writes the whole register without reading it
                writeonly=bool(args and args[0]=='r17' and ins.op in
                               ('ldi','ldd','lds','in','pop','mov'))
                if 'r17' in regs and not writeonly:
                    self.fail(f'R17 read after removed LDI at {name}: {hex(pc)} {ins.op} {ins.operands}')
                if writeonly:
                    reached_writes.append(pc)
                    continue
                if ins.op in ('ret','reti'):continue
                successors=[pc+ins.size]
                if ins.op=='rjmp':successors=[ins.target]
                elif ins.op in ('brbc','brbs'):successors.append(ins.target)
                elif ins.op in ('cpse','sbrc','sbrs','sbis','sbic'):
                    following=pc+ins.size
                    successors.append(following+dec.decode(following).size)
                q.extend(successors)
            self.assertTrue(reached_writes,name)

if __name__=='__main__':unittest.main()
