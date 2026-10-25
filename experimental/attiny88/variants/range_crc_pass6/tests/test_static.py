#!/usr/bin/env python3
"""Static checks: Intel HEX, page alignment, compatible V-USB, SRAM and EEPROM."""
import unittest, pathlib, re, subprocess
ROOT=pathlib.Path(__file__).resolve().parent.parent
FLASH=8192
BOOT=0x19c0
BODY=ROOT/'firmware/BOOTLOADER_BODY_CRC_PLUS.bin'
IMAGE=ROOT/'firmware/ISP_FULL_8192_CRC_FRESH_ONLY.bin'
HEX=ROOT/'firmware/ISP_FULL_CRC_FRESH_ONLY.hex'

class StaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image=IMAGE.read_bytes();cls.body=BODY.read_bytes()
        cls.dump=subprocess.check_output(['llvm-objdump','-d',str(ROOT/'build/plus_crc.o')],text=True)
    def test_flash_layout(self):
        self.assertEqual(len(self.image),8192)
        self.assertEqual(len(self.body),1554)
        self.assertEqual(self.image[BOOT:BOOT+len(self.body)],self.body)
        self.assertEqual(self.image[BOOT+len(self.body):],b'\xff'*(8192-BOOT-len(self.body)))
        self.assertEqual(self.image[BOOT-4:BOOT],b'\xff'*4)
        op=int.from_bytes(self.image[:2],'little')
        k=op&0xfff;k=k-4096 if k&2048 else k
        self.assertEqual(((1+k)&4095)*2,BOOT)
    def test_capabilities_and_version(self):
        b=self.body
        self.assertEqual(b[2:4],(BOOT-4).to_bytes(2,'big'))
        self.assertEqual(b[4],64)
        self.assertEqual(b[8],0xe0)
        self.assertEqual(b[0x28:0x2a],b'\x10\x02')
        self.assertEqual(b[6:8],b'\x93\x11')
    def test_intel_hex(self):
        lines=HEX.read_text().splitlines();self.assertEqual(lines[-1],':00000001FF')
        self.assertGreater(len(lines),70)
        memory={}
        for line in lines:
            data=bytes.fromhex(line[1:]);n,hi,lo,kind=data[:4]
            self.assertEqual(len(data),n+5);self.assertEqual(sum(data)&255,0)
            addr=(hi<<8)|lo
            if kind==0:
                self.assertTrue((addr==0 and n==2) or BOOT<=addr<8192)
                for i,v in enumerate(data[4:-1]):memory[addr+i]=v
            elif kind in (1,3): pass
            else:self.fail(f'unexpected record {kind}')
        for address,b in memory.items():self.assertEqual(self.image[address],b)
    def test_eeprom_commands_and_clocking(self):
        t=self.dump
        self.assertIn('sbi\t0x1f, 0x2',t)
        self.assertIn('sbi\t0x1f, 0x1',t)
        self.assertRegex(t,r'sbi\s+0x1f, 0x2\s*\n\s*[0-9a-f]+:\s+[0-9a-f ]+\s+sbi\s+0x1f, 0x1')
    def test_bounded_flash_read(self):
        s=(ROOT/'source/micronucleus_t88_plus.S').read_text()
        self.assertIn('flash_read:',s)
        self.assertIn('((BOOT_AT - 4) & 0xff)',s)
        self.assertIn('    sub     r30, r24',s)
        self.assertIn('    cp      r30, r18',s)
        self.assertIn('    brlo    ee_empty',s)
        self.assertIn('    std     Y+16, r18',s)
        self.assertIn('    std     Y+17, r19',s)
    def test_disassembled_relative_branch_targets(self):
        import importlib.util, sys
        local=str(ROOT/'tests')
        if local not in sys.path: sys.path.insert(0,local)
        import avr_decoder as decoder
        decoder.START=BOOT;decoder.raw=self.body
        sym=subprocess.check_output(['llvm-objdump','-t',str(ROOT/'build/plus_crc.o')],text=True)
        m=re.search(r'^([0-9a-f]+)\s+\S+\s+\.text\s+[0-9a-f]+\s+startup$',sym,re.M)
        self.assertIsNotNone(m)
        pc=int(m.group(1),16);stop=BOOT+len(self.body);starts=set();branches=[];unknown=[]
        while pc<stop:
            ins=decoder.decode(pc)
            starts.add(pc)
            if ins.unknown: unknown.append(pc)
            if ins.target is not None: branches.append((pc,ins.target))
            pc+=ins.size
        self.assertEqual(pc,stop)
        self.assertFalse(unknown)
        self.assertGreaterEqual(len(starts),620)
        self.assertGreaterEqual(len(branches),145)
        for src,target in branches:
            self.assertTrue(target in starts or target==BOOT-4,(hex(src),hex(target)))

    def test_no_invalid_bit_io(self):
        for io in re.findall(r'\b(?:sbi|sbic|sbis|cbi)\s+0x([0-9a-f]+),',self.dump):
            self.assertLess(int(io,16),32)

if __name__=='__main__':unittest.main()
