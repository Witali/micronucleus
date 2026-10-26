#!/usr/bin/env python3
"""Opt-in, guarded old-loader / streaming-V2 memory benchmark.

Imports and tests never access USB. Backups and results belong outside Git.
The old-loader phase never sends global ERASE or RUN; its eight initially
erased scratch pages are written once and left for the necessary CLI transition.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
import time

FLASH_START=0x1800
FLASH_END=0x1a00
FLASH_PAGE=64
COMMON_FLASH=6908
EEPROM_BYTES=64
VID,PID=0x16d0,0x0753


class BenchmarkError(RuntimeError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


@dataclass
class Counters:
    control_transactions:int=0
    control_payload_bytes:int=0
    usb_seconds:float=0
    completion_transactions:int=0
    completion_usb_seconds:float=0
    program_settle_seconds:float=0
    poll_sleep_seconds:float=0


class Meter:
    def __init__(self,clock=time.perf_counter,sleep=time.sleep):
        self.clock,self.sleep=clock,sleep
        self.totals=Counters()
        self.rows=[]

    def pause(self,seconds,kind):
        start=self.clock()
        self.sleep(seconds)
        setattr(self.totals,kind,getattr(self.totals,kind)+self.clock()-start)

    def measure(self,name,size,operation,**metadata):
        before=asdict(self.totals);start=self.clock();success=False
        try:
            result=operation();success=True
            return result
        finally:
            elapsed=self.clock()-start
            delta={key:value-before[key] for key,value in asdict(self.totals).items()}
            row={'operation':name,'bytes':size,'wall_seconds':elapsed,'success':success,
                 'bytes_per_second':size/elapsed if elapsed else None,**delta,**metadata}
            row['host_other_seconds']=max(0,elapsed-sum(delta[key] for key in (
                'usb_seconds','completion_usb_seconds','program_settle_seconds','poll_sleep_seconds')))
            self.rows.append(row)


class Adapter:
    name='abstract'
    flash_chunk=0
    eeprom_chunk=0
    def __init__(self,dev,meter=None,timeout_ms=6000,poll_interval=0.001):
        self.dev=dev;self.meter=meter or Meter();self.timeout_ms=timeout_ms
        self.poll_interval=poll_interval;self.connected=False
        self.identity=None

    def ctrl(self,request_type,request,value=0,index=0,data=0,*,completion=False):
        start=self.meter.clock()
        try:
            result=self.dev.ctrl_transfer(request_type,request,value,index,data,timeout=self.timeout_ms)
        finally:
            elapsed=self.meter.clock()-start
            if completion:
                self.meter.totals.completion_transactions+=1
                self.meter.totals.completion_usb_seconds+=elapsed
            else:
                self.meter.totals.control_transactions+=1
                self.meter.totals.usb_seconds+=elapsed
        if request_type&0x80:
            result=bytes(result)
            if len(result)!=data:raise BenchmarkError(f'Short response for request {request:#04x}')
            self.meter.totals.control_payload_bytes+=len(result)
        else:
            if not isinstance(result,int) or result!=len(data):
                raise BenchmarkError(f'Short OUT transfer for request {request:#04x}')
            self.meter.totals.control_payload_bytes+=len(data)
        return result

    def require_scratch(self,address,size):
        if not self.connected:raise BenchmarkError('Connect and validate geometry first')
        if address%FLASH_PAGE or size!=FLASH_PAGE or not FLASH_START<=address<FLASH_END:
            raise BenchmarkError('Flash mutation must be one aligned scratch page')

    def read(self,kind,address,size,chunk=None):
        if not self.connected:raise BenchmarkError('Connect before reading memory')
        maximum=self.flash_chunk if kind==0 else self.eeprom_chunk
        chunk=maximum if chunk is None else chunk
        limit=COMMON_FLASH if kind==0 else EEPROM_BYTES
        if kind not in (0,1) or not 1<=chunk<=maximum or address<0 or size<0 or address+size>limit:
            raise BenchmarkError('Read range or chunk exceeds common benchmark geometry')
        return b''.join(self.read_chunk(kind,at,min(chunk,address+size-at))
                        for at in range(address,address+size,chunk))


class Legacy(Adapter):
    name='legacy-2.8'
    flash_chunk=8
    eeprom_chunk=1
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.prepared=False;self.flash_traffic_started=False;self.transport_ambiguous=False

    def flash_out(self,request,value,index):
        self.flash_traffic_started=True
        self.transport_ambiguous=True
        result=self.ctrl(0x40,request,value,index,b'')
        self.transport_ambiguous=False
        return result

    def prepare_flash(self,*,fresh_reset_confirmed=False):
        if not fresh_reset_confirmed or self.flash_traffic_started:
            raise BenchmarkError('Legacy cursor priming requires one controlled fresh RESET and no prior Flash commands')
        # Exact installed be203513... opcodes were independently executed:
        # request1 is ignored at reset cursor0; one request3 stages two words
        # only (SPM=01), advances cursor to4, and queues no page COMMIT.
        # A selecting request1 also precedes the pair: at reset it is ignored;
        # at any independently proved idle cursor it first selects scratch.
        # Final request1/CTPB=11 discards the staged words in either case.
        first=self.read(0,0,4)
        self.flash_out(1,FLASH_PAGE,FLASH_START)
        self.flash_out(3,int.from_bytes(first[:2],'little'),int.from_bytes(first[2:],'little'))
        self.flash_out(1,FLASH_PAGE,FLASH_START)
        self.prepared=True

    def abort_known_buffer(self):
        if not self.flash_traffic_started:return True
        if self.transport_ambiguous:return False
        # Let any acknowledged final-word COMMIT finish before changing its
        # cursor. Never retry ambiguous data commands or blind-prime again.
        self.meter.pause(max(0.020,2*self.flash_settle/1000),'program_settle_seconds')
        self.flash_out(1,FLASH_PAGE,FLASH_START)
        return True

    def connect(self):
        if int(self.dev.bcdDevice)!=0x0208:raise BenchmarkError('Expected installed Micronucleus+ 2.8')
        data=self.ctrl(0xc0,0,data=8)
        if int.from_bytes(data[:2],'big')!=COMMON_FLASH or data[2]!=FLASH_PAGE or data[4:6]!=b'\x93\x11' or data[6]&0xc0!=0xc0:
            raise BenchmarkError('Unexpected installed-loader identity or memory geometry')
        self.flash_settle=(data[3]&0x7f)+2
        self.connected=True
        self.wait_ready()
        self.identity={'protocol':self.name,'bcdDevice':0x0208,'flash_chunk':8,'eeprom_chunk':1,
                       'flash_program_host_settle_ms':self.flash_settle}
        return self.identity

    def wait_ready(self):
        end=self.meter.clock()+1.0
        while True:
            value=self.ctrl(0xc0,0xf0,data=1,completion=True)[0]
            if value==0:return
            if value!=1 or self.meter.clock()>=end:raise BenchmarkError('Legacy EEPROM readiness failed')
            self.meter.pause(self.poll_interval,'poll_sleep_seconds')

    def read_chunk(self,kind,address,size):
        return self.ctrl(0xc0,0xb0 if kind==0 else 0xa0,address,0,size)

    def write_page(self,address,data):
        self.require_scratch(address,len(data))
        if not self.prepared:raise BenchmarkError('Prepare the proven fresh-reset legacy cursor first')
        self.flash_out(1,FLASH_PAGE,address)
        for off in range(0,FLASH_PAGE,4):
            self.flash_out(3,int.from_bytes(data[off:off+2],'little'),
                           int.from_bytes(data[off+2:off+4],'little'))
        self.meter.pause(self.flash_settle/1000,'program_settle_seconds')

    def write_eeprom(self,data):
        if not self.connected or len(data)!=EEPROM_BYTES:raise BenchmarkError('Expected all 64 EEPROM bytes')
        self.wait_ready()
        for address,value in enumerate(data):
            status=self.ctrl(0xc0,0xc0,address,value,1)[0]
            if status!=0:raise BenchmarkError('Legacy EEPROM write was not accepted')
            self.wait_ready()


def validate_manifest(manifest):
    values={
        'purpose':'guarded-memory-benchmark','flash_mutation_start':FLASH_START,
        'flash_mutation_end_exclusive':FLASH_END,'flash_mutation_page_bytes':FLASH_PAGE,
        'eeprom_mutation_start':0,'eeprom_mutation_end_exclusive':EEPROM_BYTES,
        'protected_boot_address':0x1b00,'benchmark_feature_mask':0x80,
        'status_features':0x83,'status_app_size_field':0x1ffc,'run_request_enabled':False,
    }
    if any(manifest.get(key)!=value for key,value in values.items()):
        raise BenchmarkError('Manifest does not describe the guarded benchmark application')


class Block64(Adapter):
    name='guarded-streaming-v2'
    flash_chunk=eeprom_chunk=64
    def __init__(self,dev,manifest,*,flash_settle_ms=18,**kwargs):
        super().__init__(dev,**kwargs)
        validate_manifest(manifest)
        if not 12<=flash_settle_ms<=100:raise BenchmarkError('Flash settle must be 12..100 ms')
        self.manifest=manifest;self.flash_settle_ms=flash_settle_ms

    def status(self):
        data=self.ctrl(0xc0,0x12,data=8,completion=True)
        if data[0] not in (0,1,2,3) or data[1]>7 or data[2:]!=b'\x1f\xfc\x40\x40\x33\x83':
            raise BenchmarkError('Guarded benchmark status/identity changed')
        return data[0]

    def connect(self):
        if int(self.dev.bcdDevice)!=0x0303:raise BenchmarkError('Expected guarded application USB version 3.3')
        self.wait_ready();self.connected=True
        self.identity={'protocol':self.name,'bcdDevice':0x0303,'flash_chunk':64,'eeprom_chunk':64,
                       'flash_program_host_settle_ms':self.flash_settle_ms,
                       'benchmark_body_sha256':self.manifest.get('sha256_body')}
        return self.identity

    def wait_ready(self):
        end=self.meter.clock()+2.0
        while True:
            value=self.status()
            if value==0:return
            if value!=1 or self.meter.clock()>=end:raise BenchmarkError('Block64 memory operation failed')
            self.meter.pause(self.poll_interval,'poll_sleep_seconds')

    def read_chunk(self,kind,address,size):
        return self.ctrl(0xc0,0x10,address,kind,size)

    def flash_operation(self,request,address,data):
        if request not in (0x11,0x14):raise BenchmarkError('Unsupported Flash operation')
        self.require_scratch(address,FLASH_PAGE)
        self.ctrl(0x40,request,address,0,data)
        self.meter.pause(self.flash_settle_ms/1000,'program_settle_seconds')
        self.wait_ready()

    def erase_page(self,address):
        self.flash_operation(0x14,address,b'')

    def write_page(self,address,data):
        if len(data)!=FLASH_PAGE:raise BenchmarkError('Flash page must contain 64 bytes')
        self.flash_operation(0x11,address,bytes(data))

    def write_eeprom(self,data):
        if not self.connected or len(data)!=EEPROM_BYTES:raise BenchmarkError('Expected all 64 EEPROM bytes')
        self.ctrl(0x40,0x11,0,1,bytes(data));self.wait_ready()


def private_destination(directory):
    path=Path(directory).resolve()
    for parent in Path(__file__).resolve().parents:
        if (parent/'.git').exists():
            if path==parent or parent in path.parents:
                raise BenchmarkError('Private backups/results must be outside the Git checkout')
            break
    path.mkdir(parents=True,exist_ok=True)
    return path


def benchmark(adapter,private_dir,*,runs=3,equal_chunk=True,expected_flash=None,
              expected_eeprom=None,defer_legacy_flash_restore=False,
              legacy_fresh_reset_confirmed=False,progress=None):
    if not 1<=runs<=5:raise BenchmarkError('Runs must be between one and five')
    legacy=isinstance(adapter,Legacy)
    if legacy and not defer_legacy_flash_restore:
        raise BenchmarkError('Legacy scratch restoration must be assigned to the following CLI transition')
    if legacy and not legacy_fresh_reset_confirmed:
        raise BenchmarkError('Legacy Flash benchmark requires operator-confirmed fresh RESET before connection')
    destination=private_destination(private_dir)
    notify=progress or (lambda message:None)
    report={'passed':False,'runs':runs,'identity':adapter.identity or adapter.connect(),'measurements':adapter.meter.rows,
            'flash_scratch':[FLASH_START,FLASH_END],'common_flash_bytes':COMMON_FLASH,
            'eeprom_bytes':EEPROM_BYTES,'restoration':{},'errors':[],
            'timing_scope':'USB calls include driver scheduling, retries/NAKs and firmware busy time; fixed host waits are separate. Silicon programming duration is not measured.',
            'legacy_flash_erase':'Not issued. The necessary external CLI transition may be timed separately; its full-application host-paced erase is a different scope.',
            'equal_chunk_control':'Flash READ at8 bytes; EEPROM READ at1 byte. WRITE formats remain native.'}
    notify('Reading and checking private pre-benchmark backups; no writes yet.')
    flash=adapter.read(0,0,COMMON_FLASH);eeprom=adapter.read(1,0,EEPROM_BYTES)
    if expected_flash is not None and flash!=bytes(expected_flash)[:COMMON_FLASH]:raise BenchmarkError('Flash differs from the verified pre-benchmark image')
    if expected_eeprom is not None and eeprom!=bytes(expected_eeprom):raise BenchmarkError('EEPROM differs from the verified backup')
    scratch=flash[FLASH_START:FLASH_END]
    if scratch!=b'\xff'*(FLASH_END-FLASH_START):raise BenchmarkError('Scratch pages are not initially erased; no mutation performed')
    for name,data in (('flash-common-before.bin',flash),('eeprom-before.bin',eeprom),('scratch-before.bin',scratch)):
        with (destination/name).open('xb') as file:file.write(data)
    report['before_sha256']={'flash_common':digest(flash),'eeprom':digest(eeprom),'scratch':digest(scratch)}
    if legacy:
        report['legacy_cursor_assumption']={
            'fresh_reset_confirmed':True,'no_prior_flash_commands':True,
            'externally_verified_loader_body_sha256':'be2035139b301739837b5a214773e0a0421404450b078d40e2bf0c02aafa77c4',
            'preparation':'request1 scratch; one request3 buffer-load pair; request1 scratch CTPB; no page0 programming'}
    measure=adapter.meter.measure
    flash_dirty=False

    def same(actual,wanted,description):
        if actual!=wanted:raise BenchmarkError(description+' verification failed')

    def read_sample(kind,size,chunk,label,run,wanted):
        data=measure(label,size,lambda:adapter.read(kind,0,size,chunk),run=run,chunk=chunk)
        same(data,wanted,label);adapter.meter.rows[-1]['sha256']=digest(data)

    def pages(operation):
        for address in range(FLASH_START,FLASH_END,FLASH_PAGE):operation(address)

    try:
        for run in range(runs):
            notify(f'Read benchmark run {run+1}/{runs}.')
            read_sample(0,COMMON_FLASH,adapter.flash_chunk,'flash.read.common',run,flash)
            read_sample(1,EEPROM_BYTES,adapter.eeprom_chunk,'eeprom.read',run,eeprom)
            if equal_chunk and adapter.flash_chunk!=8:read_sample(0,COMMON_FLASH,8,'flash.read.common.control8',run,flash)
            if equal_chunk and adapter.eeprom_chunk!=1:read_sample(1,EEPROM_BYTES,1,'eeprom.read.control1',run,eeprom)
        for run in range(runs):
            notify(f'EEPROM write/read/erase verification run {run+1}/{runs}.')
            pattern=bytes((index*73+0x35+run*29)&255 for index in range(EEPROM_BYTES))
            measure('eeprom.write',EEPROM_BYTES,lambda:adapter.write_eeprom(pattern),run=run)
            same(adapter.read(1,0,EEPROM_BYTES),pattern,'EEPROM write')
            measure('eeprom.erase_to_ff',EEPROM_BYTES,lambda:adapter.write_eeprom(b'\xff'*EEPROM_BYTES),run=run)
            same(adapter.read(1,0,EEPROM_BYTES),b'\xff'*EEPROM_BYTES,'EEPROM erase-to-FF')
        # Restore before Flash work too: a failed legacy page transfer can
        # leave a partial SPM buffer that correctly rejects EEPROM writes.
        notify('Restoring original EEPROM before Flash work.')
        adapter.write_eeprom(eeprom)
        same(adapter.read(1,0,EEPROM_BYTES),eeprom,'Restored EEPROM before Flash')
        pattern=bytes((index*109+0x27)&255 for index in range(FLASH_END-FLASH_START))
        report['controlled_flash_payload_sha256']=digest(pattern)
        if legacy:
            notify('Preparing the independently proven fresh-reset Flash cursor; buffer loads only.')
            measure('flash.prepare.cursor',0,lambda:adapter.prepare_flash(fresh_reset_confirmed=True))
        for run in range(1 if legacy else runs):
            notify(f'Flash scratch write/read run {run+1}/{1 if legacy else runs}.')
            flash_dirty=True
            if not legacy:
                measure('flash.erase.scratch',len(scratch),lambda:pages(adapter.erase_page),run=run,pages=8)
                same(adapter.read(0,FLASH_START,len(scratch)),b'\xff'*len(scratch),'Flash erase')
            def write_pages():
                for address in range(FLASH_START,FLASH_END,FLASH_PAGE):
                    offset=address-FLASH_START
                    measure('flash.write.page',FLASH_PAGE,
                            lambda address=address,offset=offset:adapter.write_page(address,pattern[offset:offset+FLASH_PAGE]),
                            run=run,address=address)
            measure('flash.write.scratch',len(scratch),write_pages,run=run,pages=8,aggregate_of='flash.write.page')
            actual=measure('flash.read.controlled',len(scratch),lambda:adapter.read(0,FLASH_START,len(scratch)),run=run,chunk=adapter.flash_chunk)
            same(actual,pattern,'Controlled Flash payload')
            if equal_chunk and adapter.flash_chunk!=8:
                actual=measure('flash.read.controlled.control8',len(scratch),lambda:adapter.read(0,FLASH_START,len(scratch),8),run=run,chunk=8)
                same(actual,pattern,'Controlled Flash payload at chunk8')
        report['passed']=True
    except Exception as error:
        report['errors'].append(str(error))
    finally:
        notify('Verifying original EEPROM and restoring guarded scratch where supported.')
        if legacy and not report['passed'] and adapter.flash_traffic_started:
            try:
                cleared=adapter.abort_known_buffer()
                report['restoration']['legacy_buffer_cleared']=cleared
                if not cleared:report['restoration']['operator_reset_required']=True
            except Exception as error:
                report['errors'].append('Legacy buffer recovery: '+str(error))
                report['restoration']['operator_reset_required']=True
        try:
            adapter.wait_ready()
            if adapter.read(1,0,EEPROM_BYTES)!=eeprom:
                if legacy and adapter.transport_ambiguous:
                    raise BenchmarkError('Operator RESET is required before EEPROM restoration after ambiguous Flash transfer')
                adapter.write_eeprom(eeprom)
            same(adapter.read(1,0,EEPROM_BYTES),eeprom,'Restored EEPROM')
            report['restoration']['eeprom_verified']=True
        except Exception as error:
            report['errors'].append('EEPROM restoration: '+str(error));report['passed']=False
        if flash_dirty and not legacy:
            try:
                pages(adapter.erase_page)
                same(adapter.read(0,FLASH_START,len(scratch)),scratch,'Restored scratch')
                report['restoration']['flash_scratch_verified']=True
            except Exception as error:
                report['errors'].append('Scratch restoration: '+str(error));report['passed']=False
        if legacy:
            report['restoration']['flash_requires_external_cli_transition']=flash_dirty
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exercise-hardware',action='store_true',required=True)
    parser.add_argument('--protocol',choices=['legacy','block64'],required=True)
    parser.add_argument('--private-dir',type=Path,required=True)
    parser.add_argument('--expected-flash',type=Path)
    parser.add_argument('--expected-eeprom',type=Path,required=True)
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--defer-legacy-flash-restore-to-transition',action='store_true')
    parser.add_argument('--legacy-fresh-reset-confirmed',action='store_true')
    parser.add_argument('--runs',type=int,default=3)
    parser.add_argument('--equal-chunk-control',action=argparse.BooleanOptionalAction,default=True)
    parser.add_argument('--flash-settle-ms',type=float,default=18)
    parser.add_argument('--dll');parser.add_argument('--python-libs',type=Path)
    parser.add_argument('--wait-seconds',type=float,default=120)
    args=parser.parse_args()
    if args.python_libs:
        import sys
        sys.path.insert(0,str(args.python_libs))
    import usb.core
    import usb.backend.libusb0
    backend=usb.backend.libusb0.get_backend(find_library=lambda _:args.dll) if args.dll else None
    destination=private_destination(args.private_dir)
    if (destination/'report.json').exists():raise BenchmarkError('Use a fresh private directory for each phase')
    manifest=json.loads(args.manifest.read_text()) if args.manifest else None
    if args.protocol=='block64':validate_manifest(manifest or {})
    if args.protocol=='legacy' and not args.expected_flash:
        raise BenchmarkError('Legacy mode requires the fresh verified Flash backup')
    if args.protocol=='legacy' and not args.legacy_fresh_reset_confirmed:
        raise BenchmarkError('Legacy mode requires --legacy-fresh-reset-confirmed under operator orchestration')
    expected_eeprom=args.expected_eeprom.read_bytes()
    if len(expected_eeprom)!=EEPROM_BYTES:raise BenchmarkError('Expected EEPROM backup must be exactly 64 bytes')
    expected_flash=args.expected_flash.read_bytes() if args.expected_flash else None
    if expected_flash is not None and not COMMON_FLASH<=len(expected_flash)<=8192:
        raise BenchmarkError('Expected Flash backup must contain 6908..8192 bytes')
    until=time.monotonic()+args.wait_seconds
    adapter=None
    print(f'Waiting for {args.protocol} USB identity; no memory writes have started.',flush=True)
    while time.monotonic()<until:
        try:
            devices=list(usb.core.find(find_all=True,idVendor=VID,idProduct=PID,backend=backend))
            matching=[dev for dev in devices if int(dev.bcdDevice)==(0x0208 if args.protocol=='legacy' else 0x0303)]
            if len(matching)>1:raise BenchmarkError('More than one matching device is connected')
            if matching:
                candidate=Legacy(matching[0]) if args.protocol=='legacy' else Block64(matching[0],manifest,flash_settle_ms=args.flash_settle_ms)
                try:
                    candidate.connect()
                    adapter=candidate;break
                except (usb.core.USBError,BenchmarkError):
                    pass  # Reset/enumeration can expose the descriptor before EP0 is ready.
        except usb.core.USBError:
            pass
        time.sleep(0.1)
    if adapter is None:raise BenchmarkError('Expected benchmark device was not observed')
    print('USB identity validated. Beginning bounded memory benchmark.',flush=True)
    try:
        report=benchmark(adapter,destination,runs=args.runs,equal_chunk=args.equal_chunk_control,
            expected_flash=expected_flash,expected_eeprom=expected_eeprom,
            defer_legacy_flash_restore=args.defer_legacy_flash_restore_to_transition,
            legacy_fresh_reset_confirmed=args.legacy_fresh_reset_confirmed,
            progress=lambda message:print(message,flush=True))
    except Exception as error:
        report={'passed':False,'errors':[str(error)]}
    (destination/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'protocol':args.protocol,
                      'measurements':len(report.get('measurements',[])),
                      'errors':report.get('errors',[])},indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
