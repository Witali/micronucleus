/* Micronucleus ATtiny88 16 MHz ASM + EEPROM + bounded Flash read.
 * BASED ON Optimized Micronucleus t88_default 16 MHz ATtiny88 bootloader, pass 3.
 * Assembler reconstruction of public Micronucleus firmware with conservative code-size
 * SRAM pointer reuse in V-USB with cycle-neutral sync-stage initialization.
 * RX/TX sampler and sender timings preserved by cycle tests; CRC-16 unchanged.
 * Source uses historical mnemonic labels; numeric names do NOT encode relocated addresses.
 * Original Micronucleus contributors and modifications: GPL-2.0-or-later.
 */
#ifndef BOOT_AT
#define BOOT_AT 0x1ac0
#endif
#if ((BOOT_AT - 3) & 0xff) < 8
#error Optimized Flash range check assumes boundary low-byte >= 8
#endif
#if ((BOOT_AT + 0x0a) >> 8) != ((BOOT_AT + 0x1c) >> 8)
#error USB descriptor pointers cross a 256-byte page; adjust optimized dispatcher
#endif
.section .text
/* Edit BOOT_AT only after the build audits that the loader fits in flash. */
.org BOOT_AT
.global bootloader_start
bootloader_start:
    rjmp startup
/* Micronucleus device-info and USB descriptors in program memory. */
    .byte ((BOOT_AT - 4) >> 8), ((BOOT_AT - 4) & 0xff), 0x40, 0x05, 0x93, 0x11, 0xe0, 0x00  /* device config: user flash, page, write delay, signature */
    .byte 0x09, 0x02, 0x12, 0x00, 0x01, 0x01, 0x00, 0x80  /* 1a4a */
    .byte 0x32, 0x09, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00  /* 1a52 */
    .byte 0x00, 0x00, 0x12, 0x01, 0x10, 0x01, 0xff, 0x00  /* 1a5a */
    .byte 0x00, 0x08, 0xd0, 0x16, 0x53, 0x07, 0x08, 0x02  /* 1a62 */
    .byte 0x00, 0x00, 0x00, 0x01  /* 1a6a */

startup:
    eor     r1, r1
    out     0x3f, r1
    ldi     r28, 0xff
    ldi     r29, 0x02
    out     0x3d, r28
    out     0x3e, r29
    /* Removed 0x1a7a: ldi     r18, 0x01 (size-optimized, see CHANGES.md) */
    ldi     r26, 0x00
    ldi     r27, 0x01
    /* Removed 0x1a80: rjmp    L1a84 (size-optimized, see CHANGES.md) */

L1a82:
    st      X+, r1

L1a84:
    cpi     r26, 0x2c
    /* Removed 0x1a86: cpc     r27, r18 (size-optimized, see CHANGES.md) */
    brbc    1, L1a82
    rjmp    main

usb_crc16_append:
    movw    r26, r24
    ldi     r24, 0x00
    ldi     r25, 0x00
    ldi     r20, 0x01
    ldi     r21, 0xa0
    com     r22
    ldi     r19, 0x00
    rjmp    L1aae

L1a9c:
    ld      r18, X+
    eor     r24, r18

L1aa0:
    ror     r25
    ror     r24
    brbs    0, L1aaa
    eor     r24, r20
    eor     r25, r21

L1aaa:
    subi    r19, 0xe0
    brbs    0, L1aa0

L1aae:
    subi    r22, 0xff
    brbs    0, L1a9c
    st      X+, r24
    st      X+, r25
    ret

USB_handler:
    push    r28
    push    r29
    eor     r28, r28

L1abe:
    inc     r28
    sbis    0x9, 1
    brbc    1, L1abe

L1ac4:
    sbis    0x9, 1
    rjmp    L1ade
    sbis    0x9, 1
    rjmp    L1ade
    sbis    0x9, 1
    rjmp    L1ade
    sbis    0x9, 1
    rjmp    L1ade
    sbis    0x9, 1
    rjmp    L1ade
    sbis    0x9, 1
    rjmp    L1ade
    rjmp    L1bf0

L1ade:
    push    r0
    lds     r28, 0x010e
    eor     r29, r29
    subi    r28, 0xea
    sbci    r29, 0xfe
    pop     r0
    ldi     r22, 0x55
    sbis    0x9, 1
    rjmp    L1af8
    push    r0
    pop     r0
    rjmp    L1ac4

L1af8:
    /* Cycle-neutral substitution at sync sampling stage.
       Former PUSH R16 (2) + POP R16 (2) were an inert 4-cycle delay.
       Now set Z=0x0100 (1+1) and RJMP-to-next (2): still 4 cycles.
       The saved register and stack depth remain unchanged; SREG unchanged.
       All subsequent USB bit sample and output timestamps remain identical. */
    ldi     r30, 0x00
    ldi     r31, 0x01
    rjmp    usb_rx_delay_complete
usb_rx_delay_complete:
    push    r16
    ldi     r18, 0x00
    ldi     r20, 0x10
    pop     r16
    in      r16, 0x9
    andi    r16, 0x06
    bst     r16, 1
    bld     r18, 7
    push    r19
    ldi     r21, 0x00
    ldi     r19, 0x0b
    rjmp    L1b86

L1b14:
    andi    r17, 0x06
    ori     r20, 0x40
    andi    r18, 0x7f
    mov     r16, r17
    subi    r21, 0xff
    rjmp    L1b5c

L1b20:
    ori     r20, 0x80
    in      r17, 0x9
    andi    r17, 0x06
    andi    r18, 0x7f
    subi    r21, 0x02
    rjmp    L1b6a

L1b2c:
    ori     r20, 0x40
    in      r16, 0x9
    andi    r18, 0x7f
    andi    r16, 0x06
    brbs    1, L1baa
    subi    r21, 0xff
    rjmp    L1b3a

L1b3a:
    rjmp    L1b82

L1b3c:
    ori     r20, 0x20
    in      r17, 0x9
    andi    r18, 0x7f
    andi    r17, 0x06
    brbs    1, L1baa
    subi    r21, 0xff
    rjmp    L1b4a

L1b4a:
    rjmp    L1b96

L1b4c:
    andi    r16, 0x06
    eor     r17, r16
    subi    r21, 0x01
    brbc    2, L1b58
    subi    r21, 0xfd
    nop

L1b58:
    subi    r17, 0x01
    ror     r18

L1b5c:
    cpi     r18, 0xfc
    in      r17, 0x9
    brbc    0, L1b14
    andi    r17, 0x06
    eor     r16, r17
    subi    r16, 0x01
    ror     r18

L1b6a:
    cpi     r18, 0xfc
    brbc    0, L1b20
    eor     r20, r18
    st      Y+, r20

L1b72:
    in      r16, 0x9
    andi    r16, 0x06
    eor     r17, r16
    andi    r20, 0x3f
    subi    r17, 0x01
    ror     r18
    cpi     r18, 0xfc
    brbc    0, L1b2c

L1b82:
    lsr     r20
    lsr     r20

L1b86:
    in      r17, 0x9
    andi    r17, 0x06
    brbs    1, L1baa
    eor     r16, r17
    subi    r16, 0x01
    ror     r18
    cpi     r18, 0xfc
    brbc    0, L1b3c

L1b96:
    subi    r22, 0xab
    brbs    0, L1b72
    subi    r19, 0x01
    in      r16, 0x9
    brbc    0, L1b4c
    rjmp    L1ba2

L1ba2:
    ldi     r17, 0x04
    out     0x1b, r17

L1ba6:
    eor     r16, r16
    rjmp    L1be4

L1baa:
    subi    r19, 0x0b
    neg     r19
    sub     r28, r19
    sbci    r29, 0x00
    ldi     r17, 0x04
    out     0x1b, r17
    /* Z already initialized without added latency in L1af8. */
    ldd     r16, Y+0
    cpi     r16, 0xc3
    brbs    1, L1bf6
    cpi     r16, 0x4b
    brbs    1, L1bf6
    ldd     r18, Z+12
    ldd     r17, Y+1
    add     r17, r17
    cpse    r17, r18
    rjmp    L1ba6
    cpi     r16, 0x69
    brbs    1, L1c14
    cpi     r16, 0x2d
    brbs    1, L1bd8
    cpi     r16, 0xe1
    brbc    1, L1ba6

L1bd8:
    ldi     r28, 0x0a

L1bda:
    in      r17, 0x1b
    sbrc    r17, 2
    rjmp    L1be4
    dec     r28
    brbc    1, L1bda

L1be4:
    sts     0x0114, r16

L1be8:
    pop     r19
    in      r28, 0x1b
    sbrc    r28, 2
    rjmp    L1abe

L1bf0:
    pop     r29
    pop     r28
    ret

L1bf6:
    ldd     r18, Z+20
    and     r18, r18
    brbs    1, L1be8
    ldd     r17, Z+18
    and     r17, r17
    brbc    1, L1c48
    cpi     r19, 0x04
    brbs    2, L1c4c
    std     Z+18, r19
    std     Z+13, r18
    rjmp    L1c4c

L1c14:
    ldd     r16, Z+18
    cpi     r16, 0x01
    brbc    4, L1c48
    ldi     r16, 0x5a
    ldd     r19, Z+15
    sbrc    r19, 4
    rjmp    L1c4e
    std     Z+15, r16
    ldi     r28, 0x01
    ldi     r29, 0x01
    rjmp    L1c56

L1c30:
    eor     r16, r21
    ldi     r17, 0x00
    rjmp    L1c36

L1c36:
    nop
    out     0xb, r16
    rjmp    L1c70

L1c3c:
    eor     r16, r21
    ldi     r17, 0x00
    adc     r18, r18
    rjmp    L1c7e

L1c44:
    ldi     r17, 0x00
    rjmp    L1c8a

L1c48:
    ldi     r20, 0x5a
    rjmp    L1c50

L1c4c:
    ldi     r19, 0xd2

L1c4e:
    mov     r20, r19

L1c50:
    ldi     r28, 0x14
    ldi     r29, 0x00
    ldi     r19, 0x02

L1c56:
    in      r17, 0xa
    ori     r17, 0x06
    sbi     0xb, 1
    in      r16, 0xb
    out     0xa, r17
    ldi     r21, 0x06
    ldi     r18, 0x80

L1c64:
    ldi     r22, 0x35

L1c66:
    sbrs    r18, 0
    eor     r16, r21
    out     0xb, r16
    ror     r18
    ror     r17

L1c70:
    cpi     r17, 0xfc
    brbc    0, L1c30
    lsr     r22
    brbc    0, L1c66
    brbc    1, L1c66
    sbrs    r18, 0
    eor     r16, r21

L1c7e:
    out     0xb, r16
    ror     r18
    ror     r17
    cpi     r17, 0xfc
    brbc    0, L1c3c
    ror     r18

L1c8a:
    ror     r17
    sbrs    r17, 7
    eor     r16, r21
    nop
    cpi     r17, 0xfc
    out     0xb, r16
    brbc    0, L1c44
    ld      r18, Y+
    dec     r19
    brbc    1, L1c64
    andi    r16, 0xf9
    ldd     r17, Z+19
    add     r17, r17
    subi    r28, 0x16
    sbci    r29, 0x00
    out     0xb, r16
    brbs    1, L1cb2
    std     Z+12, r17

L1cb2:
    ldi     r17, 0x04
    out     0x1b, r17
    ori     r16, 0x02
    in      r17, 0xa
    andi    r17, 0xf9
    mov     r20, r16
    andi    r20, 0xf9
    ldi     r21, 0x04

L1cc2:
    dec     r21
    brbc    1, L1cc2
    out     0xb, r16
    out     0xa, r17
    out     0xb, r20
    rjmp    L1be8

usb_program_page:
    movw    r30, r4
    sbiw    r30, 0
    brbc    1, L1cd8
    ldi     r24, ((0xc000 + (BOOT_AT / 2) - 1) & 0xff)
    ldi     r25, ((0xc000 + (BOOT_AT / 2) - 1) >> 8)

L1cd8:
    ldi     r18, 0x01
    movw    r0, r24
    out     0x37, r18     /* optimize: I/O address SPMCSR (0x57 - 0x20); 2 B vs 4 B */
    spm
    eor     r1, r1
    adiw    r30, 2  /* update page fill pointer in Z; only callers overwrite r24 after return */
    movw    r4, r30
    ret

main:
    wdr
    /* WDT unlock: WDCE|WDE=0x18 is sufficient regardless of the
       previous prescaler and interrupt settings. Next store, immediately,
       clears WDE/WDCE; timed sequence is unchanged. Saves four bytes. */
    ldi     r24, 0x18
    sts     0x0060, r24
    sts     0x0060, r1
    sbi     0xa, 1
    /* 300.94 ms initial USB disconnect: 19 x 63355 inner loops.
       Previous 3000 x 400 countdown cost 4,815,001 cycles;
       this takes 4,815,056 cycles at 16 MHz (difference 55 cycles),
       two bytes less while preserving the USB disconnect duration. */
    ldi     r18, 19

L1d02:
    ldi     r24, (63355 & 0xff)
    ldi     r25, (63355 >> 8)

L1d06:
    sbiw    r24, 1
    brne    L1d06
    dec     r18
    brne    L1d02
    cbi     0xa, 1
    ldi     r24, 0x5a
    sts     0x010f, r24
    ldi     r24, 0xff
    sts     0x0100, r24
    /* After reset both PCMSK2 and PCICR are zero.  Only PCINT18 / PCIE2
       are required: direct writes avoid redundant read-modify-write. */
    ldi     r24, 0x04
    sts     0x006d, r24
    sts     0x0068, r24
    /* Removed 0x1d30: sbi     0xa, 0 (size-optimized, see CHANGES.md) */
    mov     r7, r1
    mov     r3, r1
    mov     r5, r1
    mov     r4, r1

L1d3a:
    ldi     r28, 0xd5
    ldi     r29, 0x14
    ldi     r24, 0x64

L1d40:
    in      r25, 0x9
    andi    r25, 0x06
    brbs    1, L1d48
    ldi     r24, 0x64

L1d48:
    subi    r24, 0x01
    brbc    1, L1d54
    sts     0x0113, r1
    sts     0x010c, r1

L1d54:
    sbis    0x1b, 2
    rjmp    L1e98
    rcall   USB_handler
    sbi     0x1b, 2  /* PCIFR.PCIF2 W1C; reset PCMSK0/1/3 stay zero.
                        SBI is 2 cycles vs LDI+OUT 2 cycles. */

L1d5e:
    wdr
    ldi     r18, 0x02
    cpse    r3, r18
    rjmp    L1d7e
    ldi     r30, (BOOT_AT & 0xff)
    ldi     r31, (BOOT_AT >> 8)

L1d6a:
    subi    r30, 0x40
    sbc     r31, r1
    ldi     r24, 0x03
    out     0x37, r24     /* optimize: I/O address SPMCSR (0x57 - 0x20); 2 B vs 4 B */
    spm
    sbiw    r30, 0
    brbc    1, L1d6a
    movw    r4, r30 /* erase-loop exit implies Z=0, so R4:R5=0 */

L1d7e:
    mov     r24, r3
    cpi     r24, 0x40
    breq    L1d86
    /* Fold command==4 and application-idle exit dispatch into the
       previous fallthrough. Both conditional targets are now nearby;
       the long-path RJMP trampoline is unnecessary. */
    cpi     r24, 0x04
    brne    L1d9a
    or      r28, r29
    brne    L1d9c
    rjmp    L1eac

L1d86:
    movw    r30, r4
    sbiw    r30, 2
#if (BOOT_AT & 0xff) == 0
    cpi     r31, (BOOT_AT >> 8)    /* lower byte of boot boundary is 0: high compare sufficient for carry */
#else
    cpi     r30, (BOOT_AT & 0xff)
    ldi     r24, (BOOT_AT >> 8)
    cpc     r31, r24
#endif
    brbc    0, L1d9a
    andi    r30, 0xc0   /* AUDIT FIX: zero SPM Page Write PCWORD bits, 64-byte Flash page */
    ldi     r24, 0x05
    out     0x37, r24     /* optimize: I/O address SPMCSR (0x57 - 0x20); 2 B vs 4 B */
    spm

L1d9a:
    mov     r3, r1

L1d9c:
    /* Y=0x0100 is a base pointer for usbdrv SRAM globals during command/packet handling. */
    ldi     r28, 0x00
    ldi     r29, 0x01
    ldd     r24, Y+18
    subi    r24, 0x03
    brmi    L1dfc  /* N from SUBI equals previous r24 bit 7; same predicate */
    ldd     r25, Y+13
    cpi     r25, 0x2d
    brbc    1, L1df8
    cpi     r24, 0x08
    brbc    1, L1df8
    ldi     r24, 0xc3
    std     Y+1, r24
    ldi     r24, 0x5a
    std     Y+15, r24
    ldd     r24, Y+23
    andi    r24, 0x60
    ldd     r25, Y+24
    /* redundant AND r24,r24 removed: ANDI r24,0x60 already set same Z/N/V/S; LDD does not touch SREG */
    brbc    1, L1dce
    rjmp    L1f0c

L1dce:
    mov     r7, r1
    cpse    r25, r1
    rjmp    L1ec0
    ldi     r24, ((BOOT_AT + 2) & 0xff)
    ldi     r25, ((BOOT_AT + 2) >> 8)
    std     Y+17, r25
    std     Y+16, r24
    ldi     r24, 0x08

L1de2:
    ldd     r25, Y+30
    cpse    r25, r1
    rjmp    L1df4
    ldd     r25, Y+29
    cp      r25, r24
    brbc    0, L1df4
    mov     r24, r25

L1df4:
    std     Y+0, r24

L1df8:
    std     Y+18, r1

L1dfc:
    ldd     r24, Y+15
    sbrs    r24, 4
    rjmp    L1e64
    ldd     r24, Y+0
    cpi     r24, 0xff
    brbs    1, L1e64
    mov     r23, r24
    cpi     r24, 0x09
    brbs    0, L1e14
    ldi     r23, 0x08

L1e14:
    mov     r25, r24
    sub     r25, r23
    std     Y+0, r25
    ldd     r25, Y+1
    ldi     r18, 0x88
    eor     r25, r18
    std     Y+1, r25
    and     r24, r24
    brbs    1, L1e4c
    ldd     r30, Y+16
    ldd     r31, Y+17
    ldi     r26, 0x02
    ldi     r27, 0x01
    mov     r24, r23

L1e3a:
    lpm     r25, Z+  /* same read and advance; LPM Rd,Z+ supported on tiny88 */
    st      X+, r25
    subi    r24, 0x01
    brbc    1, L1e3a
    std     Y+17, r31
    std     Y+16, r30

L1e4c:
    mov     r22, r23
    ldi     r24, 0x02
    ldi     r25, 0x01
    rcall   usb_crc16_append
    subi    r23, 0xfc
    cpi     r23, 0x0c
    brbs    1, L1e60
    ldi     r24, 0xff
    std     Y+0, r24

L1e60:
    std     Y+15, r23

L1e64:
    movw    r24, r6
    adiw    r24, 1
    movw    r6, r24
    /* r24:r25 is a disposable copy of r6:r7 here. SUBI/SBCI
       reproduce CPI/CPC zero flag exactly (including Z propagation). */
    subi    r24, 0xb0
    sbci    r25, 0x04
    brbc    1, L1e7c
    ldi     r30, ((BOOT_AT - 3) & 0xff)
    ldi     r31, ((BOOT_AT - 3) >> 8)
    lpm     r30, Z
    cpi     r30, 0xff
    brbc    1, L1eac

L1e7c:
    /* Removed 0x1e7c: andi    r24, 0x4c (size-optimized, see CHANGES.md) */
    /* Removed 0x1e7e: brbc    1, L1e82 (size-optimized, see CHANGES.md) */
    /* Removed 0x1e80: rjmp    L1f82 (size-optimized, see CHANGES.md) */

L1e82:
    /* Removed 0x1e82: cbi     0xb, 0 (size-optimized, see CHANGES.md) */

L1e84:
    sbis    0x1b, 2
    rjmp    L1d3a
    ldi     r24, 0x1c

L1e8a:
    sbis    0x9, 1
    ldi     r24, 0x1c
    subi    r24, 0x01
    brbc    1, L1e8a
    sbi     0x1b, 2  /* PCIFR.PCIF2 W1C; reset PCMSK0/1/3 stay zero.
                        SBI is 2 cycles vs LDI+OUT 2 cycles. */
    rjmp    L1d3a

L1e98:
    sbiw    r28, 1
    brbs    1, L1e9e
    rjmp    L1d40

L1e9e:
    rjmp    L1d5e

L1eac:
    /* Removed 0x1eac: cbi     0xb, 0 (size-optimized, see CHANGES.md) */
    out     0xa, r1
    sts     0x0068, r1
    sts     0x006d, r1
    in      r24, 0x34
    out     0x1e, r24
    out     0x34, r1
app_jump:
    .word (0xc000 | (((bootloader_start - 4 - app_jump - 2)/2) & 0x0fff)) /* relative RJMP into application postscript */

L1ec0:
    cpi     r25, 0x01
    brbc    1, L1ee2
    cp      r4, r1
    cpc     r5, r1
    brbs    1, L1eca

L1ece:
    ldd     r24, Y+27
    andi    r24, 0xc0
    mov     r4, r24
    ldd     r5, Y+28
    ldi     r24, 0x11
    out     0x37, r24
    spm


L1eca:
    ldi     r24, 0x00
    rjmp    L1de2

L1ee2:
    cpi     r25, 0x03
    brbc    1, L1f06
    ldd     r24, Y+25
    ldd     r25, Y+26
    rcall   usb_program_page
    ldd     r24, Y+27
    ldd     r25, Y+28
    rcall   usb_program_page
    mov     r24, r4
    andi    r24, 0x3f
    brbc    1, L1eca
    ldi     r25, 0x40
    mov     r3, r25
    rjmp    L1de2

L1f06:
    andi    r25, 0x3f
    mov     r3, r25
    rjmp    L1eca

L1f0c:
    /* Vendor IN (bmRequestType=0xC0) EEPROM + Flash read extension.
       0xA0 EEPROM read byte, 0xB0 FLASH read 1..8 byte, 0xC0 EEPROM write, 0xF0 RDY/BSY.
       Feature bits in GET_INFO[6] 0x40 for EEPROM and 0x80 for Flash Read.
       Request fields: wValue = EEPROM address, wIndex low = data (write).
       USB protocol extends (NOT replaces) original ISP SPI opcode semantics.
       All new commands return 1 byte via EP0 control-IN; WRITE returns status.
       Non-EEPROM requests retain old Micronucleus dispatch unchanged. */
    ldd     r24, Y+23
    cpi     r24, 0xc0
    brne    old_vendor_dispatch
    cpi     r25, 0xa0
    breq    ee_read

ee_check_flash:
    cpi     r25, 0xb0
    brne    ee_check_write
    rjmp    flash_read

ee_check_write:
    cpi     r25, 0xc0
    breq    ee_write

ee_check_busy:
    cpi     r25, 0xf0
    breq    ee_ready

old_vendor_dispatch:
    ldd     r18, Y+25
    std     Y+10, r1
    cpse    r25, r1
    rjmp    L1f2c
    std     Y+11, r1
    ldi     r24, 0x02                        /* USB reply: number of bytes */
L1f34:
    ldi     r18, 0x0a                        /* repeated 16-bit pointer low */
    ldi     r19, 0x01                        /* repeated 16-bit pointer high */
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
    ldi     r18, ((BOOT_AT + 0x1c) & 0xff)
    cpi     r24, 0x01
    breq    desc_ptr
    cpi     r24, 0x02
    brne    L1eca
    ldi     r18, ((BOOT_AT + 0x0a) & 0xff)

desc_ptr:
    /* Both descriptors are in the same 256-byte Flash window. */
    ldi     r19, ((BOOT_AT + 0x0a) >> 8)
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
    ldi     r18, 0x15
    ldi     r19, 0x01
    ldi     r24, 0x01

main_tail:
    rjmp    L1f22

L1f82:
    /* Removed 0x1f82: sbi     0xb, 0 (size-optimized, see CHANGES.md) */
    /* Removed 0x1f84: rjmp    L1e84 (size-optimized, see CHANGES.md) */

/* ---------------- EEPROM operations (ATtiny88: 64 bytes) -----------------
 * EEPROM registers (I/O addresses): EECR=0x1F, EEDR=0x20, EEARL=0x21.
 * Only 64 bytes exist, so EEARH is not used. Reject any high address bits.
 * New control operations are deliberately outside the bit-bang USB RX/TX.
 * For all new operations the host sends bmRequestType=0xC0 (vendor, IN).
 * Writes return status: 0=accepted, 1=EEPROM/SPM busy, 2=invalid address.
 * EEPROM is not modified on unsupported or invalid requests.
 */

/* 0xF0 readiness. Reuse exact busy-status code for EEPE=1. */
ee_ready:
    /* ATtiny88 halts the CPU while SPM page erase/write is active;
       only EEPE can be busy when a USB SETUP is processed. */
    ldi     r18, 0
    sbic    0x1f, 1
    ldi     r18, 1
    rjmp    ee_return_one

/* 0xA0 read EEPROM address. wIndex ignored (as SPI dummy field).
   If EEPROM busy, zero-length reply; host should poll 0xF0. */
ee_read:
    rcall   ee_validate_addr
    brcc    ee_empty
    sbic    0x1f, 1
    rjmp    ee_empty
    out     0x21, r16
    sbi     0x1f, 0
    in      r18, 0x20
    rjmp    ee_return_one

ee_empty:
    rjmp    L1eca      /* zero length, no EEPROM access */

/* 0xC0 write EEPROM address with data=wIndex[7:0].
   Return status 0=accepted, 1=busy, 2=bad address/parameters.
   EEPROM write starts asynchronously; host polls 0xF0 then reads 0xA0.
   EEMPE->EEPE must be within 4 CPU cycles; consecutive SBI=2 cycles.
   As in Microchip datasheet, EECR is reset to programming mode 00
   (erase+write) BEFORE the timed sequence. */
ee_write:
    rcall   ee_validate_addr
    brcc    ee_bad_addr
    /* Reject high wIndex byte and an unfinished Flash page buffer:
       ATtiny88 datasheet warns EEPROM writing during SPM page fill
       destroys staged Flash data. Both nonzero conditions return 2. */
    ldd     r19, Y+28
    mov     r18, r4
    andi    r18, 0x3f
    or      r19, r18
    brne    ee_bad_addr
    sbic    0x1f, 1      /* EEPROM write active? */
    rjmp    ee_busy
    /* On ATtiny88 a Flash Page Erase/Write SPM stalls the CPU until
       the operation completes. Page-buffer operations clear SELFPRGEN
       before another USB SETUP can be processed. Hence reaching this
       handler already implies SPM cannot be in progress. */
    ldd     r19, Y+27   /* data byte */
    out     0x21, r16   /* EEARL, address 0..63 */
    out     0x20, r19   /* EEDR */
    out     0x1f, r1    /* EECR=0: erase/write, no EERIE */
    sbi     0x1f, 2    /* EEMPE = 1; 2 clocks */
    sbi     0x1f, 1    /* EEPE = 1; next instruction, within 4 clocks */
    clr     r18         /* accepted */
    rjmp    ee_return_one

ee_bad_addr:
    ldi     r18, 0x02
    rjmp    ee_return_one

ee_busy:
    ldi     r18, 0x01
    /* Fall through to common 1-byte response. */

/* Shared 1-byte USB response buffer at SRAM 0x010A, reused by legacy
   Micronucleus vendor responses. Fall through to common setup-response code. */
ee_return_one:
    std     Y+10, r18
    ldi     r24, 1
    rjmp    L1f34

/* ---------------- Read user application Flash ---------------------------
 * Request 0xB0 vendor IN; wValue=byte address, wIndex=0, wLength=1..8.
 * No new buffer: set normal usbMsgPtr to requested Flash address and hand
 * off to Micronucleus' existing descriptor-data sender, L1de2.
 * Critical low-level USB bit timing is untouched.
 * Security/safety: never disclose bootloader or postscript; check the
 * *entire* requested range, including 16-bit addition overflow.
 * This routine handles small control transfers; longer host dumps split into
 * eight-byte requests; application reset vector remains patched in raw dump.
 */
flash_read:
    /* Require wIndex==0 and high byte of wLength==0. Combine all
       reserved-byte checks into one OR / branch. */
    ldd     r18, Y+27
    ldd     r19, Y+28
    or      r18, r19
    ldd     r19, Y+30
    or      r18, r19
    brne    ee_empty
    ldd     r24, Y+29            /* wLength low, reply length */
    tst     r24
    breq    ee_empty
    cpi     r24, 9
    brsh    ee_empty            /* reject length > 8 */
    ldd     r18, Y+25            /* wValue low - start address */
    ldd     r19, Y+26            /* wValue high */
    /* All byte counts are 1..8. Since APP_LIMIT ends at >=0x07,
       addresses below its high-byte window cannot exceed the bound. */
    cpi     r19, ((BOOT_AT - 3) >> 8)
    brlo    flash_valid
    brne    ee_empty
    /* start+length <= APP_LIMIT, checked without 8-bit overflow. */
    ldi     r30, ((BOOT_AT - 4) & 0xff)
    sub     r30, r24
    cp      r30, r18
    brlo    ee_empty
flash_valid:
    /* Reuse two pointer stores in L1f22. The extra RJMP consumes two
       cycles outside the low-level USB sampling/transmit path. */
    rjmp    L1f22

/* Common validation, returns carry=1 on valid, carry=0 on invalid.
   Read wValue 16bit from Y+25/26, and reject >63 (non-wrapping).
   OUT: r16=EEARL (0..63). r18 altered. Does not write EEPROM. */
ee_validate_addr:
    /* 16-bit compare wValue (Y+26:Y+25) < 0x0040.
       CPC with R1=0 propagates low-byte borrow into high byte.
       C=1 means valid (< 0x0040).
       Callers use BRCC for invalid, replacing their earlier BRCS. */
    ldd     r16, Y+25
    cpi     r16, 0x40
    ldd     r18, Y+26
    cpc     r18, r1
    ret

