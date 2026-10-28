#!/usr/bin/env python3
"""Experimental ATtiny88 Pass35 TX state guard, USB vendor Flash-only protocol v4.1.

Host-owned geometry, complete page planning, fixed-address READ8/WRITE2,
explicit page commit and readback. Never writes without explicit consent.
The PHY is NOT validated on a physical board; flash programming requires ISP.
"""
from __future__ import annotations
import argparse
import math
from pathlib import Path
import time
try:
    from . import image_core as core
except ImportError:
    import image_core as core

USB_VID, USB_PID = 0x16D0, 0x0753
USB_PROFILES = {
    0x0450: ('Pass35 ACK TX-state guard / no LED', 0x1BC0, 1032),
    0x0451: ('Pass35 ACK TX-state guard / LED active-high', 0x1BC0, 1052),
    0x0452: ('Pass35 ACK TX-state guard / LED active-low', 0x1BC0, 1050),
}
FLASH_BYTES = 8192
PAGE_BYTES = 64
WORD_BYTES = 2
READ_BYTES = 8
POSTSCRIPT_BYTES = 4
REQ_SELECT = 1
REQ_SELECT_ERASE = 2
REQ_WRITE2 = 3
REQ_RUN = 4
REQ_COMMIT_PAGE = 5
REQ_READ8 = 0xB0
DEFAULT_FLASH_DELAY_MS = 7.0  # established host policy; v4.1 has no board timing admission

pack_application = core.pack_application
parse_intel_hex = core.parse_intel_hex
image_from_file = core.image_from_file
image_to_hex = core.image_to_hex

class USBTransport:
    """Device selection is descriptor-only. Never accept an old incompatible ID."""
    def __init__(self, dev):
        if (int(dev.idVendor),int(dev.idProduct)) != (USB_VID,USB_PID):
            raise ValueError('Unexpected USB VID/PID; no vendor commands sent')
        version = int(dev.bcdDevice)
        if version not in USB_PROFILES:
            raise ValueError(f'Unknown or incompatible bootloader bcdDevice={version:#06x}; no vendor commands sent')
        self.dev = dev
        self.bcd_device = version
        self.profile,self.boot_at,self.code_bytes = USB_PROFILES[version]
        self.app_bytes = self.boot_at-POSTSCRIPT_BYTES
        self._selected_page: int|None = None
        self._erased_page: int|None = None
        self._pending_words: set[int] = set()

    def _invalidate_page(self):
        """Forget all staging assumptions after an ambiguous USB transaction."""
        self._selected_page=None
        self._erased_page=None
        self._pending_words.clear()

    def _out(self,opcode:int,value:int=0,index:int=0):
        return self.dev.ctrl_transfer(0x40,opcode,value,index,[],timeout=5000)

    def _check_page(self,address:int):
        if not 0<=address<self.boot_at or address%PAGE_BYTES:
            raise ValueError(f'Flash page {address:#x} is unaligned or overlaps bootloader')

    def select_page(self,address:int,*,erase:bool=False):
        # A new selection abandons the old local plan, even if validation or
        # the USB request fails. COMMIT must never fall back to an old page.
        self._invalidate_page()
        self._check_page(address)
        self._out(REQ_SELECT_ERASE if erase else REQ_SELECT,0,address)
        self._selected_page=address
        self._erased_page=address if erase else None

    def erase_page(self,address:int):
        self.select_page(address,erase=True)

    def write2(self,address:int,data:bytes):
        if len(data)!=WORD_BYTES:
            raise ValueError('WRITE2 requires exactly two bytes')
        if self._selected_page is None:
            raise ValueError('WRITE2 requires a selected page')
        if not 0<=address<self.boot_at or address%2 or address//PAGE_BYTES != self._selected_page//PAGE_BYTES:
            raise ValueError('WRITE2 target is not a word-aligned address in the selected application page')
        try:
            # Sending a fixed address makes duplicate SETUP/WRITE2 idempotent
            # at the page buffer's word-slot level. CRC16 input is still NOT checked.
            self._out(REQ_WRITE2,int.from_bytes(data,'little'),address)
        except Exception:
            # An ambiguous result is never silently advanced or committed.
            self._invalidate_page()
            raise
        self._pending_words.add(address)

    def commit_page(self):
        page=self._selected_page
        if page is None or len(self._pending_words)!=PAGE_BYTES//WORD_BYTES:
            raise ValueError('COMMIT needs an explicitly selected, fully staged 64-byte page')
        if self._pending_words != set(range(page,page+PAGE_BYTES,WORD_BYTES)):
            raise ValueError('Page does not contain all 32 word addresses')
        try:
            self._out(REQ_COMMIT_PAGE)
        finally:
            self._invalidate_page()

    def read8(self,address:int,*,raw_flash:bool=False):
        limit=FLASH_BYTES if raw_flash else self.app_bytes
        if address%2 or address<0 or address+READ_BYTES>limit:
            raise ValueError('READ8 address unaligned or exceeds permitted range')
        try:
            result=bytes(self.dev.ctrl_transfer(0xC0,REQ_READ8,0,address,READ_BYTES,timeout=5000))
            if len(result)!=READ_BYTES:
                raise IOError(f'Short READ8 from {address:#06x}, expected eight bytes')
        except Exception:
            self._invalidate_page()
            raise
        return result

    def read8_firmware(self,address:int):
        return self.read8(address,raw_flash=True)

    def run(self):
        # Even if the response is lost, RUN may already have left the loader.
        try:
            self._out(REQ_RUN)
        finally:
            self._invalidate_page()


def verify_page(t:USBTransport,position:int,data:bytes):
    if len(data)!=PAGE_BYTES or position%PAGE_BYTES or not 0<=position<t.boot_at:
        raise ValueError('Invalid page verification')
    actual=b''.join(t.read8_firmware(position+i) for i in range(0,64,8))
    if actual!=data:
        raise IOError(f'Flash mismatch at page {position:#06x}')


def verify_erased(t:USBTransport,page:int):
    verify_page(t,page,bytes([0xFF])*PAGE_BYTES)


def program_application(t:USBTransport,patched:core.PatchedImage,*,delay:float=DEFAULT_FLASH_DELAY_MS/1000):
    """Conservative offline-tested programming sequence; does not auto-retry errors.

    Erase old postscript first. Every word uses absolute wIndex. If COMMIT's
    control transfer fails, readback can establish whether commit completed;
    otherwise fail closed. Do not reissue COMMIT blindly.
    """
    if len(patched.image)!=t.boot_at:
        raise ValueError('Patched application geometry does not match USB descriptor')
    if not math.isfinite(delay) or delay<=0:
        raise ValueError('Flash wait must be positive and finite')
    pages=[(a,patched.image[a:a+PAGE_BYTES]) for a in range(0,t.boot_at,PAGE_BYTES)]
    last_page=t.boot_at-PAGE_BYTES
    t.erase_page(last_page)
    time.sleep(delay)
    verify_erased(t,last_page)
    for address,data in pages:
        if address!=last_page:
            t.erase_page(address)
            time.sleep(delay)
            verify_erased(t,address)
        else:
            # Postscript page has already been erased. SELECT clears temporary
            # page buffer without an extra erase cycle.
            t.select_page(address,erase=False)
        for j in range(0,PAGE_BYTES,2):
            t.write2(address+j,data[j:j+2])
        try:
            t.commit_page()
        except Exception as exc:
            time.sleep(delay)
            # A lost USB ACK does not establish a failed Flash commit; use
            # readback after quiet time, but never issue COMMIT twice.
            try:
                verify_page(t,address,data)
            except Exception:
                raise IOError(f'Indeterminate Flash commit at {address:#06x}; reflash from erase (ISP recovery may be needed)') from exc
        else:
            time.sleep(delay)
            verify_page(t,address,data)
    return True


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('application',nargs='?',type=Path,help='Original (unpatched) .bin or .hex')
    ap.add_argument('--out',type=Path,help='Prepare patched full application Intel HEX offline')
    ap.add_argument('--boot-at',type=lambda v:int(v,0),default=0x1C00,help='Offline-only geometry; hardware always uses bcdDevice')
    ap.add_argument('--identify',action='store_true',help='Only read USB device descriptor identity')
    ap.add_argument('--execute',action='store_true',help='Program connected board (experimental)')
    ap.add_argument('--i-have-isp-recovery',action='store_true',help='Acknowledge ISP and backup availability')
    ap.add_argument('--accept-untested-usb',action='store_true',help='Acknowledge hardware/CRC5/OUT ACK limitations')
    ap.add_argument('--run',action='store_true',help='Run application after successful programming (requires --execute)')
    ap.add_argument('--flash-delay-ms',type=float,default=DEFAULT_FLASH_DELAY_MS)
    args=ap.parse_args(argv)
    if not args.application and not args.identify:
        ap.error('An application is required except for --identify')
    if args.execute and not (args.i_have_isp_recovery and args.accept_untested_usb):
        ap.error('--execute needs BOTH --i-have-isp-recovery and --accept-untested-usb')
    if args.execute and not args.application:
        ap.error('--execute needs application HEX/BIN')
    if args.run and not args.execute:
        ap.error('--run requires --execute')
    if not math.isfinite(args.flash_delay_ms) or args.flash_delay_ms<=0:
        ap.error('--flash-delay-ms must be positive and finite')
    transport=None
    if args.identify or args.execute:
        try:
            import usb.core
        except ImportError as e:
            raise SystemExit('PyUSB and libusb are required for device access') from e
        device=usb.core.find(idVendor=USB_VID,idProduct=USB_PID)
        if device is None:raise SystemExit('No matching USB device')
        transport=USBTransport(device)
        print(f'{transport.profile}; bcdDevice=0x{transport.bcd_device:04x}; BOOT_AT=0x{transport.boot_at:04x}')
    if not args.application:return
    boot_at=transport.boot_at if transport is not None else args.boot_at
    prepared=pack_application(image_from_file(args.application),boot_at=boot_at)
    if args.out:
        args.out.write_text(image_to_hex(prepared.image),encoding='ascii')
        print('Saved prepared image',args.out)
    if args.execute:
        program_application(transport,prepared,delay=args.flash_delay_ms/1000)
        print('Verified all Flash pages including postscript')
        if args.run:transport.run()
    elif not args.out:
        print('Offline image prepared; no USB traffic or flash writes sent')

if __name__=='__main__':main()
