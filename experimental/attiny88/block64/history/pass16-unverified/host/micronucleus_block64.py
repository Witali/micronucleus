#!/usr/bin/env python3
"""Micronucleus ATtiny88 Block64 USB control-transfer programmer, protocol v3.3 (fixed 8-byte GET_STATUS).

UNTESTED ON REAL HARDWARE. Requires PyUSB/libusb when talking to a board.
The code does not use the legacy Micronucleus 2.x host write format.

All memory commands are USB vendor control transfers:
  IN   0x10 READ; wValue=byte address, wIndex=0 Flash or 1 EEPROM,
                  wLength=1..64, result is binary memory data.
  OUT  0x11 WRITE; Flash: aligned page, exactly 64 data bytes; EEPROM: 1..64.
  OUT  0x14 ERASE_PAGE; Flash page address, 0 data bytes; independent from WRITE.
  IN   0x12 GET_STATUS; wLength=8 always: result/state/geometry/version.
  OUT  0x13 RUN; zero DATA length, status stage finishes before entering app.
  (legacy INFO 0x20 has been removed).

USB low-speed EP0 still sends <=8 bytes per physical DATA packet.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
import pathlib
import sys
import time
from typing import Protocol

VID=0x16D0;PID=0x0753
REQ_READ=0x10;REQ_WRITE=0x11;REQ_STATUS=0x12;REQ_RUN=0x13;REQ_ERASE_PAGE=0x14
IN_VENDOR=0xC0;OUT_VENDOR=0x40
FLASH=0;EEPROM=1
FLASH_TOTAL=8192;EEPROM_TOTAL=64;FLASH_PAGE=64;MAX_CHUNK=64
BOOT_FEATURE_V3=0x01
BOOT_FEATURE_SPLIT_ERASE=0x02

class Block64Error(RuntimeError):pass

@dataclass(frozen=True)
class Info:
    app_size:int
    page_size:int
    eeprom_size:int
    boot_start:int
    version:int
    features:int
    status:int             # result code at GET_STATUS(8) snapshot time
    state:int              # internal state at GET_STATUS(8) snapshot time

    @property
    def flash_rw_end(self)->int:
        return self.app_size+4 # four-byte reset-vector postscript

class USBDevice(Protocol):
    bcdDevice:int
    def ctrl_transfer(self,request_type:int,request:int,value:int,index:int,data_or_wlength,timeout:int=...):...

class Programmer:
    def __init__(self,dev:USBDevice,timeout_ms:int=6000,sleep=None,spm_settle_s:float=0.018):
        self.dev=dev
        self.timeout_ms=timeout_ms
        self.info:Info|None=None
        self.sleep=sleep or time.sleep
        self.spm_settle_s=spm_settle_s

    def _ctrl(self,request_type:int,request:int,addr:int=0,memtype:int=0,data=0):
        try:
            return self.dev.ctrl_transfer(request_type,request,addr,memtype,data,timeout=self.timeout_ms)
        except Exception as e:
            raise Block64Error(f'USB request 0x{request:02X} (address {addr:#06x}) failed: {e}') from e

    def connect(self)->Info:
        version=int(getattr(self.dev,'bcdDevice',0))
        if version!=0x0303:
            raise Block64Error(f'Expected Block64 v3.3 (bcdDevice=0x0303), got 0x{version:04X}')
        head=bytes(self._ctrl(IN_VENDOR,REQ_STATUS,data=8))
        if len(head)!=8:
            raise Block64Error(f'GET_STATUS(8) returned {len(head)} bytes, expected 8')
        # Wire format: result, state, application_hi, application_lo,
        # Flash_page_bytes, EEPROM_bytes, protocol_marker, feature_bits.
        result,state,app_hi,app_lo,pagesz,eeprom,protocol,feature=head
        if result not in (0,1,2,3) or state>7:
            raise Block64Error(f'Invalid GET_STATUS state/result: {result}/{state}')
        if protocol!=0x33:
            raise Block64Error(f'Unsupported GET_STATUS protocol marker 0x{protocol:02X}')
        appsz=(app_hi<<8)|app_lo
        if pagesz!=FLASH_PAGE or eeprom!=EEPROM_TOTAL or appsz<2048 or appsz>=FLASH_TOTAL or (appsz+4)%64:
            raise Block64Error(f'Unexpected memory geometry app={appsz}, page={pagesz}, EEPROM={eeprom}')
        if (feature & (BOOT_FEATURE_V3|BOOT_FEATURE_SPLIT_ERASE))!=(BOOT_FEATURE_V3|BOOT_FEATURE_SPLIT_ERASE):
            raise Block64Error('Block64 v3.3 split ERASE/WRITE feature bits missing')
        self.info=Info(appsz,pagesz,eeprom,appsz+4,version,feature,result,state)
        return self.info

    def _require(self,kind:int,addr:int,size:int):
        if self.info is None: raise Block64Error('Connect before accessing memory')
        if kind not in (FLASH,EEPROM):raise Block64Error('Unknown memory kind')
        end=self.info.flash_rw_end if kind==FLASH else self.info.eeprom_size
        if addr<0 or size<0 or addr+size>end:
            raise Block64Error(f'{"Flash" if kind==FLASH else "EEPROM"} range {addr:#06x}+{size} exceeds {end:#06x}')

    def read(self,kind:int,start:int,length:int)->bytes:
        self._require(kind,start,length)
        result=bytearray()
        for addr in range(start,start+length,MAX_CHUNK):
            count=min(MAX_CHUNK,start+length-addr)
            packet=bytes(self._ctrl(IN_VENDOR,REQ_READ,addr,kind,count))
            if len(packet)!=count:
                raise Block64Error(f'READ 0x{addr:04X}: expected {count}, received {len(packet)} bytes')
            result.extend(packet)
        return bytes(result)

    def status(self)->int:
        """Single fixed-format GET_STATUS(8); byte 0 is the operation result."""
        result=bytes(self._ctrl(IN_VENDOR,REQ_STATUS,data=8))
        if len(result)!=8 or result[0] not in (0,1,2,3) or result[1]>7:
            raise Block64Error(f'Invalid 8-byte status reply {result.hex()}')
        return result[0]

    def _wait_for_result(self,max_seconds:float=2.0):
        # Physical SPM blocks the CPU. The host waits for the deliberately
        # deferred operation before issuing STATUS (avoids USB during SPM).
        deadline=time.monotonic()+max_seconds
        while True:
            code=self.status()
            if code==0:return
            if code!=1:raise Block64Error(f'MCU memory operation failed: status={code}')
            if time.monotonic()>=deadline:raise Block64Error('Timed out waiting for memory operation')
            self.sleep(0.010)

    def _require_flash_page(self,base:int):
        self._require(FLASH,base,FLASH_PAGE)
        if base%FLASH_PAGE:
            raise Block64Error(f'Flash page address 0x{base:04X} must be 64-byte aligned')

    def erase_page(self,base:int,verify:bool=False):
        """ERASE_PAGE is a standalone host command; no WRITE is implied."""
        self._require_flash_page(base)
        sent=self._ctrl(OUT_VENDOR,REQ_ERASE_PAGE,base,FLASH,b'')
        if isinstance(sent,int) and sent!=0:
            raise Block64Error(f'Unexpected ERASE response length: {sent}')
        self.sleep(self.spm_settle_s)
        self._wait_for_result()
        if verify and self.read(FLASH,base,FLASH_PAGE)!=b'\xff'*FLASH_PAGE:
            raise Block64Error(f'ERASE verification failed at 0x{base:04X}')

    def write_page(self,base:int,data:bytes,verify:bool=True):
        """WRITE_PAGE does NOT erase; call erase_page beforehand.

        The MCU defensively forces the first reset word to its bootloader,
        and the host also does it, so raw page-0 writes cannot bypass RESET.
        """
        self._require_flash_page(base)
        if len(data)!=FLASH_PAGE:
            raise Block64Error('Flash WRITE requires exactly 64 bytes')
        target=bytearray(data)
        if base==0:
            reset=0xC000 | (((self.info.boot_start//2)-1)&0x0FFF)
            target[:2]=reset.to_bytes(2,'little')
        sent=self._ctrl(OUT_VENDOR,REQ_WRITE,base,FLASH,bytes(target))
        if isinstance(sent,int) and sent!=FLASH_PAGE:
            raise Block64Error(f'WRITE_PAGE at 0x{base:04X}: sent {sent} instead of 64')
        self.sleep(self.spm_settle_s)
        self._wait_for_result()
        if verify:
            got=self.read(FLASH,base,FLASH_PAGE)
            if got!=target:
                raise Block64Error(f'Verification of Flash page 0x{base:04X} failed')

    def write(self,kind:int,start:int,data:bytes,verify:bool=True):
        """Convenience write. Host performs Flash RMW for partial pages.

        Firmware itself contains no Flash RMW or implicit page erase.
        """
        if not data:return
        self._require(kind,start,len(data))
        if kind==EEPROM:
            for off in range(0,len(data),MAX_CHUNK):
                addr=start+off
                part=bytes(data[off:off+MAX_CHUNK])
                sent=self._ctrl(OUT_VENDOR,REQ_WRITE,addr,EEPROM,part)
                if isinstance(sent,int) and sent!=len(part):
                    raise Block64Error(f'EEPROM WRITE 0x{addr:04X}: short transfer')
                # Unlike Flash, EEPROM service runs while the host receives
                # NAKs for STATUS until the last cell is programmed.
                self._wait_for_result()
                if verify and self.read(EEPROM,addr,len(part))!=part:
                    raise Block64Error(f'EEPROM verification failed at 0x{addr:04X}')
            return
        off=0
        while off<len(data):
            addr=start+off
            page=addr & ~(FLASH_PAGE-1)
            index=addr-page
            count=min(len(data)-off,FLASH_PAGE-index)
            if index==0 and count==FLASH_PAGE:
                # The dominant full-page case: no Flash read at all.
                target=bytes(data[off:off+FLASH_PAGE])
            else:
                # Partial updates happen on the computer, never in firmware.
                target=bytearray(self.read(FLASH,page,FLASH_PAGE))
                target[index:index+count]=data[off:off+count]
                target=bytes(target)
            self.erase_page(page)
            self.write_page(page,target,verify=verify)
            off+=count

    def run(self):
        result=self._ctrl(OUT_VENDOR,REQ_RUN,data=b'')
        if isinstance(result,int) and result!=0: raise Block64Error('RUN returned unexpected transfer length')

    def upload(self,patches:dict[int,int],full_erase:bool=True,verify:bool=True,run:bool=False):
        """Upload application, patch reset & postscript on the PC, page 0 last.

        In full-erase mode, full 64-byte Flash pages are sent without a read.
        The postscript page is erased first and written last, disabling a
        partial application until the final stage succeeds.
        """
        if self.info is None:raise Block64Error('Connect first')
        app_size=self.info.app_size
        if 0 not in patches or 1 not in patches:
            raise Block64Error('HEX image must contain a two-byte RJMP reset vector')
        if any(a<0 or a>=app_size or not 0<=v<=255 for a,v in patches.items()):
            raise Block64Error('Image contains invalid/reserved Flash address')
        orig=patches[0]|patches[1]<<8
        if orig&0xF000!=0xC000:
            raise Block64Error(f'Expected RJMP at address zero, found 0x{orig:04X}')
        target_word=((orig&0x0FFF)+1)&0x0FFF
        reset=0xC000|(((self.info.boot_start//2)-1)&0x0FFF)
        post_start=app_size
        post_off=(target_word-(post_start//2+1))&0x0FFF
        post_jump=0xC000|post_off
        final_page=self.info.boot_start-FLASH_PAGE
        if full_erase:
            image=bytearray(b'\xff'*self.info.boot_start)
        else:
            # Partial image replacement preserves unmentioned existing bytes.
            image=bytearray(self.read(FLASH,0,self.info.boot_start))
        for addr,value in patches.items():image[addr]=value
        image[:2]=reset.to_bytes(2,'little')
        image[post_start:post_start+4]=post_jump.to_bytes(2,'little')+b'\xff\xff'
        # Invalidate the old application before touching any new code.
        # Full mode needs only ERASE here (no RMW or page WRITE yet).
        if full_erase:
            self.erase_page(final_page,verify=verify)
        else:
            invalid=bytearray(image[final_page:self.info.boot_start]);invalid[-4:]=b'\xff'*4
            self.erase_page(final_page)
            self.write_page(final_page,invalid,verify=verify)
        # Other pages: reset vector page zero is delayed until just before
        # restoring the postscript. Erase every page for full replacement.
        selected=(list(range(FLASH_PAGE,final_page,FLASH_PAGE))
                  if full_erase else sorted({a&~63 for a in patches if FLASH_PAGE<=a<final_page}))
        for base in selected:
            target=bytes(image[base:base+FLASH_PAGE])
            self.erase_page(base,verify=verify and target==b'\xff'*FLASH_PAGE)
            if target!=b'\xff'*FLASH_PAGE:self.write_page(base,target,verify=verify)
        first=bytes(image[:FLASH_PAGE])
        self.erase_page(0)
        self.write_page(0,first,verify=verify)
        # The final page must be written after the reset vector page; this
        # restores the postscript and enables the completed application.
        if not full_erase:self.erase_page(final_page)
        self.write_page(final_page,bytes(image[final_page:self.info.boot_start]),verify=verify)
        if run:self.run()

def parse_hex(path:pathlib.Path)->dict[int,int]:
    mem={}
    upper=0
    seen_end=False
    for lineno,raw in enumerate(path.read_text().splitlines(),1):
        s=raw.strip()
        if not s:continue
        if not s.startswith(':') or (len(s)-1)%2:
            raise Block64Error(f'Intel HEX line {lineno}: invalid record')
        try:v=bytes.fromhex(s[1:])
        except ValueError as e:raise Block64Error(f'Intel HEX line {lineno}: malformed hex') from e
        if len(v)<5 or len(v)!=v[0]+5 or sum(v)%256:
            raise Block64Error(f'Intel HEX line {lineno}: bad length/checksum')
        n=v[0];adr=(v[1]<<8)|v[2];typ=v[3];data=v[4:-1]
        if seen_end:raise Block64Error(f'Intel HEX line {lineno}: data after EOF')
        if typ==0:
            for i,b in enumerate(data):
                k=upper+adr+i
                if k in mem and mem[k]!=b:raise Block64Error(f'Overlapping conflicting data at 0x{k:04X}')
                mem[k]=b
        elif typ==1:
            if n:raise Block64Error('Malformed EOF record')
            seen_end=True
        elif typ==2:
            if n!=2:raise Block64Error('Malformed segment record')
            upper=int.from_bytes(data,'big')<<4
        elif typ==4:
            if n!=2:raise Block64Error('Malformed linear address record')
            upper=int.from_bytes(data,'big')<<16
        elif typ in (3,5):continue
        else:raise Block64Error(f'Intel HEX record type 0x{typ:02X} unsupported')
    if not seen_end:raise Block64Error('Missing Intel HEX EOF record')
    return mem

def dump_hex(data:bytes,start:int=0)->str:
    def rec(adr:int,typ:int,payload:bytes):
        raw=bytes([len(payload),(adr>>8)&255,adr&255,typ])+payload
        return ':'+(raw+bytes([(-sum(raw))&255])).hex().upper()
    parts=[rec(start+i,0,data[i:i+16]) for i in range(0,len(data),16)]
    parts.append(rec(0,1,b''))
    return '\n'.join(parts)+'\n'

def read_image(path:pathlib.Path)->dict[int,int]:
    if path.suffix.lower() in ('.hex','.eep'):
        return parse_hex(path)
    return dict(enumerate(path.read_bytes()))

def integer(x:str)->int:return int(x,0)

def discover():
    try:import usb.core
    except ImportError as e:raise Block64Error('Install PyUSB: python -m pip install pyusb') from e
    device=usb.core.find(idVendor=VID,idProduct=PID)
    if device is None:raise Block64Error('MH-Tiny88 not found (connect while bootloader is active)')
    return device

def main(argv=None)->int:
    p=argparse.ArgumentParser(description='Experimental ATtiny88 Micronucleus Block64 v3.3 fixed GET_STATUS(8) host')
    subs=p.add_subparsers(dest='cmd',required=True)
    subs.add_parser('info')
    subs.add_parser('status')
    for name in ('flash-read','eeprom-read'):
        a=subs.add_parser(name)
        a.add_argument('path',type=pathlib.Path)
        a.add_argument('--start',type=integer,default=0)
        a.add_argument('--length',type=integer)
    for name in ('flash-write','eeprom-write'):
        a=subs.add_parser(name)
        a.add_argument('path',type=pathlib.Path)
        a.add_argument('--verify',action=argparse.BooleanOptionalAction,default=True)
    a=subs.add_parser('flash-erase-page')
    a.add_argument('address',type=integer)
    a.add_argument('--verify',action='store_true')
    a=subs.add_parser('flash-program-page')
    a.add_argument('address',type=integer)
    a.add_argument('path',type=pathlib.Path,help='Raw file containing exactly 64 bytes')
    a.add_argument('--verify',action=argparse.BooleanOptionalAction,default=True)
    a=subs.add_parser('flash-upload')
    a.add_argument('path',type=pathlib.Path)
    a.add_argument('--run',action='store_true')
    a.add_argument('--full-erase',action=argparse.BooleanOptionalAction,default=True)
    a.add_argument('--verify',action=argparse.BooleanOptionalAction,default=True)
    subs.add_parser('run')
    args=p.parse_args(argv)
    tool=Programmer(discover());inf=tool.connect()
    if args.cmd=='info':
        print(f'ATtiny88: Block64 v{inf.version>>8}.{inf.version&255}, boot @ 0x{inf.boot_start:04X}, app {inf.app_size} B, Flash page {inf.page_size} B, EEPROM {inf.eeprom_size} B; status={inf.status}, state={inf.state}')
    elif args.cmd=='status':
        print(f'Status: {tool.status()}')
    elif args.cmd in ('flash-read','eeprom-read'):
        kind=FLASH if args.cmd=='flash-read' else EEPROM
        maxlen=inf.app_size if kind==FLASH else inf.eeprom_size
        size=(maxlen-args.start if args.length is None else args.length)
        data=tool.read(kind,args.start,size)
        if args.path.suffix.lower() in ('.hex','.eep'):args.path.write_text(dump_hex(data,args.start))
        else:args.path.write_bytes(data)
        print(f'Read {len(data)} bytes from {"Flash" if kind==FLASH else "EEPROM"}')
    elif args.cmd in ('flash-write','eeprom-write'):
        kind=FLASH if args.cmd=='flash-write' else EEPROM
        image=read_image(args.path)
        if image:
            keys=sorted(image);addresses=[]; groups=[]; start=prev=keys[0];data=bytearray([image[start]])
            for k in keys[1:]:
                if k!=prev+1:
                    groups.append((start,bytes(data)))
                    start=k;data=bytearray()
                data.append(image[k]);prev=k
            groups.append((start,bytes(data)))
            for addr,chunk in groups:tool.write(kind,addr,chunk,verify=args.verify)
        print(f'Wrote {len(image)} bytes to {"Flash" if kind==FLASH else "EEPROM"}')
    elif args.cmd=='flash-erase-page':
        tool.erase_page(args.address,verify=args.verify)
        print(f'Erased page at 0x{args.address:04X}')
    elif args.cmd=='flash-program-page':
        raw=args.path.read_bytes()
        tool.write_page(args.address,raw,verify=args.verify)
        print(f'Programmed 64 bytes at 0x{args.address:04X} (ERASE_PAGE required first)')
    elif args.cmd=='flash-upload':
        tool.upload(read_image(args.path),full_erase=args.full_erase,verify=args.verify,run=args.run)
        print('Image programmed with protected boot reset vector and application postscript.')
    elif args.cmd=='run':tool.run()
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (Block64Error,OSError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        sys.exit(2)
