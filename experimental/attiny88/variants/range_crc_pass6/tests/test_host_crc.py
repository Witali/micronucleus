#!/usr/bin/env python3
"""Host CRC extension tests using a deterministic in-memory fake USB endpoint."""
import sys, unittest, pathlib, random
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
import micronucleus_plus as host


def crc_usb(data):
    state=0xffff
    for b in data:
        state ^= b
        for i in range(8):
            state=(state>>1)^(0xa001 if (state&1) else 0)
    return state ^ 0xffff

class FakeDevice:
    bcdDevice = 0x0210
    def __init__(self):
        r=random.Random(98712)
        self.flash=bytes(r.randrange(256) for _ in range(6588))
        self.eeprom=bytes(r.randrange(256) for _ in range(64))
        self.requests=[]
        self.job=None
    def ctrl_transfer(self,typ,opcode,start,end,length,timeout):
        self.requests.append((typ,opcode,start,end,length))
        if opcode==0:
            return [0x19,0xbc,64,5,0x93,0x11,0xe0,0]
        if opcode==0xb0:
            return self.flash[start:start+length]
        if opcode==0xa0:
            return bytes([self.eeprom[start]])
        if opcode==0xf0:
            return b'\x00'
        if opcode in (0xd0,0xd1):
            src=self.flash if opcode==0xd0 else self.eeprom
            if not(0<=start<end<=len(src)):
                return b'\x02'
            self.job=(src,start,end)
            return b'\x00'
        if opcode==0xd2:
            if self.job is None:
                return b'\x02\x00\x00'
            src,pos,end=self.job
            n=min(start,end-pos)
            pos+=n
            self.job=(src,pos,end)
            # Keep initial start separate via bytes prefix property to mimic state.
            # The start for this fake is recovered from the first setup request.
            start_address=next(r[2] for r in reversed(self.requests) if r[1] in (0xd0,0xd1))
            c=crc_usb(src[start_address:pos])
            return bytes([1 if pos==end else 0,c&255,c>>8])
        raise AssertionError(hex(opcode))

class HostCRCTests(unittest.TestCase):
    def test_flash_crc_and_eeprom_crc(self):
        dev=FakeDevice();api=host.EEPROMTool(dev,sleep=lambda _:None)
        api.check_device()
        self.assertTrue(api.crc_supported)
        for region,src,start,end in (('flash',dev.flash,0,6588),('flash',dev.flash,33,1024),('eeprom',dev.eeprom,0,64),('eeprom',dev.eeprom,11,59)):
            for chunk in (1,3,8,16):
                got=api.crc_range(region,start,end,chunk=chunk)
                self.assertEqual(got,crc_usb(src[start:end]))
    def test_local_crc_fallback_uses_no_firmware_crc_commands(self):
        dev=FakeDevice();api=host.EEPROMTool(dev,sleep=lambda _:None)
        api.check_device()
        api.crc_supported=False
        for region,src,a,b in [('flash',dev.flash,128,200),('eeprom',dev.eeprom,4,22)]:
            self.assertEqual(api.crc_range_local(region,a,b),crc_usb(src[a:b]))
        self.assertFalse(any(req[1] in (0xd0,0xd1,0xd2) for req in dev.requests))

    def test_bad_range_and_unsupported_firmware(self):
        d=FakeDevice();t=host.EEPROMTool(d,sleep=lambda _:None);t.check_device()
        for area,lo,hi,c in (('flash',6587,6589,8),('eeprom',0,65,8),('flash',2,1,8),('flash',0,64,0),('flash',0,64,17)):
            with self.assertRaises(host.EEPROMError):t.crc_range(area,lo,hi,chunk=c)
        t.crc_supported=False
        with self.assertRaisesRegex(host.EEPROMError,'not supported'):
            t.crc_range('flash',0,16)

if __name__=='__main__':unittest.main()
