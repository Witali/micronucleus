# Micronucleus+ ATtiny88 v2.8 (experimental)

EEPROM and Flash read requests extend Micronucleus 2.x. Original v2.x requests 0,1,2,3,4 retain their semantics. All extended operations use USB vendor IN bmRequestType=0xC0 and EP0; the ISP opcode values A0/C0/F0 are *borrowed*, not the SPI wire protocol.

GET_INFO bRequest=0: bytes 0-1 report **user app programmable bytes**, excluding the reserved reset postscript (BOOT_AT-4), byte6 advertises 0x40 (EEPROM) and 0x80 (Flash Read), version bcdDevice=2.8. Byte 6 also retains MCUSR bit 0x20. With EEPROM and Flash capability this is 0xE0.

EEPROM read: bRequest 0xA0, wValue address (0-63), wLength 1, returns byte (bad address/busy -> zero-length response).
EEPROM write: bRequest 0xC0, wValue address, wIndex low byte payload, high byte zero, wLength 1, returns status 0 accepted, 1 busy, 2 invalid. No USB data OUT stage.
EEPROM ready: bRequest 0xF0, wValue=wIndex=0, wLength 1, returns 0 ready, 1 busy.

Flash read: bRequest 0xB0, wValue byte address, wIndex=0, wLength=1..8, returns raw flash bytes. Request must be within 0..(BOOT_AT-4), and address+requested count <= APP_LIMIT; otherwise returns zero-length data. Does not read bootloader or postscript. The physical reset vector in Flash[0] is patched by Micronucleus; this operation is a raw image dump, not a ready-to-upload original firmware.

Only old GET_INFO/Flash upload commands supported by the stock Micronucleus CLI. The new host utility detects capability flags before any read/write.
