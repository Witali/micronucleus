#!/usr/bin/env python3
"""Host-side tests: no USB hardware needed."""
from pathlib import Path
import importlib.util, random, tempfile, unittest
ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('mn_eeprom',ROOT/'host/micronucleus_plus.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class FakeDevice:
    def __init__(self,ext=True):
        self.e=bytearray(range(64)); self.ext=ext; self.cycles=0; self.calls=[];self.busy_ticks=0;self.writes=0
        self.flash=bytes((i*19+7)&255 for i in range(6780))
    def ctrl_transfer(self,request_type,b_request,w_value,w_index,length,timeout=0):
        assert request_type == 0xC0, 'Only USB vendor IN requests are part of this extension'
        self.calls.append((b_request,w_value,w_index,length))
        if b_request==0x00: return bytes([0x1a,0x7c,64,5,0x93,0x11,0xe0 if self.ext else 0,0])
        if not self.ext: return b''
        if b_request==0xB0:
            if not 1<=length<=8 or w_index or w_value<0 or w_value+length>len(self.flash): return b''
            return self.flash[w_value:w_value+length]
        if b_request==0xF0:
            if self.busy_ticks:
                self.busy_ticks-=1
                return b'\x01'
            return b'\x00'
        if b_request==0xA0:
            return bytes((self.e[w_value],)) if 0<=w_value<64 else b''
        if b_request==0xC0:
            if not 0<=w_value<64 or not 0<=w_index<256:return b'\x02'
            if self.busy_ticks:return b'\x01'
            self.e[w_value]=w_index; self.writes+=1;self.busy_ticks=2
            return b'\x00'
        return b''

class HostTests(unittest.TestCase):
    def make(self,ext=True):
        dev=FakeDevice(ext)
        api=m.EEPROMTool(dev,sleep=lambda _:None)
        if ext: self.assertEqual(api.check_device(),64)
        return api,dev
    def test_info(self):
        api,d=self.make();self.assertEqual(api.size,64)
        bad,_=self.make(False)
        with self.assertRaises(m.EEPROMError): bad.check_device()
    def test_full_read(self):
        api,dev=self.make()
        self.assertEqual(api.read(),bytes(range(64)))
    def test_program_skip_unchanged_and_verify(self):
        api,dev=self.make();patch={0:0,1:255,63:22}
        self.assertEqual(api.program(patch),2)
        self.assertEqual(dev.writes,2)
        api.verify(patch)
        self.assertEqual(api.program(patch),0)
        self.assertEqual(dev.writes,2)
    def test_write_force(self):
        api,dev=self.make()
        self.assertEqual(api.program({0:0,1:1},skip_unchanged=False),2)
    def test_verify_detects_mismatch(self):
        api,dev=self.make()
        with self.assertRaisesRegex(m.EEPROMError,'mismatch'):
            api.verify({3:12})
    def test_bounds_and_missing_check(self):
        api,dev=self.make()
        for a in (-1,64,255,65535):
            with self.assertRaises(m.EEPROMError):api.read_byte(a)
        with self.assertRaises(m.EEPROMError):api.write_byte(0,256)
        raw=m.EEPROMTool(dev)
        with self.assertRaises(m.EEPROMError):raw.read_byte(0)
    def test_hex_roundtrip(self):
        rng=random.Random(123)
        for n in (0,1,16,17,32,63,64):
            data=bytes(rng.randrange(256) for _ in range(n))
            hx=m.write_hex_bytes(data)
            self.assertEqual(m.load_hex_bytes(hx),dict(enumerate(data)))
    def test_sparse_hex_and_bad_checksum(self):
        text='\n'.join([m.hex_rec(5,b'\x11\x22'),m.hex_rec(62,b'\xFF\x00'),m.hex_rec(0,b'',1)])
        self.assertEqual(m.load_hex_bytes(text),{5:0x11,6:0x22,62:255,63:0})
        with self.assertRaisesRegex(m.EEPROMError,'checksum'):
            m.load_hex_bytes(text.replace('FF00','FF01'))
        with self.assertRaisesRegex(m.EEPROMError,'exceeds'):
            m.load_hex_bytes('\n'.join([m.hex_rec(63,b'\x01\x02'),m.hex_rec(0,b'',1)]))
    def test_eep_extension(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'test.eep'
            p.write_text('\n'.join([m.hex_rec(10,b'\x12\x34'),m.hex_rec(0,b'',1)]))
            self.assertEqual(m.load_image(p),{10:18,11:52})
    def test_transport_error(self):
        class Broken:
            def ctrl_transfer(self,*a,**b):raise OSError('disconnected')
        with self.assertRaises(m.EEPROMError):m.EEPROMTool(Broken()).check_device()

if __name__=='__main__':unittest.main(verbosity=2)


class FlashHostTests(unittest.TestCase):
    def setup_tool(self):
        dev=FakeDevice()
        tool=m.EEPROMTool(dev, sleep=lambda _:None)
        tool.check_device()
        return tool,dev
    def test_flash_dump_full_and_partial(self):
        t,d=self.setup_tool()
        self.assertEqual(t.flash_size,6780)
        self.assertEqual(t.read_flash(),d.flash)
        self.assertEqual(t.read_flash(0x19ff,27),d.flash[0x19ff:0x19ff+27])
        request_lengths=[call[3] for call in d.calls if call[0]==0xb0]
        self.assertIn(8,request_lengths);self.assertIn(4,request_lengths)
        self.assertTrue(all(1<=length<=8 for length in request_lengths))
    def test_flash_verify(self):
        t,d=self.setup_tool()
        t.verify_flash({8:d.flash[8],13:d.flash[13],6779:d.flash[6779]})
        with self.assertRaisesRegex(m.EEPROMError,'Flash mismatch'):
            t.verify_flash({8:(d.flash[8]^0xff)})
        t.verify_flash({0:0x00,1:0x01},skip_reset_vector=True)
    def test_flash_bounds(self):
        t,d=self.setup_tool()
        for address,length in ((6780,1),(6779,2),(-1,1),(0,9),(0,0)):
            with self.assertRaises(m.EEPROMError):t.read_flash_block(address,length)
        for start,length in ((-1,1),(6779,2),(6781,0)):
            with self.assertRaises(m.EEPROMError):t.read_flash(start,length)
    def test_sparse_flash_hex(self):
        d=bytes(range(21))
        self.assertEqual(m.load_hex_bytes(m.write_hex_bytes(d,base=0x1a10),max_size=6780),
                         dict((i+0x1a10,x) for i,x in enumerate(d)))
    def test_flash_writer_delegates_to_existing_micronucleus(self):
        from unittest.mock import patch
        from subprocess import CompletedProcess
        with patch.object(m.shutil,'which',return_value='/usr/bin/micronucleus'),patch.object(m.subprocess,'run',return_value=CompletedProcess([],0)) as run:
            rc=m.write_flash_using_official_tool(Path('program.hex'),run=True)
            self.assertEqual(rc,0)
            run.assert_called_once_with(['micronucleus','--run','program.hex'],check=False)
