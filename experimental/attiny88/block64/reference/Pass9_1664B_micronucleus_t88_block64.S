/* Micronucleus ATtiny88 16 MHz Block64 v3.1-compatible Reset-only Pass8 ASM.
 * BASED ON Optimized Micronucleus t88_default 16 MHz ATtiny88 bootloader, pass 3.
 * Assembler reconstruction of public Micronucleus firmware with conservative code-size
 * SRAM pointer reuse in V-USB with cycle-neutral sync-stage initialization.
 * RX/TX sampler and sender timings preserved by cycle tests; CRC-16 unchanged.
 * Source uses historical mnemonic labels; numeric names do NOT encode relocated addresses.
 * The normal AVR interrupt vector table is fully application-owned except RESET.
 * Page 0 updates erase the entire 64-byte page; only the rewritten RESET word
 * is forcibly redirected to Micronucleus. This is SOFTWARE protection, not
 * a power-failure-safe or hardware-locked RESET word.
 * Original Micronucleus contributors and modifications: GPL-2.0-or-later.
 */
#ifndef BOOT_AT
#define BOOT_AT 0x1980
#endif
#if ((BOOT_AT - 3) & 0xff) < 8
#error Optimized Flash range check assumes boundary low-byte >= 8
#endif
#if ((BOOT_AT + 0x0a) >> 8) != ((BOOT_AT + 0x1c) >> 8)
#error USB descriptor pointers cross a 256-byte page; adjust optimized dispatcher
#endif

/* Block64 split erase/write v3.1 (incompatible with old Micronucleus CLI). */
#define MEM_STATE 0x0130
#define MEM_TYPE 0x0131
#define MEM_ADDR_LO 0x0132
#define MEM_ADDR_HI 0x0133
#define MEM_REMAIN 0x0134
#define MEM_INDEX 0x0135
#define MEM_TOTAL 0x0136
#define MEM_STATUS 0x0137
#define MEM_PROGRESS 0x0138
#define MEM_EXPECT_PID 0x0139  /* USB DATA1 after SETUP, toggles per accepted OUT */
#define MEM_BUFFER 0x0140   /* one 64-byte SRAM page, 0x0140-0x017f */
/* State values are intentionally clustered for short busy checks:
   idle/done/error=0..2, run=3, active write phases=4..7. */
#define ST_IDLE 0
#define ST_DONE 1
#define ST_ERROR 2
#define ST_RUN 3
#define ST_RECEIVE 4
#define ST_WRITE_EEPROM 5
#define ST_FLASH_WAIT_PREP 6
#define ST_SPM_WAIT_SENT 7
/* ST_FLASH_WAIT_PREP serves both erase and write. MEM_PROGRESS distinguishes them. */
#define OP_READ 0x10
#define OP_WRITE 0x11
#define OP_STATUS 0x12
#define OP_RUN 0x13
#define OP_INFO 0x20
#define OP_ERASE_PAGE 0x14
#define MEM_FLASH 0
#define MEM_EEPROM 1
#define RESULT_OK 0
#define RESULT_BUSY 1
#define RESULT_BOUNDS 2
#define RESULT_FAIL 3
#define EP0_NAK 0x5a
#define EMPTY_MESSAGE 0xff
#define EP0_MAX_PACKET 8
#define BLOCK_MAX 64
#define RESET_RJMP (0xc000 | (((BOOT_AT/2)-1) & 0x0fff))

.section .text
/* Edit BOOT_AT only after the build audits that the loader fits in flash. */
.org BOOT_AT
.global bootloader_start
bootloader_start:
    rjmp startup
/* Micronucleus device-info and USB descriptors in program memory. */
    .byte ((BOOT_AT - 4) >> 8), ((BOOT_AT - 4) & 0xff), 0x40, 0x05, 0x93, 0x11, 0xe3, 0x00  /* device config: user flash, page, write delay, signature */
    .byte 0x09, 0x02, 0x12, 0x00, 0x01, 0x01, 0x00, 0x80  /* 1a4a */
    .byte 0x32, 0x09, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00  /* 1a52 */
    .byte 0x00, 0x00, 0x12, 0x01, 0x10, 0x01, 0xff, 0x00  /* 1a5a */
    .byte 0x00, 0x08, 0xd0, 0x16, 0x53, 0x07, 0x01, 0x03  /* 1a62 */
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
    /* 0x0100..0x0139 includes USB variables AND Block64 state.
       The original limit 0x012C left the state machine uninitialized. */
    cpi     r26, 0x3a
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
    sbi     0x1b, 2  /* 2 cycles like original LDI+OUT; PCMSK0/1/3 remain 0 */

L1ba6:
    eor     r16, r16
    rjmp    L1be4

L1baa:
    subi    r19, 0x0b
    neg     r19
    sub     r28, r19
    sbci    r29, 0x00
    sbi     0x1b, 2  /* 2 cycles like original LDI+OUT; PCMSK0/1/3 remain 0 */
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
    /* Z is guaranteed 0x0100 on every path reaching packet commit.
       STD Z+20 and STS 0x0114 each take two clocks; STD is 2 B shorter. */
    std     Z+20, r16

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
    sbi     0x1b, 2  /* 2 cycles like original LDI+OUT; PCMSK0/1/3 remain 0 */
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
    rcall   block_memory_service

/* Examine a staged USB packet; SETUP and DATA OUT have distinct handlers. */
L1d9c:
    /* Y=0x0100 from the immediately preceding block_memory_service call;
       every returning path of that routine preserves Y. */
    ldd     r24, Y+18
    subi    r24, 3
    brmi    L1dfc
    ldd     r25, Y+13
    cpi     r25, 0xe1            /* OUT token, DATA0/1 already decoded */
    breq    block_out_packet
    cpi     r25, 0x2d            /* SETUP token */
    brne    L1df8
    cpi     r24, 8
    brne    L1df8
    mov     r7, r1               /* extend inactivity timeout */
    ldi     r24, 0xc3            /* initialize DATA0, TX toggle -> DATA1 */
    std     Y+1, r24
    ldi     r24, EP0_NAK
    std     Y+15, r24
    ldi     r24, EMPTY_MESSAGE
    std     Y+0, r24             /* do not send reply until prepared */
    ldd     r24, Y+23            /* bmRequestType */
    andi    r24, 0x60
    ldd     r25, Y+24            /* bRequest */
    breq    block_standard_setup
    rjmp    block_vendor_dispatch
block_standard_setup:
    rjmp    old_vendor_dispatch

block_out_packet:
    rcall   block_accept_out
    rjmp    L1df8

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
    /* Shared SRAM/Flash TX copy setup; data-path instructions unchanged. */
    ldi     r26, 0x02
    ldi     r27, 0x01
    mov     r24, r23
    /* 0x810a denotes a prefilled 8-byte EP0 reply; skip copying. */
    sbrs    r31, 7
    rjmp    tx_copy_flash_start
    cpi     r30, 0x0a
    breq    L1e4c
    /* 0x81xx encodes a real SRAM source. Clear marker before LD. */
    andi    r31, 0x7f

tx_copy_sram_loop:
    ld      r25, Z+
    st      X+, r25
    dec     r24
    brne    tx_copy_sram_loop
    ori     r31, 0x80            /* persist SRAM marker */
    rjmp    tx_update_source_pointer

tx_copy_flash_start:
L1e3a:
    lpm     r25, Z+
    st      X+, r25
    dec     r24
    brne    L1e3a

tx_update_source_pointer:
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
    /* Only a FLASH_WAIT_PREP request needs the deferred SPM transition.
       This is the sole caller of the old 12-byte status-prepared helper. */
    ldd     r18, Y+48
    cpi     r18, ST_FLASH_WAIT_PREP
    brne    L1e64
    ldi     r18, ST_SPM_WAIT_SENT
    std     Y+48, r18

L1e64:
    movw    r24, r6
    adiw    r24, 1
    movw    r6, r24
    subi    r24, 0xb0
    sbci    r25, 0x04
    brne    L1e7c
    ldd     r18, Y+48
    cpi     r18, ST_IDLE
    brne    L1e7c
    ldi     r30, ((BOOT_AT - 3) & 0xff)
    ldi     r31, ((BOOT_AT - 3) >> 8)
    lpm     r30, Z
    cpi     r30, 0xff
    brne    L1eac

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
    /* Only an expired quiet polling interval may start a blocking SPM.
       After the host has seen the USB status stage it must pause before
       issuing another request. No code in USB_handler has been changed. */
    rcall   block_spm_after_quiet
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

/* ------------------ Unified 1..64 byte memory protocol -----------------
 * USB low-speed endpoint zero carries 8 bytes per DATA packet.
 * Control transfer wLength=1..64 uses repeated DATA0/DATA1 packets.
 * The low-level NRZI RX/TX and USB packet CRC implementation is untouched.
 * Vendor IN:  READ=0x10, STATUS=0x12, INFO=0x20.
 * Vendor OUT: WRITE=0x11, RUN=0x13.
 * wValue=16-bit byte address, wIndex=memory (0 Flash, 1 EEPROM).
 * Flash WRITE is exactly 64 bytes, aligned at 64. ERASE_PAGE is distinct.
 * Partial Flash writes are host-side read/modify/write of full pages.
 * SPM is deferred until after USB status TX and a quiet polling interval.
 * No legacy SPI or old Micronucleus vendor opcodes are accepted.
 */
block_vendor_dispatch:
    ldd     r18, Y+23         /* complete bmRequestType (IN/OUT) */
    cpi     r18, 0xc0
    breq    block_vendor_in
    cpi     r18, 0x40
    breq    block_vendor_out
    rjmp    block_reject

block_vendor_in:
    cpi     r25, OP_INFO
    breq    block_info
    cpi     r25, OP_STATUS
    breq    block_status
    cpi     r25, OP_READ
    breq    block_read_setup
    rjmp    block_reject

block_vendor_out:
    cpi     r25, OP_WRITE
    breq    block_write_setup
    cpi     r25, OP_ERASE_PAGE
    brne    block_vendor_not_erase
    rjmp    block_erase_setup
block_vendor_not_erase:
    cpi     r25, OP_RUN
    breq    block_run
    rjmp    block_reject

block_info:
    ldi     r18, ((BOOT_AT + 2) & 0xff)
    ldi     r19, ((BOOT_AT + 2) >> 8)
    ldi     r24, 8
    rjmp    L1f22

block_status:
    ldd     r18, Y+55
    std     Y+2, r18
    ldi     r24, 1
    rjmp    L1f34

block_run:
    /* Only run when EEPROM/Flash modification is fully complete. */
    ldd     r18, Y+48
    cpi     r18, ST_ERROR /* 0=IDLE, 1=DONE allow run; others reject */
    brsh    block_reject
block_run_ready:
    ldi     r18, ST_RUN
    std     Y+48, r18
    ldi     r24, 0
    rjmp    L1de2

/* Both READ and WRITE share validation. Valid 1..64 byte counts;
   Flash bound is BOOT_AT (includes 4-byte reset postscript for host);
   EEPROM bound is 64 bytes. No wraparound is permitted. */
block_read_setup:
    rcall   block_validate_range
    brcc    block_reject
block_read_range_ok:
    /* r16=memory type; r22:r23=start address; r24=request size. */
    tst     r16
    breq    block_read_flash
    sbic    0x1f, 1
    rjmp    block_reject
    /* Snapshot EEPROM to 64-byte SRAM buffer before starting DATA IN. */
    ldi     r26, 0x40
    ldi     r27, 0x01
    mov     r20, r24
    mov     r17, r22
block_snapshot_eeprom_loop:
    out     0x21, r17
    sbi     0x1f, 0
    in      r18, 0x20
    st      X+, r18
    inc     r17
    dec     r20
    brne    block_snapshot_eeprom_loop
    ldi     r18, 0x40
    ldi     r19, 0x81    /* marker: SRAM 0x0140 */
    rjmp    L1f22

block_read_flash:
    mov     r18, r22
    mov     r19, r23
    rjmp    L1f22

block_write_setup:
    rcall   block_validate_range
    brcc    block_write_bad
    /* Host must send an entire aligned Flash page, never a fragment.
       EEPROM still accepts 1..64 bytes. */
    tst     r16
    brne    block_write_validated
    mov     r17, r22
    andi    r17, 0x3f
    brne    block_write_bad
    cpi     r24, 64
    brne    block_write_bad
block_write_validated:
    rcall   block_check_idle_for_write
    brcc    block_write_bad
    ldi     r17, ST_RECEIVE
    std     Y+48, r17
    std     Y+49, r16
    std     Y+50, r22
    std     Y+51, r23
    std     Y+52, r24
    std     Y+54, r24
    std     Y+56, r1
    ldi     r17, 0x4b            /* USB DATA1 first after SETUP */
    std     Y+57, r17
    ldi     r17, RESULT_BUSY
    std     Y+55, r17
    /* Incoming DATA1..DATA0 fills the SRAM 64-byte buffer at index 0.
       No Flash LPM/RMW and no SPM inside SETUP or bit-level USB code. */
    std     Y+53, r1
    ldi     r17, EMPTY_MESSAGE
    std     Y+0, r17
    rjmp    L1df8
block_write_bad:
block_reject:
    /* A malformed or overlapping command may not cancel an in-progress
       operation; otherwise a hostile SETUP could interrupt a pending SPM. */
    ldd     r18, Y+48
    cpi     r18, ST_RECEIVE
    brsh    block_reject_no_state
    /* Both RESULT_BOUNDS and ST_ERROR are value 2. */
    ldi     r18, RESULT_BOUNDS
    std     Y+55, r18
    std     Y+48, r18
block_reject_no_state:
    ldi     r24, EMPTY_MESSAGE
    std     Y+0, r24
    rjmp    L1df8


/* ERASE_PAGE uses a zero-length Vendor OUT control request.
   Host is responsible for waiting for completion before WRITE_PAGE.
   Must not erase any bootloader byte; 0x1900 is the final writable page
   for BOOT_AT=0x1980 (other layouts derive it from BOOT_AT). */
block_erase_setup:
    ldd     r22, Y+25
    ldd     r23, Y+26
    mov     r18, r22
    andi    r18, 0x3f
    brne    block_reject
#if (BOOT_AT & 0xff) == 0
    /* Since both page and boot start are 256B-aligned, comparing the
       high byte alone is sufficient to reject the entire bootloader. */
    cpi     r23, (BOOT_AT >> 8)
    brsh    block_reject
#else
    cpi     r22, (BOOT_AT & 0xff)
    ldi     r18, (BOOT_AT >> 8)
    cpc     r23, r18
    brsh    block_reject
#endif
    /* Memory type must be Flash, length=0, and index high/low zero. */
    ldd     r18, Y+27
    ldd     r19, Y+28
    or      r18, r19
    ldd     r19, Y+29
    or      r18, r19
    ldd     r19, Y+30
    or      r18, r19
    brne    block_reject
    rcall   block_check_idle_for_write
    brcc    block_reject
    ldi     r18, ST_FLASH_WAIT_PREP
    std     Y+48, r18
    /* MEM_TYPE is not used during standalone ERASE. */
    std     Y+50, r22
    std     Y+51, r23
    ldi     r18, RESULT_BUSY
    std     Y+56, r18  /* SPM operation flag: 1=erase, 0=page-write */
    std     Y+55, r18
    /* Prepare ZLP for the control OUT status stage. */
    std     Y+0, r1
    rjmp    L1df8

/* Returns C=1 if no other memory operation is active and EEPE is clear. */
block_check_idle_for_write:
    ldd     r17, Y+48
    cpi     r17, ST_RUN
    brsh    block_idle_return    /* C=0 for state>=3: already busy */
    /* If EEPROM is idle, SBIC skips CLC: CPI left C=1 for state<3. */
    sbic    0x1f, 1
    clc
block_idle_return:
    ret


/* Validate wValue+wLength against selected memory bounds. Carry set
 * on success; r16 type, r22:r23 address, r24 length; r18:r19 scratch. */
block_validate_range:
    ldd     r16, Y+27
    /* Combine the reserved high byte of wIndex and wLength. */
    ldd     r18, Y+28
    ldd     r19, Y+30
    or      r18, r19
    brne    block_invalid_range
    cpi     r16, 2
    brsh    block_invalid_range
    ldd     r24, Y+29
    tst     r24
    breq    block_invalid_range
    cpi     r24, 65
    brsh    block_invalid_range
    ldd     r22, Y+25
    ldd     r23, Y+26
    /* Avoid 17-bit address+length arithmetic: compare address <= bound-length.
       Both memory bounds are >=64, and 1<=length<=64 was checked above. */
    /* Select the exclusive end: EEPROM=64, Flash=BOOT_AT. */
    ldi     r20, 64
    ldi     r21, 0
    tst     r16
    brne    block_check_selected_bound
#if (BOOT_AT & 0xff) != 64
    ldi     r20, (BOOT_AT & 0xff)
#endif
    ldi     r21, (BOOT_AT >> 8)
block_check_selected_bound:
    sub     r20, r24
    sbc     r21, r1
    cp      r20, r22
    cpc     r21, r23
    brcs    block_invalid_range
block_valid_range:
    sec
    ret
block_invalid_range:
    clc
    ret

/* One incoming OUT DATA0/1 packet containing 1..8 payload bytes.
 * RX data already ACKed by USB_handler; buffer stays NAK until consumed.
 */
block_accept_out:
    ldd     r18, Y+48
    cpi     r18, ST_RECEIVE
    brne    block_out_return
    /* ACK may have been lost at the host; ignore repeated DATA0/DATA1. */
    ldd     r17, Y+22            /* received PID */
    ldd     r18, Y+57
    cp      r17, r18
    brne    block_out_return
    /* r24 = rxLength - 3, valid length 1..8 and <= remaining */
    tst     r24
    breq    block_out_return
    cpi     r24, 9
    brsh    block_out_return
    /* Verify DATA CRC16 using the same 44-byte V-USB CRC routine.
       This runs AFTER the hardware-timed packet ACK, outside USB sampling.
       Discard corrupted payload and force a host timeout rather than
       silently writing Flash/EEPROM. */
    mov     r23, r24
    ldi     r26, 0x17
    ldi     r27, 0x01
    add     r26, r23
    ld      r16, X+            /* received CRC low */
    ld      r17, X             /* received CRC high */
    ldi     r24, 0x17
    ldi     r25, 0x01
    mov     r22, r23
    rcall   usb_crc16_append
    cp      r24, r16
    cpc     r25, r17  /* combine 16-bit equality with propagated Z */
    brne    block_out_return
    mov     r24, r23
    ldd     r18, Y+52
    cp      r18, r24
    brlo    block_out_return
    sub     r18, r24
    std     Y+52, r18
    ldd     r19, Y+53
    ldi     r26, 0x17            /* RX payload at 0x0117 */
    ldi     r27, 0x01
    ldi     r30, 0x40            /* SRAM block data 0x0140 + index */
    add     r30, r19
    ldi     r31, 0x01
block_out_copy_byte:
    ld      r20, X+
    st      Z+, r20
    inc     r19
    dec     r24
    brne    block_out_copy_byte
    std     Y+53, r19
    ldd     r17, Y+57
    ldi     r20, 0x88            /* DATA0/DATA1 PID XOR mask */
    eor     r17, r20
    std     Y+57, r17
    tst     r18
    brne    block_out_return
    /* Received full wLength. Queue asynchronous memory commit. */
    /* For type 0/1 select 6=FLASH_WAIT_PREP or 5=WRITE_EEPROM. */
    ldd     r17, Y+49
    ldi     r20, ST_FLASH_WAIT_PREP
    sub     r20, r17
    std     Y+48, r20
    tst     r17
    brne    block_out_return
    /* The last FLASH DATA OUT byte queues the status-stage ZLP. */
    std     Y+0, r1
block_out_return:
    ret

/* Called from main loop, never within the cycle-critical USB packet engine.
 * EEPROM programming progresses one byte whenever EEPE clears. Flash
 * erase/fill/write executes only after the entire control OUT payload.
 */
block_memory_service:
    ldi     r28, 0x00
    ldi     r29, 0x01
    ldd     r18, Y+48
    cpi     r18, ST_WRITE_EEPROM
    breq    block_step_eeprom
    cpi     r18, ST_RUN
    brne    block_service_return
    /* Inline the sole RUN dispatch, remove RCALL trampoline and a RET. */
    lds     r18, 0x010f
    cpi     r18, EP0_NAK
    brne    block_service_return
    rjmp    L1eac
block_service_return:
    ret

block_step_eeprom:
    sbic    0x1f, 1           /* EEPE active? */
    ret
    ldd     r18, Y+56
    ldd     r19, Y+54
    cp      r18, r19
    breq    block_complete
block_eeprom_more_bytes:
    ldd     r20, Y+50
    add     r20, r18
    ldi     r30, 0x40
    add     r30, r18
    ldi     r31, 0x01
    ld      r21, Z
    out     0x21, r20         /* EEARL */
    out     0x20, r21         /* EEDR */
    out     0x1f, r1         /* erase-and-write mode */
    sbi     0x1f, 2          /* EEMPE: master enable */
    sbi     0x1f, 1          /* EEPE within 4 cycles */
    inc     r18
    std     Y+56, r18
    ret

block_complete:
    /* Finish EEPROM control-OUT with a ZLP; Flash finishes separately. */
    sts     0x0100, r1
    rjmp    block_complete_flash

/* This hook runs only when the main USB polling window has expired.
   The control OUT status ZLP must have been physically emitted first,
   i.e. its TX length returned to EP0_NAK. The host waits after the
   successful control transfer, because ATtiny88 stalls during SPM. */
block_spm_after_quiet:
    ldi     r28, 0x00
    ldi     r29, 0x01
    ldd     r18, Y+48
    cpi     r18, ST_SPM_WAIT_SENT
    brne    block_service_return
    ldd     r18, Y+15
    cpi     r18, EP0_NAK
    brne    block_service_return
    ldd     r18, Y+56
    tst     r18
    breq    block_commit_flash

block_flash_erase_only:
    /* EEPE was checked when command was accepted. Busy states block
       intervening EEPROM commands, so no intervening EEPROM write exists. */
    rcall   block_load_page_z
    ldi     r18, 0x03
    out     0x37, r18
    spm
    rjmp    block_complete_flash

block_commit_flash:
    /* Same interlock as standalone ERASE_PAGE, no duplicate EEPE check. */
    rcall   block_load_page_z
    /* Patch ONLY 0x0000..0x0001 on page 0. Leave 0x0002..0x003f
       exactly as supplied by the application, including all ISR vectors.
       This does NOT keep RESET valid between ERASE_PAGE and WRITE. */
    mov     r18, r30
    or      r18, r31
    brne    block_flash_fill_start
    ldi     r26, 0x40
    ldi     r27, 0x01
    ldi     r18, (RESET_RJMP & 0xff)
    st      X+, r18
    ldi     r18, (RESET_RJMP >> 8)
    st      X, r18
block_flash_fill_start:
    /* Clear stale hardware page buffer. Page erase was a separate call. */
    ldi     r18, 0x11
    out     0x37, r18        /* CTPB|SELFPRGEN */
    spm
    ldi     r26, 0x40
    ldi     r27, 0x01
    ldi     r20, 32          /* 32 words in one 64-byte page */
    ldi     r18, 0x01
block_flash_fill_word:
    ld      r0, X+
    ld      r1, X+
    out     0x37, r18
    spm
    adiw    r30, 2
    dec     r20
    brne    block_flash_fill_word
    clr     r1
    /* Page write must have Z low six address bits zero. */
    rcall   block_load_page_z
    ldi     r18, 0x05
    out     0x37, r18
    spm
    /* Fall through into shared completion; no second USB status. */

block_complete_flash:
    /* The control transfer has already completed; never queue another ZLP. */
    std     Y+55, r1
    ldi     r18, ST_DONE
    std     Y+48, r18
    ret

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
    ldi     r18, ((BOOT_AT + 0x1c) & 0xff)
    cpi     r24, 0x01
    breq    desc_ptr
    cpi     r24, 0x02
    brne    L1f70
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
    ldd     r18, Y+21
    std     Y+2, r18
    ldi     r24, 0x01

main_tail:
    rjmp    L1f34

L1f82:
    /* Removed 0x1f82: sbi     0xb, 0 (size-optimized, see CHANGES.md) */
    /* Removed 0x1f84: rjmp    L1e84 (size-optimized, see CHANGES.md) */


/* Shared non-USB address builder for both Flash SPM operations and
   the page-buffer refill. Saves 4 bytes despite RCALL/RET overhead.
   Must execute before SPMCSR timing-critical write, not after it. */
block_load_page_z:
    ldd     r30, Y+50
    andi    r30, 0xc0
    ldd     r31, Y+51
    ret
