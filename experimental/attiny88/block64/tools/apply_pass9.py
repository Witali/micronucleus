#!/usr/bin/env python3
"""Apply conservative size optimizations to the Pass 8 snapshot.
Each transformation has an exact source guard; fail if base changes.
The low-level USB_handler and usb_crc16_append are left untouched.
"""
from pathlib import Path
import difflib
root=Path(__file__).resolve().parent.parent
p=root/'source/micronucleus_t88_block64.S'
s=p.read_text()
base=s
changes=[]
def change(old,new,label,exact=1):
 global s
 hits=s.count(old)
 assert hits==exact,(label,hits)
 s=s.replace(old,new)
 changes.append((label,len(old),len(new)))

change('    brne    L1eca\n', '    brne    L1f70\n', 'Resolve missing standard-descriptor jump target')
change('''    clr     r17
    std     Y+56, r17
''','''    std     Y+56, r1
''','Use zero register for MEM_PROGRESS initialization')
change('''    ldi     r18, RESULT_OK
    std     Y+55, r18
''','''    std     Y+55, r1
''','Use zero register for successful result')
change('''    cp      r24, r16
    brne    block_out_return
    cp      r25, r17
    brne    block_out_return
''','''    cp      r24, r16
    cpc     r25, r17  /* combine 16-bit equality with propagated Z */
    brne    block_out_return
''','Compare CRC as a single 16-bit equality')
change('''    tst     r16
    breq    block_validate_flash
    tst     r19
    brne    block_invalid_range
    cpi     r18, 65
    brsh    block_invalid_range
    rjmp    block_valid_range
block_validate_flash:
    ldi     r20, (BOOT_AT & 0xff)
    ldi     r21, (BOOT_AT >> 8)
    cp      r20, r18
    cpc     r21, r19
    brcs    block_invalid_range
''','''    /* Select one 16-bit exclusive bound: EEPROM=64, Flash=BOOT_AT. */
    ldi     r20, 64
    ldi     r21, 0
    tst     r16
    brne    block_check_selected_bound
    ldi     r20, (BOOT_AT & 0xff)
    ldi     r21, (BOOT_AT >> 8)
block_check_selected_bound:
    cp      r20, r18
    cpc     r21, r19
    brcs    block_invalid_range
''','Unify Flash and EEPROM length+address bound comparisons')
p.write_text(s)
(root/'PASS9_CHANGES.diff').write_text(''.join(difflib.unified_diff(base.splitlines(True),s.splitlines(True),fromfile='Pass8/micronucleus_t88_block64.S',tofile='Pass9/micronucleus_t88_block64.S')))
print('\n'.join(x[0] for x in changes))
