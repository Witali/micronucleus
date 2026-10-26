#!/usr/bin/env python3
"""Apply Pass10 GET_STATUS consolidation to Pass9 source. Safe to re-run on baseline only."""
from pathlib import Path
src=Path(__file__).resolve().parents[1]/'source/micronucleus_t88_block64.S'
s=src.read_text()

def replace(old,new):
 global s
 if s.count(old)!=1:raise RuntimeError(f'Expected exactly one occurrence, got {s.count(old)}: {old[:130]!r}')
 s=s.replace(old,new)
replace('#define OP_INFO 0x20\n','')
replace('/* Micronucleus device-info and USB descriptors in program memory. */\n    .byte ((BOOT_AT - 4) >> 8), ((BOOT_AT - 4) & 0xff), 0x40, 0x05, 0x93, 0x11, 0xe3, 0x00  /* device config: user flash, page, write delay, signature */',
'''/* Six-byte constant tail for extended GET_STATUS (status/state are dynamic).
 * The last two bytes retain the ATtiny88 signature for offline identification.
 * SRAM reply layout: [result, state, app_hi, app_lo, page, eeprom, proto, features]. */
    .byte ((BOOT_AT - 4) >> 8), ((BOOT_AT - 4) & 0xff), 0x40, 0x40, 0x32, 0x03, 0x93, 0x11''')
replace('0x53, 0x07, 0x01, 0x03', '0x53, 0x07, 0x02, 0x03')
replace(' * Vendor IN:  READ=0x10, STATUS=0x12, INFO=0x20.',
''' * Vendor IN: READ=0x10, GET_STATUS=0x12 (wLength=1 or 8).
 * GET_STATUS(1): result code. GET_STATUS(8): result, state,
 *     app capacity MSB/LSB, page bytes, EEPROM bytes, protocol 0x32, features.
 * The fixed tail is stored with the descriptors in Flash; result/state
 * are populated in the existing 8-byte endpoint-zero payload in SRAM.''')
replace('''block_vendor_in:
    cpi     r25, OP_INFO
    breq    block_info
    cpi     r25, OP_STATUS
    breq    block_status''','''block_vendor_in:
    cpi     r25, OP_STATUS
    breq    block_status''')
replace('''block_info:
    ldi     r18, ((BOOT_AT + 2) & 0xff)
    ldi     r19, ((BOOT_AT + 2) >> 8)
    ldi     r24, 8
    rjmp    L1f22

block_status:
    ldd     r18, Y+55
    std     Y+2, r18
    ldi     r24, 1
    rjmp    L1f34''','''/* Single GET_STATUS command: one-byte polling or eight-byte status+info.
 * The six immutable bytes live in program Flash at BOOT_AT+2.
 * The reply is assembled in the normal EP0 payload at 0x0102..0x0109,
 * eliminating duplicate INFO dispatch and avoiding extra RAM buffers.
 * Timing-sensitive NRZI RX/TX code is untouched. */
block_status:
    ldd     r18, Y+55                  /* last result: OK/BUSY/BOUNDS/FAIL */
    std     Y+2, r18
    ldi     r24, 1
    ldd     r20, Y+29                  /* wLength low */
    cpi     r20, 8
    brne    L1f34                     /* fast status-only reply */
    ldd     r20, Y+30                  /* wLength high must be zero */
    tst     r20
    brne    L1f34
    ldd     r18, Y+48                  /* machine state */
    std     Y+3, r18
    ldi     r30, ((BOOT_AT + 2) & 0xff)
    ldi     r31, ((BOOT_AT + 2) >> 8)
    ldi     r26, 0x04                  /* metadata goes at 0x0104..0x0109 */
    ldi     r27, 0x01
    ldi     r20, 6
block_status_copy_metadata:
    lpm     r18, Z+
    st      X+, r18
    dec     r20
    brne    block_status_copy_metadata
    ldi     r24, 8
    rjmp    L1f34''')
src.write_text(s)
print('Updated source',src)
