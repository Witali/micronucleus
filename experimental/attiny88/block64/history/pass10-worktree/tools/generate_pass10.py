#!/usr/bin/env python3
"""Generate SRAM-overlay GET_STATUS v3.2 from original Pass9 sources."""
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
base=Path('/mnt/data/Micronucleus_ATtiny88_Block64_Optimization_Pass9_2026-10-26')
s=(base/'source/micronucleus_t88_block64.S').read_text()
repls={
 '#define OP_INFO 0x20\n':'',
 '#define MEM_STATE 0x0130':'#define MEM_STATE 0x0139',
 '#define MEM_TYPE 0x0131':'#define MEM_TYPE 0x0130',
 '#define MEM_ADDR_LO 0x0132':'#define MEM_ADDR_LO 0x0131',
 '#define MEM_ADDR_HI 0x0133':'#define MEM_ADDR_HI 0x0132',
 '#define MEM_REMAIN 0x0134':'#define MEM_REMAIN 0x0133',
 '#define MEM_INDEX 0x0135':'#define MEM_INDEX 0x0134',
 '#define MEM_TOTAL 0x0136':'#define MEM_TOTAL 0x0135',
 '#define MEM_STATUS 0x0137':'#define MEM_STATUS 0x0138',
 '#define MEM_PROGRESS 0x0138':'#define MEM_PROGRESS 0x0136',
 '#define MEM_EXPECT_PID 0x0139':'#define MEM_EXPECT_PID 0x0137',
 '    .byte ((BOOT_AT - 4) >> 8), ((BOOT_AT - 4) & 0xff), 0x40, 0x05, 0x93, 0x11, 0xe3, 0x00  /* device config: user flash, page, write delay, signature */':
 '    .byte ((BOOT_AT - 4) >> 8), ((BOOT_AT - 4) & 0xff), 0x40, 0x40, 0x32, 0x03, 0x93, 0x11  /* GET_STATUS metadata; status/state are live SRAM bytes */',
 '0x53, 0x07, 0x01, 0x03':'0x53, 0x07, 0x02, 0x03',
 ' * Vendor IN:  READ=0x10, STATUS=0x12, INFO=0x20.':
 ' * Vendor IN: READ=0x10, GET_STATUS=0x12 (1 or 8 bytes, no 0x20 INFO).',
 '''block_vendor_in:
    cpi     r25, OP_INFO
    breq    block_info
    cpi     r25, OP_STATUS
    breq    block_status''':
 '''block_vendor_in:
    cpi     r25, OP_STATUS
    breq    block_status''',
 '''block_info:
    ldi     r18, ((BOOT_AT + 2) & 0xff)
    ldi     r19, ((BOOT_AT + 2) >> 8)
    ldi     r24, 8
    rjmp    L1f22

block_status:
    ldd     r18, Y+55
    std     Y+2, r18
    ldi     r24, 1
    rjmp    L1f34''':
 '''/* Live SRAM response overlay at 0x0138:
 * [last_result, state, app_hi, app_lo, page_bytes, eeprom_bytes,
 *  protocol_minor (0x32), feature_flags (0x03)].
 * The six constant bytes are initialized exactly once after reset.
 * GET_STATUS length 1 (polling) or length 8 (full metadata); the generic
 * non-bit-timed endpoint-zero SRAM sender handles both with no copy here. */
block_status:
    ldi     r18, 0x38
    ldi     r19, 0x81            /* SRAM pointer marker: 0x0138 */
    ldi     r24, 8
    ldd     r20, Y+29           /* host-requested low-byte length */
    cpi     r20, 8
    breq    block_status_length_ready
    ldi     r24, 1
block_status_length_ready:
    rjmp    L1f22''',
}
for old,new in repls.items():
 if s.count(old)!=1:raise RuntimeError(f'{s.count(old)} matches for {old[:90]}')
 s=s.replace(old,new)
# Remap ONLY operand occurrences Y+48 through Y+57 (stable SRAM-overlay).
mp={48:57,49:48,50:49,51:50,52:51,53:52,54:53,55:56,56:54,57:55}
s=re.sub(r'\bY\+(4[89]|5[0-7])\b',lambda m:'Y+'+str(mp[int(m.group(1))]),s)
# Startup in legacy clears 0x0100..0x0139. Immediately initialize constants
# 0x013A..0x013F with the 6-byte existing Flash metadata prefix.
old='''    cpi     r26, 0x3a
    /* Removed 0x1a86: cpc     r27, r18 (size-optimized, see CHANGES.md) */
    brbc    1, L1a82
    rjmp    main'''
new='''    cpi     r26, 0x3a
    /* SRAM 0x0100..0x0139 is cleared, including both live status bytes. */
    brbc    1, L1a82
    /* X == 0x013A; preload constant tail once, not on every status poll. */
    ldi     r30, ((BOOT_AT + 2) & 0xff)
    ldi     r31, ((BOOT_AT + 2) >> 8)
    ldi     r20, 6
block_init_status_tail:
    lpm     r18, Z+
    st      X+, r18
    dec     r20
    brne    block_init_status_tail
    rjmp    main'''
if s.count(old)!=1:raise RuntimeError('startup missing')
s=s.replace(old,new)
s=s.replace('/* State values are intentionally clustered for short busy checks:',
'''/* Live status response at SRAM 0x0138..0x013F: MEM_STATUS, MEM_STATE,
   then six immutable fields initialized from Flash BOOT_AT+2.\n
/* State values are intentionally clustered for short busy checks:''')
(root/'source/micronucleus_t88_block64.S').write_text(s)
print('Generated',root/'source/micronucleus_t88_block64.S')
