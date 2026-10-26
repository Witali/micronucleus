#!/usr/bin/env python3
"""Micronucleus ATtiny88 Block64 USB control-transfer programmer, protocol v3.0.

UNTESTED ON REAL HARDWARE. Requires PyUSB/libusb when talking to a board.
The code does not use the legacy Micronucleus 2.x host write format.

All memory commands are USB vendor control transfers:
  IN   0x10 READ; wValue=byte address, wIndex=0 Flash or 1 EEPROM,
                  wLength=1..64, result is binary memory data.
  OUT  0x11 WRITE; wValue=byte address, wIndex=memory, DATA OUT 1..64 bytes.
  IN   0x12 STATUS; returns 0 OK, 1 busy, 2 bad address, 3 error.
  OUT  0x13 RUN; zero DATA length, status stage finishes before entering app.
  IN   0x20 INFO; 8-byte Micronucleus info layout (v3.0 descriptor).

USB low-speed EP0 still sends <=8 bytes per physical DATA packet.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
import pathlib
import sys
from typing import Protocol

VID=0x16D0;PID=0x0753
REQ_READ=0x10;REQ_WRITE=0x11;REQ_STATUS=0x12;REQ_RUN=0x13;REQ_INFO=0x20
IN_VENDOR=0xC0;OUT_VENDOR=0x40
FLASH=0;EEPROM=1
FLASH_TOTAL=8192;EEPROM_TOTAL=64;FLASH_PAGE=64;MAX_CHUNK=64
BOOT_FEATURE_V3=0x01

class Block64Error(RuntimeError):pass

@dataclass(frozen=True)
class Info:
    app_size:int
    page_size:int
    eeprom_size:int
    boot_start:int
    version:int
    features:int
    signature:tuple[int,int,int]

    @property
    def flash_rw_end(self)->int:
        return self.app_size+4 # four-byte reset-vector postscript

class USBDevice(Protocol):
    bcdDevice:int
    def ctrl_transfer(self,request_type:int,request:int,value:int,index:int,data_or_wlength,timeout:int=...):...

class Programmer:
    def __init__(self,dev:USBDevice,timeout_ms:int=6000):
        self.dev=dev
        self.timeout_ms=timeout_ms
        self.info:Info|None=None

    def _ctrl(self,request_type:int,request:int,addr:int=0,memtype:int=0,data=0):
        try:
            return self.dev.ctrl_transfer(request_type,request,addr,memtype,data,timeout=self.timeout_ms)
        except Exception as e:
            raise Block64Error(f'USB request 0x{request:02X} (address {addr:#06x}) failed: {e}') from e

    def connect(self)->Info:
        version=int(getattr(self.dev,'bcdDevice',0))
        if version!=0x0300:
            raise Block64Error(f'Expected Block64 firmware bcdDevice=0x0300, got 0x{version:04X}')
        head=bytes(self._ctrl(IN_VENDOR,REQ_INFO,data=8))
        if len(head)!=8:
            raise Block64Error(f'INFO length {len(head)} instead of 8')
        appsz=(head[0]<<8)|head[1]
        pagesz=head[2]
        feature=head[6]
        if pagesz!=FLASH_PAGE or appsz<2048 or appsz>=FLASH_TOTAL or (appsz+4)%64:
            raise Block64Error(f'Unexpected Flash geometry app={appsz}, page={pagesz}')
        if head[4:6]!=bytes((0x93,0x11)):
            raise Block64Error(f'Not an ATtiny88: 1E-{head[4]:02X}-{head[5]:02X}')
        if not feature&BOOT_FEATURE_V3:
            raise Block64Error('Block64 v3.0 feature bit missing')
        self.info=Info(appsz,pagesz,EEPROM_TOTAL,appsz+4,version,feature,(0x1E,head[4],head[5]))
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
        result=bytes(self._ctrl(IN_VENDOR,REQ_STATUS,data=1))
        if len(result)!=1 or result[0] not in (0,1,2,3):
            raise Block64Error(f'Invalid status reply {result.hex()}')
        return result[0]

    def write(self,kind:int,start:int,data:bytes,verify:bool=True):
        if not data:return
        self._require(kind,start,len(data))
        offset=0
        while offset<len(data):
            addr=start+offset
            size=min(MAX_CHUNK,len(data)-offset)
            if kind==FLASH:
                size=min(size,FLASH_PAGE-(addr%FLASH_PAGE))
            part=bytes(data[offset:offset+size]);assert len(part)==size
            sent=self._ctrl(OUT_VENDOR,REQ_WRITE,addr,kind,part)
            if isinstance(sent,int) and sent!=len(part):
                raise Block64Error(f'WRITE 0x{addr:04X}: sent {sent}, expected {len(part)}')
            code=self.status()
            if code!=0:
                raise Block64Error(f'MCU failed write 0x{addr:04X}: status={code}')
            if verify:
                observed=self.read(kind,addr,size)
                expected=part
                if kind==FLASH and addr<2:
                    # The firmware forces the reset vector to its own start.
                    bootjmp=(0xc000|(((self.info.boot_start//2)-1)&0x0fff)).to_bytes(2,'little')
                    i=max(0,addr);j=min(2,addr+size)
                    expected=bytearray(part)
                    expected[i-addr:j-addr]=bootjmp[i:j]
                if observed!=expected:
                    raise Block64Error(f'Verification failed at 0x{addr:04X}: wrote {expected.hex()}, read {observed.hex()}')
            offset+=size

    def run(self):
        result=self._ctrl(OUT_VENDOR,REQ_RUN,data=b'')
        if isinstance(result,int) and result!=0: raise Block64Error('RUN returned unexpected transfer length')

    def upload(self,patches:dict[int,int],full_erase:bool=True,verify:bool=True,run:bool=False):
        """Upload an application that begins with an AVR RJMP reset vector.

        Firmware v3.0 retains the original Micronucleus boot-at-reset scheme:
        first Flash word points to loader; final application Flash page has a
        four-byte postscript with an RJMP to the app's original RESET target.
        The postscript is invalidated before page 0 and only restored last.
        """
        if self.info is None:raise Block64Error('Connect first')
        app_size=self.info.app_size
        if not patches or (0 not in patches or 1 not in patches):
            raise Block64Error('Image must include the two bytes of its RJMP RESET vector')
        if any(a<0 or a>=app_size or not 0<=v<=255 for a,v in patches.items()):
            raise Block64Error('Image contains data in reserved postscript/bootloader space')
        orig=patches[0]|patches[1]<<8
        if orig&0xF000!=0xC000:
            raise Block64Error(f'Expected RJMP in RESET vector, got 0x{orig:04X}; convert/relocate before upload')
        app=bytearray(b'\xff'*self.info.boot_start)
        for addr,value in patches.items():app[addr]=value
        target_word=((orig&0x0fff)+1)&0x0fff
        rjmp_boot=0xc000 | (((self.info.boot_start//2)-1)&0x0fff)
        app[0:2]=rjmp_boot.to_bytes(2,'little')
        post_start=app_size
        off=(target_word - (post_start//2+1))&0x0fff
        post_jump=0xc000|off
        app[post_start:post_start+4]=post_jump.to_bytes(2,'little')+b'\xff\xff'

        final_page=self.info.boot_start-FLASH_PAGE
        # First invalidate existing application postscript (prevents booting
        # incomplete application after a brownout while programming).
        self.write(FLASH,post_start,b'\xff'*4,verify=verify)
        if full_erase:
            page_starts=range(0,final_page,FLASH_PAGE)
        else:
            page_starts=sorted({a&~63 for a in patches}|{0})
            page_starts=(p for p in page_starts if p!=final_page)
        for base in page_starts:
            self.write(FLASH,base,app[base:base+FLASH_PAGE],verify=verify)
        # Last page includes application tail plus the postscript, thus must
        # always be written AFTER all other pages.
        self.write(FLASH,final_page,app[final_page:self.info.boot_start],verify=verify)
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
    p=argparse.ArgumentParser(description='Experimental ATtiny88 Micronucleus Block64 v3.0 host')
    subs=p.add_subparsers(dest='cmd',required=True)
    subs.add_parser('info')
    for name in ('flash-read','eeprom-read'):
        a=subs.add_parser(name)
        a.add_argument('path',type=pathlib.Path)
        a.add_argument('--start',type=integer,default=0)
        a.add_argument('--length',type=integer)
    for name in ('flash-write','eeprom-write'):
        a=subs.add_parser(name)
        a.add_argument('path',type=pathlib.Path)
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
        print(f'ATtiny88: Block64 v{inf.version>>8}.{inf.version&255}, boot @ 0x{inf.boot_start:04X}, app {inf.app_size} B, Flash page {inf.page_size} B, EEPROM {inf.eeprom_size} B')
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
