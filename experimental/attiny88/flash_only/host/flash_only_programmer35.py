#!/usr/bin/env python3
"""Experimental ATtiny88 Flash-only protocol v4.2: cursor READ8/WRITE4.

SELECT owns a common cursor. Each WRITE4 fills two new buffer words; the last
chunk automatically programs its 64-byte page. A USB ambiguity stops the plan.
"""
from __future__ import annotations
import argparse
import math
from pathlib import Path
import time
try:
    from . import image_core as core
    from .profiles import BOOT_AT, USB_PROFILES
except ImportError:
    import image_core as core
    from profiles import BOOT_AT, USB_PROFILES

USB_VID, USB_PID = 0x16D0, 0x0753
FLASH_BYTES, PAGE_BYTES, WORD_BYTES = 8192,64,2
READ_BYTES, WRITE_BYTES, POSTSCRIPT_BYTES = 8,4,4
REQ_SELECT, REQ_SELECT_ERASE, REQ_WRITE4, REQ_RUN, REQ_READ8 = 1,2,3,4,0xB0
DEFAULT_FLASH_DELAY_MS = 7.0

pack_application = core.pack_application
parse_intel_hex = core.parse_intel_hex
image_from_file = core.image_from_file
image_to_hex = core.image_to_hex


class USBTransport:
    """Descriptor-selected protocol and a fail-closed host cursor/page plan."""
    def __init__(self,dev):
        if (int(dev.idVendor),int(dev.idProduct))!=(USB_VID,USB_PID):
            raise ValueError('Unexpected USB VID/PID; no vendor commands sent')
        version=int(dev.bcdDevice)
        if version not in USB_PROFILES:
            raise ValueError(f'Unknown or incompatible bootloader bcdDevice={version:#06x}; no vendor commands sent')
        self.dev=dev
        self.bcd_device=version
        self.profile,self.boot_at,self.code_bytes=USB_PROFILES[version]
        self.app_bytes=self.boot_at-POSTSCRIPT_BYTES
        self.flash_delay=DEFAULT_FLASH_DELAY_MS/1000
        self._valid=True
        self._cursor:int|None=None
        self._staged_page:int|None=None
        self._staged_bytes=0
        self._write_stream=False
        self._verified_erased_pages:set[int]=set()
        self._needs_wait=False

    @property
    def cursor(self):
        return self._cursor

    def _require_plan(self):
        if not self._valid:
            raise ValueError('USB result was ambiguous; reconnect and start a new erase/verification plan')

    def _invalidate_page(self):
        """An unknown completion invalidates the cursor, buffer and erase proof."""
        self._valid=False
        self._cursor=None
        self._staged_page=None
        self._staged_bytes=0
        self._write_stream=False
        self._verified_erased_pages.clear()

    def wait_ready(self):
        """Apply the configured quiet interval once after erase/automatic write."""
        self._require_plan()
        if self._needs_wait:
            time.sleep(self.flash_delay)
            self._needs_wait=False

    def _out(self,opcode:int,value:int=0,index:int=0):
        self.wait_ready()
        result=self.dev.ctrl_transfer(0x40,opcode,value,index,[],timeout=5000)
        if result!=0:
            raise IOError('Unexpected nonzero completion for a no-data USB command')
        return result

    def _check_page(self,address:int):
        if not isinstance(address,int) or address<0 or address%PAGE_BYTES or address+PAGE_BYTES>self.boot_at:
            raise ValueError('Flash page must be aligned and below the bootloader')

    def select(self,address:int,*,erase:bool=False):
        """Clear the device buffer and select a word-aligned common cursor."""
        self._require_plan()
        try:
            if self._staged_bytes:
                raise ValueError('Finish the staged page before selecting or reading another address')
            if not isinstance(address,int) or address<0 or address%WORD_BYTES or address>=FLASH_BYTES:
                raise ValueError('SELECT needs a word-aligned Flash address')
            if erase:self._check_page(address)
            self._out(REQ_SELECT_ERASE if erase else REQ_SELECT,0,address)
        except Exception:
            self._invalidate_page()
            raise
        self._cursor=address
        self._staged_page=None
        self._staged_bytes=0
        self._write_stream=address%PAGE_BYTES==0
        if erase:
            self._verified_erased_pages.discard(address)
            self._needs_wait=True

    def select_page(self,address:int,*,erase:bool=False):
        try:self._check_page(address)
        except Exception:
            self._invalidate_page()
            raise
        self.select(address,erase=erase)

    def erase_page(self,address:int):
        self.select_page(address,erase=True)

    def write4(self,data:bytes):
        """Load two fresh words; never retry this operation after USB ambiguity."""
        self._require_plan()
        if not isinstance(data,(bytes,bytearray,memoryview)):
            raise ValueError('WRITE4 needs a four-byte payload')
        data=bytes(data)
        if len(data)!=WRITE_BYTES:
            raise ValueError('WRITE4 requires exactly four bytes')
        address=self._cursor
        if address is None or not self._write_stream:
            raise ValueError('WRITE4 requires a fresh page-aligned SELECT, without intervening reads')
        page=address-address%PAGE_BYTES
        if address%WRITE_BYTES or address<0 or address+WRITE_BYTES>self.boot_at:
            raise ValueError('WRITE4 cursor is unaligned or overlaps bootloader')
        if not self._staged_bytes:
            if address!=page or page not in self._verified_erased_pages:
                raise ValueError('WRITE4 needs a complete page plan and verified erased Flash')
            self._staged_page=page
        if page!=self._staged_page or address!=page+self._staged_bytes:
            raise ValueError('WRITE4 cursor does not match the staged page')
        try:
            self._out(REQ_WRITE4,int.from_bytes(data[:2],'little'),int.from_bytes(data[2:],'little'))
        except Exception:
            self._invalidate_page()
            raise
        self._cursor=address+WRITE_BYTES
        self._staged_bytes+=WRITE_BYTES
        if self._staged_bytes==PAGE_BYTES:
            self._staged_bytes=0
            self._staged_page=None
            self._verified_erased_pages.discard(page)
            self._needs_wait=True

    def read8(self,length:int=READ_BYTES,*,raw_flash:bool=False):
        """Read at the current cursor, advancing only after complete success."""
        self._require_plan()
        if self._staged_bytes:
            raise ValueError('READ cannot interleave an incompletely staged write page')
        limit=FLASH_BYTES if raw_flash else self.app_bytes
        address=self._cursor
        if address is None or not isinstance(length,int) or not 1<=length<=READ_BYTES or address<0 or address+length>limit:
            raise ValueError('READ8 cursor/count exceeds the permitted Flash range')
        try:
            self.wait_ready()
            result=bytes(self.dev.ctrl_transfer(0xC0,REQ_READ8,0,0,length,timeout=5000))
            if len(result)!=length:
                raise IOError(f'Short READ8 at {address:#06x}: expected {length}, received {len(result)}')
        except Exception:
            self._invalidate_page()
            raise
        self._cursor=address+len(result)
        self._write_stream=False
        self._staged_page=None
        return result

    def read_memory(self,address:int,length:int,*,raw_flash:bool=False):
        self._require_plan()
        if self._staged_bytes:
            raise ValueError('READ cannot interleave an incompletely staged write page')
        limit=FLASH_BYTES if raw_flash else self.app_bytes
        if not isinstance(address,int) or not isinstance(length,int) or address<0 or address%WORD_BYTES or length<0 or address+length>limit:
            raise ValueError('Invalid sequential Flash read range')
        if not length:return b''
        if self._cursor!=address:self.select(address)
        output=bytearray()
        while len(output)<length:
            output.extend(self.read8(min(READ_BYTES,length-len(output)),raw_flash=raw_flash))
        return bytes(output)

    def run(self):
        self._require_plan()
        if self._staged_bytes:
            raise ValueError('RUN cannot abandon an incompletely staged page')
        try:self._out(REQ_RUN)
        finally:self._invalidate_page()


def verify_page(t:USBTransport,position:int,data:bytes):
    if len(data)!=PAGE_BYTES or position%PAGE_BYTES or position<0 or position+PAGE_BYTES>t.boot_at:
        raise ValueError('Invalid page verification')
    actual=t.read_memory(position,PAGE_BYTES,raw_flash=True)
    if actual!=data:
        t._invalidate_page()
        raise IOError(f'Flash mismatch at page {position:#06x}')
    if data==bytes([0xFF])*PAGE_BYTES:t._verified_erased_pages.add(position)


def verify_erased(t:USBTransport,page:int):
    verify_page(t,page,bytes([0xFF])*PAGE_BYTES)


def program_application(t:USBTransport,patched:core.PatchedImage,*,delay:float=DEFAULT_FLASH_DELAY_MS/1000):
    """Erase/verify, reselect, fill whole pages, wait and verify without replay."""
    if len(patched.image)!=t.boot_at:
        raise ValueError('Patched application geometry does not match USB descriptor')
    if not math.isfinite(delay) or delay<=0:
        raise ValueError('Flash wait must be positive and finite')
    t.flash_delay=delay
    pages=[(a,patched.image[a:a+PAGE_BYTES]) for a in range(0,t.boot_at,PAGE_BYTES)]
    last_page=t.boot_at-PAGE_BYTES
    # Disable the old postscript first, then keep that page erased until last.
    t.erase_page(last_page)
    t.wait_ready()
    verify_erased(t,last_page)
    for address,data in pages:
        if address!=last_page:
            t.erase_page(address)
            t.wait_ready()
            verify_erased(t,address)
        # Erase verification advanced the common cursor; every write phase
        # begins with a fresh SELECT and an empty once-per-word page buffer.
        t.select_page(address)
        for offset in range(0,PAGE_BYTES,WRITE_BYTES):
            t.write4(data[offset:offset+WRITE_BYTES])
        t.wait_ready()
        verify_page(t,address,data)
    # Later pages may have corrupted an earlier one despite local readback.
    for address,data in pages:verify_page(t,address,data)
    return True


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('application',nargs='?',type=Path,help='Original (unpatched) .bin or .hex')
    ap.add_argument('--out',type=Path,help='Prepare patched full application Intel HEX offline')
    ap.add_argument('--boot-at',type=lambda v:int(v,0),default=BOOT_AT,help='Offline-only geometry; hardware always uses bcdDevice')
    ap.add_argument('--identify',action='store_true',help='Only read USB device descriptor identity')
    ap.add_argument('--execute',action='store_true',help='Program connected board (experimental)')
    ap.add_argument('--i-have-isp-recovery',action='store_true',help='Acknowledge ISP and backup availability')
    ap.add_argument('--accept-untested-usb',action='store_true',help='Acknowledge missing hardware admission and incoming DATA CRC16 validation')
    ap.add_argument('--run',action='store_true',help='Run application after successful programming (requires --execute)')
    ap.add_argument('--flash-delay-ms',type=float,default=DEFAULT_FLASH_DELAY_MS)
    args=ap.parse_args(argv)
    if not args.application and not args.identify:ap.error('An application is required except for --identify')
    if args.execute and not (args.i_have_isp_recovery and args.accept_untested_usb):
        ap.error('--execute needs BOTH --i-have-isp-recovery and --accept-untested-usb')
    if args.execute and not args.application:ap.error('--execute needs application HEX/BIN')
    if args.run and not args.execute:ap.error('--run requires --execute')
    if not math.isfinite(args.flash_delay_ms) or args.flash_delay_ms<=0:ap.error('--flash-delay-ms must be positive and finite')
    transport=None
    if args.identify or args.execute:
        try:import usb.core
        except ImportError as error:raise SystemExit('PyUSB and libusb are required for device access') from error
        device=usb.core.find(idVendor=USB_VID,idProduct=USB_PID)
        if device is None:raise SystemExit('No matching USB device')
        transport=USBTransport(device)
        print(f'{transport.profile}; bcdDevice=0x{transport.bcd_device:04x}; BOOT_AT=0x{transport.boot_at:04x}')
    if not args.application:return
    prepared=pack_application(image_from_file(args.application),boot_at=transport.boot_at if transport else args.boot_at)
    if args.out:
        args.out.write_text(image_to_hex(prepared.image),encoding='ascii')
        print('Saved prepared image',args.out)
    if args.execute:
        program_application(transport,prepared,delay=args.flash_delay_ms/1000)
        print('Verified all Flash pages including postscript')
        if args.run:transport.run()
    elif not args.out:print('Offline image prepared; no USB traffic or flash writes sent')


if __name__=='__main__':main()
