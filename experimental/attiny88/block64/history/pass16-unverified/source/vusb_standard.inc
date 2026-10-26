/* USB standard requests and descriptors. Included at original location. */
old_vendor_dispatch:
    ldd     r18, Y+25
    std     Y+2, r1
    cpse    r25, r1
    rjmp    L1f2c
    std     Y+3, r1
    ldi     r24, 0x02                        /* USB reply: number of bytes */
L1f34:
    ldi     r18, 0x0a                        /* repeated 16-bit pointer low */
    ldi     r19, 0x81                        /* prepared EP0 buffer marker */
L1f22:
    std     Y+17, r19                       /* send pointer high */
    std     Y+16, r18                       /* send pointer low */
    rjmp    L1de2

L1f2c:
    cpi     r25, 0x05
    brbc    1, L1f3a
    std     Y+19, r18
    rjmp    L1f34                           /* preserve fallthrough semantics */

L1f3a:
    cpi     r25, 0x06
    brbc    1, L1f62
    ldd     r24, Y+26
    ldi     r18, ((BOOT_AT + 0x1a) & 0xff)
    cpi     r24, 0x01
    breq    desc_ptr
    cpi     r24, 0x02
    brne    L1f70
    ldi     r18, ((BOOT_AT + 0x08) & 0xff)

desc_ptr:
    /* Both descriptors are in the same 256-byte Flash window. */
    ldi     r19, ((BOOT_AT + 0x08) >> 8)
    ldi     r24, 0x12
    rjmp    L1f22

L1f62:
    cpi     r25, 0x08
    brbs    1, L1f7a
    cpi     r25, 0x09
    brbc    1, L1f70
    std     Y+21, r18
    rjmp    L1f34

L1f70:
    ldi     r24, 0x01
    cpi     r25, 0x0a
    brbs    1, L1f34
    ldi     r24, 0x00
    rjmp    L1f34

L1f7a:
    ldd     r18, Y+21
    std     Y+2, r18
    ldi     r24, 0x01

main_tail:
    rjmp    L1f34

L1f82:
    /* Removed 0x1f82: sbi     0xb, 0 (size-optimized, see CHANGES.md) */
    /* Removed 0x1f84: rjmp    L1e84 (size-optimized, see CHANGES.md) */


