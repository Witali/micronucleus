"""Host framing, timing separation, mutation bounds and failure restoration."""
from pathlib import Path
import sys
import pytest

HOST=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HOST))
from benchmark import (Legacy,Block64,Meter,BenchmarkError,benchmark,validate_manifest,
                       private_destination,FLASH_START,FLASH_END,COMMON_FLASH)


def manifest():
    return {'purpose':'guarded-memory-benchmark','flash_mutation_start':0x1800,
        'flash_mutation_end_exclusive':0x1a00,'flash_mutation_page_bytes':64,
        'eeprom_mutation_start':0,'eeprom_mutation_end_exclusive':64,
        'protected_boot_address':0x1b00,'benchmark_feature_mask':0x80,
        'status_features':0x83,'status_app_size_field':0x1ffc,'run_request_enabled':False}


class Clock:
    now=0.0
    def __call__(self):return self.now
    def sleep(self,seconds):self.now+=seconds


class Device:
    def __init__(self,clock,legacy):
        self.clock=clock;self.legacy=legacy;self.bcdDevice=0x0208 if legacy else 0x0303
        self.flash=bytearray(b'\xff'*8192);self.flash[:512]=bytes(range(256))*2
        self.flash[:2]=bytes.fromhex('7fcd')
        self.eeprom=bytearray((i*41+9)&255 for i in range(64))
        self.calls=[];self.page_address=None;self.page_buffer=bytearray()
        self.written=set();self.features=0x83;self.fail_program=False
        self.cursor=0;self.buffer=bytearray(b'\xff'*64)
        self.legacy_data_calls=0;self.fail_legacy_data_call=None

    def ctrl_transfer(self,rt,request,value,index,data,timeout):
        self.clock.now+=0.001;self.calls.append((rt,request,value,index,data))
        if self.legacy:
            if rt==0xc0:
                if request==0:return bytes([0x1a,0xfc,64,5,0x93,0x11,0xc0,1])
                if request==0xf0:return b'\0'
                if request==0xb0:return bytes(self.flash[value:value+data])
                if request==0xa0:
                    assert data==1
                    return bytes([self.eeprom[value]])
                if request==0xc0:
                    self.eeprom[value]=index;return b'\0'
            if rt==0x40 and request==1:
                assert value==64 and FLASH_START<=index<FLASH_END
                if self.cursor==0:return 0 # Deployed legacy quirk: first page select is ignored.
                self.cursor=index;self.buffer=bytearray(b'\xff'*64);return 0
            if rt==0x40 and request==3:
                self.legacy_data_calls+=1
                if self.legacy_data_calls==self.fail_legacy_data_call:raise BenchmarkError('Injected ambiguous legacy transfer')
                offset=self.cursor%64
                self.buffer[offset:offset+4]=value.to_bytes(2,'little')+index.to_bytes(2,'little')
                self.cursor+=4
                if self.cursor%64==0:
                    base=(self.cursor-2)&~63
                    assert FLASH_START<=base<FLASH_END and base not in self.written
                    self.flash[base:base+64]=self.buffer;self.written.add(base)
                    self.buffer=bytearray(b'\xff'*64)
                return 0
        else:
            if rt==0xc0 and request==0x12:return bytes([0,0,0x1f,0xfc,64,64,0x33,self.features])
            if rt==0xc0 and request==0x10:
                source=self.flash if index==0 else self.eeprom
                return bytes(source[value:value+data])
            if rt==0x40 and request==0x14:
                assert index==0 and FLASH_START<=value<FLASH_END and value%64==0
                self.flash[value:value+64]=b'\xff'*64;self.written.discard(value);return 0
            if rt==0x40 and request==0x11:
                if index==1:self.eeprom[value:value+len(data)]=data
                else:
                    assert FLASH_START<=value<FLASH_END and value%64==0 and len(data)==64
                    if self.fail_program:raise BenchmarkError('Injected Flash write failure')
                    assert self.flash[value:value+64]==b'\xff'*64
                    self.flash[value:value+64]=data;self.written.add(value)
                return len(data)
        raise AssertionError(f'Unexpected or destructive USB request: {rt:#x}/{request:#x}')


def setup(legacy):
    clock=Clock();device=Device(clock,legacy);meter=Meter(clock,clock.sleep)
    adapter=Legacy(device,meter=meter) if legacy else Block64(device,manifest(),meter=meter)
    return adapter,device


def test_legacy_writes_only_once_and_keeps_original_eeprom(tmp_path):
    adapter,dev=setup(True);original_ee=bytes(dev.eeprom);original_flash=bytes(dev.flash)
    report=benchmark(adapter,tmp_path,runs=2,expected_flash=original_flash,
                     expected_eeprom=original_ee,defer_legacy_flash_restore=True,
                     legacy_fresh_reset_confirmed=True)
    assert report['passed'] and bytes(dev.eeprom)==original_ee
    assert len(dev.written)==8
    assert bytes(dev.flash[:FLASH_START])==original_flash[:FLASH_START]
    assert bytes(dev.flash[FLASH_END:])==original_flash[FLASH_END:]
    assert report['restoration']['flash_requires_external_cli_transition']
    assert not any(rt==0x40 and req in (2,4,0x13) for rt,req,*_ in dev.calls)
    aggregate=[row for row in report['measurements'] if row['operation']=='flash.write.scratch']
    assert len(aggregate)==1
    row=aggregate[0]
    assert row['control_transactions']==8*17
    assert row['program_settle_seconds']==pytest.approx(8*0.007)
    assert row['usb_seconds']==pytest.approx(8*17*0.001)
    assert row['wall_seconds']==pytest.approx(8*(0.017+0.007))
    assert (tmp_path/'eeprom-before.bin').read_bytes()==original_ee
    preparation=[row for row in report['measurements'] if row['operation']=='flash.prepare.cursor']
    assert preparation[0]['control_transactions']==4


def test_block64_multiple_rounds_and_exact_restoration(tmp_path):
    adapter,dev=setup(False);original_flash=bytes(dev.flash);original_ee=bytes(dev.eeprom)
    report=benchmark(adapter,tmp_path,runs=2,expected_eeprom=original_ee)
    assert report['passed']
    assert bytes(dev.flash)==original_flash and bytes(dev.eeprom)==original_ee
    assert report['restoration']=={'eeprom_verified':True,'flash_scratch_verified':True}
    writes=[row for row in report['measurements'] if row['operation']=='flash.write.scratch']
    assert len(writes)==2
    assert writes[0]['control_transactions']==8
    assert writes[0]['completion_transactions']==8
    assert writes[0]['program_settle_seconds']==pytest.approx(8*0.018)
    reads=[row for row in report['measurements'] if row['operation']=='flash.read.common']
    controls=[row for row in report['measurements'] if row['operation']=='flash.read.common.control8']
    assert reads[0]['control_transactions']==108
    assert controls[0]['control_transactions']==864
    assert not any(rt==0x40 and req in (2,4,0x13) for rt,req,*_ in dev.calls)


def test_failure_restores_eeprom_and_scratch(tmp_path):
    adapter,dev=setup(False);original_flash=bytes(dev.flash);original_ee=bytes(dev.eeprom)
    dev.fail_program=True
    report=benchmark(adapter,tmp_path,runs=1)
    assert not report['passed'] and report['errors']
    assert bytes(dev.flash)==original_flash and bytes(dev.eeprom)==original_ee
    assert report['restoration']['eeprom_verified']
    assert report['restoration']['flash_scratch_verified']


def test_bad_identity_manifest_and_write_bounds_fail_before_mutation():
    bad=manifest();bad['flash_mutation_end_exclusive']=0x1b00
    with pytest.raises(BenchmarkError):validate_manifest(bad)
    adapter,dev=setup(False);dev.features=3
    with pytest.raises(BenchmarkError):adapter.connect()
    assert not any(rt==0x40 for rt,*_ in dev.calls)
    dev.features=0x83;adapter.connect()
    for address in (0,0x17c0,0x1801,0x1a00,0x1b00):
        with pytest.raises(BenchmarkError):adapter.erase_page(address)
        with pytest.raises(BenchmarkError):adapter.write_page(address,b'\0'*64)


def test_non_erased_scratch_is_rejected_without_programming(tmp_path):
    adapter,dev=setup(True);dev.flash[FLASH_START]=0
    with pytest.raises(BenchmarkError):benchmark(adapter,tmp_path,runs=1,defer_legacy_flash_restore=True,legacy_fresh_reset_confirmed=True)
    assert not any(req in (1,2,3,0xc0) for _,req,*_ in dev.calls)


def test_private_dumps_cannot_be_written_to_checkout():
    with pytest.raises(BenchmarkError):private_destination(HOST/'private-backup-forbidden')


def test_read_control_chunks_are_protocol_bounded():
    adapter,_=setup(True);adapter.connect()
    for kind,chunk in ((0,9),(1,2)):
        with pytest.raises(BenchmarkError):adapter.read(kind,0,64,chunk)
    with pytest.raises(BenchmarkError):adapter.read(0,COMMON_FLASH-1,2)


def test_legacy_requires_fresh_reset_assurance_before_any_usb_access(tmp_path):
    adapter,dev=setup(True)
    with pytest.raises(BenchmarkError):benchmark(adapter,tmp_path,defer_legacy_flash_restore=True)
    assert dev.calls==[]


def test_legacy_prime_changes_only_temporary_buffer_and_known_abort_is_safe():
    adapter,dev=setup(True);adapter.connect();original=bytes(dev.flash)
    with pytest.raises(BenchmarkError):adapter.write_page(FLASH_START,b'\0'*64)
    adapter.prepare_flash(fresh_reset_confirmed=True)
    assert bytes(dev.flash)==original and dev.cursor==FLASH_START
    adapter.flash_out(3,0x1234,0x5678)
    assert dev.cursor==FLASH_START+4 and bytes(dev.flash)==original
    assert adapter.abort_known_buffer()
    assert dev.cursor==FLASH_START and bytes(dev.flash)==original
    with pytest.raises(BenchmarkError):adapter.prepare_flash(fresh_reset_confirmed=True)


def test_ambiguous_legacy_data_is_not_retried_and_eeprom_already_restored(tmp_path):
    adapter,dev=setup(True);original=bytes(dev.flash);ee=bytes(dev.eeprom)
    dev.fail_legacy_data_call=3
    report=benchmark(adapter,tmp_path,runs=1,defer_legacy_flash_restore=True,legacy_fresh_reset_confirmed=True)
    assert not report['passed'] and report['restoration']['operator_reset_required']
    assert not report['restoration']['legacy_buffer_cleared']
    assert dev.legacy_data_calls==3 # Prime plus one acknowledged pair plus one ambiguous call.
    assert bytes(dev.flash)==original and bytes(dev.eeprom)==ee
    assert report['restoration']['eeprom_verified']
