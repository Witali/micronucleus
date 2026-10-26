/* Experimental V2 16 MHz streaming RX CRC sampler. Not production validated.
 * Derived from V-USB 18 MHz CRC receive architecture and maintained t88 PHY.
 * GPL-2.0-or-later; original V-USB contributor notices remain in upstream.
 * Tables: low page 0x16, high page 0x17; must match wrapper placement.
 * CRC stages: bit3 index, bit4 high carry, bit5 high LPM, bit6 low LPM.
 * Normal bit periods: 10,10,11/12,11,11,11,11,10 = 85/86 clocks.
 * True rolling-byte assembly permits a two-instruction six-one test.
 * Stuffed zeros enter five-bit cooldown paths without altering real data.
 * SE0 guards cover every even bit plus the first cooldown sample.
 */
#ifndef STREAM_CRC_TABLE_LOW_PAGE
#define STREAM_CRC_TABLE_LOW_PAGE 0x16
#endif
#ifndef STREAM_CRC_TABLE_HIGH_PAGE
#define STREAM_CRC_TABLE_HIGH_PAGE 0x17
#endif
USB_handler:
    push    r28
    push    r29
    eor     r28, r28

L1abe:
    inc     r28
    sbis    T88_IO_PIND, 1
    brbc    1, L1abe

L1ac4:
    sbis    T88_IO_PIND, 1
    rjmp    L1ade
    sbis    T88_IO_PIND, 1
    rjmp    L1ade
    sbis    T88_IO_PIND, 1
    rjmp    L1ade
    sbis    T88_IO_PIND, 1
    rjmp    L1ade
    sbis    T88_IO_PIND, 1
    rjmp    L1ade
    sbis    T88_IO_PIND, 1
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
    sbis    T88_IO_PIND, 1
    rjmp    L1af8
    push    r0
    pop     r0
    rjmp    L1ac4


L1af8:
    push    r19
    ldi     r19, 11
    ldi     r17, 4
    clr     r18
    clr     r21
    nop
    ldi     r30, 0x54
    ldi     r25, 0xfe
    nop
stream_pid_bit0:
    in      r16, T88_IO_PIND
    andi    r16, 6
    eor     r17, r16
    subi    r17, 1
    ror     r18
    rjmp    .+0
    rjmp    .+0
    rjmp    .+0
stream_pid_bit1:
    in      r17, T88_IO_PIND
    andi    r17, 6
    breq    stream_pid_drop
    eor     r16, r17
    subi    r16, 1
    ror     r18
    rjmp    .+0
    rjmp    .+0
stream_pid_bit2:
    in      r16, T88_IO_PIND
    andi    r16, 6
    eor     r17, r16
    subi    r17, 1
    ror     r18
    rjmp    .+0
    rjmp    .+0
    rjmp    .+0
stream_pid_bit3:
    in      r17, T88_IO_PIND
    andi    r17, 6
    breq    stream_pid_drop
    eor     r16, r17
    subi    r16, 1
    ror     r18
    rjmp    .+0
    rjmp    .+0
    nop
stream_pid_bit4:
    in      r16, T88_IO_PIND
    andi    r16, 6
    eor     r17, r16
    subi    r17, 1
    ror     r18
    rjmp    .+0
    rjmp    .+0
    nop
stream_pid_bit5:
    in      r17, T88_IO_PIND
    andi    r17, 6
    breq    stream_pid_drop
    eor     r16, r17
    subi    r16, 1
    ror     r18
    rjmp    .+0
    rjmp    .+0
    nop
stream_pid_bit6:
    in      r16, T88_IO_PIND
    andi    r16, 6
    eor     r17, r16
    subi    r17, 1
    ror     r18
    rjmp    .+0
    rjmp    .+0
    nop
    ldi     r22, 4
stream_pid_bit7:
    in      r17, T88_IO_PIND
    andi    r17, 6
    eor     r16, r17
    subi    r16, 1
    ror     r18
    mov     r20, r18
    mov     r24, r20
    mov     r26, r20
    rjmp    stream_bit0
stream_pid_drop:
    rjmp    stream_drop

/* Nearby stubs keep conditional branches within AVR reach. */
stream_stuff_stub4:
    rjmp    stream_stuff4
stream_stuff_stub5:
    rjmp    stream_stuff5
stream_stuff_stub6:
    rjmp    stream_stuff6
stream_stuff_stub7:
    rjmp    stream_stuff7
stream_eop_near46_before_store:
    rjmp    stream_eop_before_store
stream_eop_near46_store_only:
    rjmp    stream_eop_store_only
stream_eop_near46_full:
    rjmp    stream_eop_full
stream_eop_near46_index:
    rjmp    stream_eop_index
stream_eop_near46_low:
    rjmp    stream_eop_low
stream_eop_near46_finish:
    rjmp    stream_eop_finish
stream_eop_near46_drop:
    rjmp    stream_drop

stream_bit4:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_eop_near46_index
    eor     r17, r16
    subi    r17, 1
    ror     r18
    cpi     r18, 0xfc
    brcc    stream_stuff_stub4
    mov     r24, r25
    ldi     r31, STREAM_CRC_TABLE_HIGH_PAGE
    nop

stream_bit5:
    in      r17, T88_IO_PIND
    andi    r17, 6
    eor     r16, r17
    subi    r16, 1
    ror     r18
    cpi     r18, 0xfc
    brcc    stream_stuff_stub5
    lpm     r25, Z
    ldi     r31, STREAM_CRC_TABLE_LOW_PAGE

stream_bit6:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_eop_near46_low
    eor     r17, r16
    subi    r17, 1
    ror     r18
    cpi     r18, 0xfc
    brcc    stream_stuff_stub6
    lpm     r30, Z

stream_bit7:
    in      r17, T88_IO_PIND
    andi    r17, 6
    eor     r16, r17
    subi    r16, 1
    ror     r18
    cpi     r18, 0xfc
    brcc    stream_stuff_stub7
    mov     r20, r18
    rjmp    .+0

stream_bit0:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_eop_near03_before_store
    eor     r17, r16
    subi    r17, 1
    ror     r18
    cpi     r18, 0xfc
    brcc    stream_stuff_stub0
    subi    r19, 1
    brcs    stream_eop_near03_drop

stream_bit1:
    in      r17, T88_IO_PIND
    andi    r17, 6
    breq    stream_eop_near03_store_only
    eor     r16, r17
    subi    r16, 1
    ror     r18
    cpi     r18, 0xfc
    brcc    stream_stuff_stub1
    st      Y+, r20

stream_bit2:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_eop_near03_full
    eor     r17, r16
    subi    r17, 1
    ror     r18
    cpi     r18, 0xfc
    brcc    stream_stuff_stub2
    subi    r21, 1
    brpl    .+4
    subi    r21, 0xfd
    nop

stream_bit3:
    in      r17, T88_IO_PIND
    andi    r17, 6
    eor     r16, r17
    subi    r16, 1
    ror     r18
    cpi     r18, 0xfc
    brcc    stream_stuff_stub3
    eor     r30, r24
    eor     r30, r20
    rjmp    stream_bit4
stream_stuff_stub0:
    rjmp    stream_stuff0
stream_stuff_stub1:
    rjmp    stream_stuff1
stream_stuff_stub2:
    rjmp    stream_stuff2
stream_stuff_stub3:
    rjmp    stream_stuff3
stream_eop_near03_before_store:
    rjmp    stream_eop_before_store
stream_eop_near03_store_only:
    rjmp    stream_eop_store_only
stream_eop_near03_full:
    rjmp    stream_eop_full
stream_eop_near03_index:
    rjmp    stream_eop_index
stream_eop_near03_low:
    rjmp    stream_eop_low
stream_eop_near03_finish:
    rjmp    stream_eop_finish
stream_eop_near03_drop:
    rjmp    stream_drop

/* Stuff after bit0: preserve real history, then suppress checks for five bits. */
stream_stuff0:
stream_stuff0_sample:
    in      r17, T88_IO_PIND
    andi    r17, 6
    eor     r16, r17
    breq    stream_stuff_bad0
    rjmp    .+0
    subi    r19, 1
    brcs    stream_stuff_overflow0
    rjmp    stream_cooldown_0_1
stream_stuff_overflow0:
    rjmp    stream_drop
stream_stuff_bad0:
    tst     r17
    breq    stream_stuff_eop0
    rjmp    stream_drop
stream_stuff_eop0:
    rjmp    stream_eop_before_store
stream_cooldown_0_1:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_cooldown_eop0_store_only
    eor     r17, r16
    subi    r17, 1
    ror     r18
    rjmp    .+0
    st      Y+, r20
stream_cooldown_0_2:
    in      r17, T88_IO_PIND
    andi    r17, 6
    breq    stream_cooldown_eop0_full
    eor     r16, r17
    subi    r16, 1
    ror     r18
    subi    r21, 0xff
    mov     r16, r17
    subi    r21, 1
    brpl    .+4
    subi    r21, 0xfd
    nop
stream_cooldown_0_3:
    in      r17, T88_IO_PIND
    andi    r17, 6
    eor     r16, r17
    subi    r16, 1
    ror     r18
    rjmp    .+0
    eor     r30, r24
    eor     r30, r20
    rjmp    .+0
stream_cooldown_0_4:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_cooldown_eop0_index
    eor     r17, r16
    subi    r17, 1
    ror     r18
    rjmp    .+0
    mov     r24, r25
    ldi     r31, STREAM_CRC_TABLE_HIGH_PAGE
    nop
stream_cooldown_0_5:
    in      r17, T88_IO_PIND
    andi    r17, 6
    eor     r16, r17
    subi    r16, 1
    ror     r18
    lpm     r25, Z
    ldi     r31, STREAM_CRC_TABLE_LOW_PAGE
    rjmp    stream_bit6
stream_cooldown_eop0_before_store:
    rjmp    stream_eop_before_store
stream_cooldown_eop0_store_only:
    rjmp    stream_eop_store_only
stream_cooldown_eop0_full:
    rjmp    stream_eop_full
stream_cooldown_eop0_index:
    rjmp    stream_eop_index
stream_cooldown_eop0_low:
    rjmp    stream_eop_low
stream_cooldown_eop0_finish:
    rjmp    stream_eop_finish
stream_cooldown_eop0_drop:
    rjmp    stream_drop

/* Stuff after bit1: preserve real history, then suppress checks for five bits. */
stream_stuff1:
stream_stuff1_sample:
    in      r16, T88_IO_PIND
    andi    r16, 6
    eor     r17, r16
    breq    stream_stuff_bad1
    rjmp    .+0
    st      Y+, r20
    rjmp    stream_cooldown_1_1
stream_stuff_overflow1:
    rjmp    stream_drop
stream_stuff_bad1:
    tst     r16
    breq    stream_stuff_eop1
    rjmp    stream_drop
stream_stuff_eop1:
    rjmp    stream_eop_store_only
stream_cooldown_1_1:
    in      r17, T88_IO_PIND
    andi    r17, 6
    breq    stream_cooldown_eop1_full
    eor     r16, r17
    subi    r16, 1
    ror     r18
    subi    r21, 0xff
    nop
    subi    r21, 1
    brpl    .+4
    subi    r21, 0xfd
    nop
stream_cooldown_1_2:
    in      r16, T88_IO_PIND
    andi    r16, 6
    eor     r17, r16
    subi    r17, 1
    ror     r18
    mov     r17, r16
    nop
    eor     r30, r24
    eor     r30, r20
    rjmp    .+0
stream_cooldown_1_3:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_cooldown_eop1_index
    eor     r17, r16
    subi    r17, 1
    ror     r18
    rjmp    .+0
    mov     r24, r25
    ldi     r31, STREAM_CRC_TABLE_HIGH_PAGE
    nop
stream_cooldown_1_4:
    in      r17, T88_IO_PIND
    andi    r17, 6
    eor     r16, r17
    subi    r16, 1
    ror     r18
    rjmp    .+0
    lpm     r25, Z
    ldi     r31, STREAM_CRC_TABLE_LOW_PAGE
stream_cooldown_1_5:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_cooldown_eop1_low
    eor     r17, r16
    subi    r17, 1
    ror     r18
    lpm     r30, Z
    rjmp    stream_bit7
stream_cooldown_eop1_before_store:
    rjmp    stream_eop_before_store
stream_cooldown_eop1_store_only:
    rjmp    stream_eop_store_only
stream_cooldown_eop1_full:
    rjmp    stream_eop_full
stream_cooldown_eop1_index:
    rjmp    stream_eop_index
stream_cooldown_eop1_low:
    rjmp    stream_eop_low
stream_cooldown_eop1_finish:
    rjmp    stream_eop_finish
stream_cooldown_eop1_drop:
    rjmp    stream_drop

/* Stuff after bit2: preserve real history, then suppress checks for five bits. */
stream_stuff2:
stream_stuff2_sample:
    in      r17, T88_IO_PIND
    andi    r17, 6
    eor     r16, r17
    breq    stream_stuff_bad2
    subi    r21, 0xff
    nop
    subi    r21, 1
    brpl    .+4
    subi    r21, 0xfd
    nop
    rjmp    stream_cooldown_2_1
stream_stuff_overflow2:
    rjmp    stream_drop
stream_stuff_bad2:
    tst     r17
    breq    stream_stuff_eop2
    rjmp    stream_drop
stream_stuff_eop2:
    rjmp    stream_eop_full
stream_cooldown_2_1:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_cooldown_eop2_full
    eor     r17, r16
    subi    r17, 1
    ror     r18
    nop
    eor     r30, r24
    eor     r30, r20
    rjmp    .+0
stream_cooldown_2_2:
    in      r17, T88_IO_PIND
    andi    r17, 6
    breq    stream_cooldown_eop2_index
    eor     r16, r17
    subi    r16, 1
    ror     r18
    mov     r16, r17
    nop
    mov     r24, r25
    ldi     r31, STREAM_CRC_TABLE_HIGH_PAGE
    nop
stream_cooldown_2_3:
    in      r17, T88_IO_PIND
    andi    r17, 6
    eor     r16, r17
    subi    r16, 1
    ror     r18
    rjmp    .+0
    lpm     r25, Z
    ldi     r31, STREAM_CRC_TABLE_LOW_PAGE
stream_cooldown_2_4:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_cooldown_eop2_low
    eor     r17, r16
    subi    r17, 1
    ror     r18
    rjmp    .+0
    lpm     r30, Z
stream_cooldown_2_5:
    in      r17, T88_IO_PIND
    andi    r17, 6
    eor     r16, r17
    subi    r16, 1
    ror     r18
    mov     r20, r18
    rjmp    .+0
    rjmp    stream_bit0
stream_cooldown_eop2_before_store:
    rjmp    stream_eop_before_store
stream_cooldown_eop2_store_only:
    rjmp    stream_eop_store_only
stream_cooldown_eop2_full:
    rjmp    stream_eop_full
stream_cooldown_eop2_index:
    rjmp    stream_eop_index
stream_cooldown_eop2_low:
    rjmp    stream_eop_low
stream_cooldown_eop2_finish:
    rjmp    stream_eop_finish
stream_cooldown_eop2_drop:
    rjmp    stream_drop

/* Stuff after bit3: preserve real history, then suppress checks for five bits. */
stream_stuff3:
    nop
stream_stuff3_sample:
    in      r16, T88_IO_PIND
    andi    r16, 6
    eor     r17, r16
    breq    stream_stuff_bad3
    rjmp    .+0
    nop
    eor     r30, r24
    eor     r30, r20
    rjmp    stream_cooldown_3_1
stream_stuff_overflow3:
    rjmp    stream_drop
stream_stuff_bad3:
    tst     r16
    breq    stream_stuff_eop3
    rjmp    stream_drop
stream_stuff_eop3:
    rjmp    stream_eop_full
stream_cooldown_3_1:
    in      r17, T88_IO_PIND
    andi    r17, 6
    breq    stream_cooldown_eop3_index
    eor     r16, r17
    subi    r16, 1
    ror     r18
    rjmp    .+0
    mov     r24, r25
    ldi     r31, STREAM_CRC_TABLE_HIGH_PAGE
    nop
stream_cooldown_3_2:
    in      r16, T88_IO_PIND
    andi    r16, 6
    eor     r17, r16
    subi    r17, 1
    ror     r18
    mov     r17, r16
    nop
    lpm     r25, Z
    ldi     r31, STREAM_CRC_TABLE_LOW_PAGE
stream_cooldown_3_3:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_cooldown_eop3_low
    eor     r17, r16
    subi    r17, 1
    ror     r18
    subi    r21, 0xff
    nop
    lpm     r30, Z
stream_cooldown_3_4:
    in      r17, T88_IO_PIND
    andi    r17, 6
    eor     r16, r17
    subi    r16, 1
    ror     r18
    rjmp    .+0
    mov     r20, r18
    rjmp    .+0
stream_cooldown_3_5:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_cooldown_eop3_before_store
    eor     r17, r16
    subi    r17, 1
    ror     r18
    subi    r19, 1
    brcs    stream_cooldown_eop3_drop
    rjmp    stream_bit1
stream_cooldown_eop3_before_store:
    rjmp    stream_eop_before_store
stream_cooldown_eop3_store_only:
    rjmp    stream_eop_store_only
stream_cooldown_eop3_full:
    rjmp    stream_eop_full
stream_cooldown_eop3_index:
    rjmp    stream_eop_index
stream_cooldown_eop3_low:
    rjmp    stream_eop_low
stream_cooldown_eop3_finish:
    rjmp    stream_eop_finish
stream_cooldown_eop3_drop:
    rjmp    stream_drop

/* Stuff after bit4: preserve real history, then suppress checks for five bits. */
stream_stuff4:
stream_stuff4_sample:
    in      r17, T88_IO_PIND
    andi    r17, 6
    eor     r16, r17
    breq    stream_stuff_bad4
    rjmp    .+0
    mov     r24, r25
    ldi     r31, STREAM_CRC_TABLE_HIGH_PAGE
    nop
    rjmp    stream_cooldown_4_1
stream_stuff_overflow4:
    rjmp    stream_drop
stream_stuff_bad4:
    tst     r17
    breq    stream_stuff_eop4
    rjmp    stream_drop
stream_stuff_eop4:
    rjmp    stream_eop_index
stream_cooldown_4_1:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_cooldown_eop4_index
    eor     r17, r16
    subi    r17, 1
    ror     r18
    nop
    lpm     r25, Z
    ldi     r31, STREAM_CRC_TABLE_LOW_PAGE
stream_cooldown_4_2:
    in      r17, T88_IO_PIND
    andi    r17, 6
    breq    stream_cooldown_eop4_low
    eor     r16, r17
    subi    r16, 1
    ror     r18
    mov     r16, r17
    nop
    lpm     r30, Z
stream_cooldown_4_3:
    in      r17, T88_IO_PIND
    andi    r17, 6
    eor     r16, r17
    subi    r16, 1
    ror     r18
    subi    r21, 0xff
    nop
    mov     r20, r18
    rjmp    .+0
stream_cooldown_4_4:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_cooldown_eop4_before_store
    eor     r17, r16
    subi    r17, 1
    ror     r18
    rjmp    .+0
    subi    r19, 1
    brcs    stream_cooldown_eop4_drop
stream_cooldown_4_5:
    in      r17, T88_IO_PIND
    andi    r17, 6
    breq    stream_cooldown_eop4_store_only
    eor     r16, r17
    subi    r16, 1
    ror     r18
    st      Y+, r20
    rjmp    stream_bit2
stream_cooldown_eop4_before_store:
    rjmp    stream_eop_before_store
stream_cooldown_eop4_store_only:
    rjmp    stream_eop_store_only
stream_cooldown_eop4_full:
    rjmp    stream_eop_full
stream_cooldown_eop4_index:
    rjmp    stream_eop_index
stream_cooldown_eop4_low:
    rjmp    stream_eop_low
stream_cooldown_eop4_finish:
    rjmp    stream_eop_finish
stream_cooldown_eop4_drop:
    rjmp    stream_drop

/* Stuff after bit5: preserve real history, then suppress checks for five bits. */
stream_stuff5:
    nop
stream_stuff5_sample:
    in      r16, T88_IO_PIND
    andi    r16, 6
    eor     r17, r16
    breq    stream_stuff_bad5
    nop
    lpm     r25, Z
    ldi     r31, STREAM_CRC_TABLE_LOW_PAGE
    rjmp    stream_cooldown_5_1
stream_stuff_overflow5:
    rjmp    stream_drop
stream_stuff_bad5:
    tst     r16
    breq    stream_stuff_eop5
    rjmp    stream_drop
stream_stuff_eop5:
    rjmp    stream_eop_index
stream_cooldown_5_1:
    in      r17, T88_IO_PIND
    andi    r17, 6
    breq    stream_cooldown_eop5_low
    eor     r16, r17
    subi    r16, 1
    ror     r18
    rjmp    .+0
    lpm     r30, Z
stream_cooldown_5_2:
    in      r16, T88_IO_PIND
    andi    r16, 6
    eor     r17, r16
    subi    r17, 1
    ror     r18
    mov     r17, r16
    nop
    mov     r20, r18
    rjmp    .+0
stream_cooldown_5_3:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_cooldown_eop5_before_store
    eor     r17, r16
    subi    r17, 1
    ror     r18
    subi    r21, 0xff
    nop
    subi    r19, 1
    brcs    stream_cooldown_eop5_drop
stream_cooldown_5_4:
    in      r17, T88_IO_PIND
    andi    r17, 6
    breq    stream_cooldown_eop5_store_only
    eor     r16, r17
    subi    r16, 1
    ror     r18
    rjmp    .+0
    st      Y+, r20
stream_cooldown_5_5:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_cooldown_eop5_full
    eor     r17, r16
    subi    r17, 1
    ror     r18
    subi    r21, 1
    brpl    .+4
    subi    r21, 0xfd
    nop
    rjmp    stream_bit3
stream_cooldown_eop5_before_store:
    rjmp    stream_eop_before_store
stream_cooldown_eop5_store_only:
    rjmp    stream_eop_store_only
stream_cooldown_eop5_full:
    rjmp    stream_eop_full
stream_cooldown_eop5_index:
    rjmp    stream_eop_index
stream_cooldown_eop5_low:
    rjmp    stream_eop_low
stream_cooldown_eop5_finish:
    rjmp    stream_eop_finish
stream_cooldown_eop5_drop:
    rjmp    stream_drop

/* Stuff after bit6: preserve real history, then suppress checks for five bits. */
stream_stuff6:
stream_stuff6_sample:
    in      r17, T88_IO_PIND
    andi    r17, 6
    eor     r16, r17
    breq    stream_stuff_bad6
    rjmp    .+0
    lpm     r30, Z
    rjmp    stream_cooldown_6_1
stream_stuff_overflow6:
    rjmp    stream_drop
stream_stuff_bad6:
    tst     r17
    breq    stream_stuff_eop6
    rjmp    stream_drop
stream_stuff_eop6:
    rjmp    stream_eop_low
stream_cooldown_6_1:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_cooldown_eop6_finish
    eor     r17, r16
    subi    r17, 1
    ror     r18
    nop
    mov     r20, r18
    rjmp    .+0
stream_cooldown_6_2:
    in      r17, T88_IO_PIND
    andi    r17, 6
    breq    stream_cooldown_eop6_before_store
    eor     r16, r17
    subi    r16, 1
    ror     r18
    mov     r16, r17
    nop
    subi    r19, 1
    brcs    stream_cooldown_eop6_drop
stream_cooldown_6_3:
    in      r17, T88_IO_PIND
    andi    r17, 6
    breq    stream_cooldown_eop6_store_only
    eor     r16, r17
    subi    r16, 1
    ror     r18
    subi    r21, 0xff
    nop
    st      Y+, r20
stream_cooldown_6_4:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_cooldown_eop6_full
    eor     r17, r16
    subi    r17, 1
    ror     r18
    rjmp    .+0
    subi    r21, 1
    brpl    .+4
    subi    r21, 0xfd
    nop
stream_cooldown_6_5:
    in      r17, T88_IO_PIND
    andi    r17, 6
    eor     r16, r17
    subi    r16, 1
    ror     r18
    rjmp    .+0
    eor     r30, r24
    eor     r30, r20
    rjmp    stream_bit4
stream_cooldown_eop6_before_store:
    rjmp    stream_eop_before_store
stream_cooldown_eop6_store_only:
    rjmp    stream_eop_store_only
stream_cooldown_eop6_full:
    rjmp    stream_eop_full
stream_cooldown_eop6_index:
    rjmp    stream_eop_index
stream_cooldown_eop6_low:
    rjmp    stream_eop_low
stream_cooldown_eop6_finish:
    rjmp    stream_eop_finish
stream_cooldown_eop6_drop:
    rjmp    stream_drop

/* Stuff after bit7: preserve real history, then suppress checks for five bits. */
stream_stuff7:
stream_stuff7_sample:
    in      r16, T88_IO_PIND
    andi    r16, 6
    eor     r17, r16
    breq    stream_stuff_bad7
    nop
    mov     r20, r18
    rjmp    .+0
    rjmp    stream_cooldown_7_1
stream_stuff_overflow7:
    rjmp    stream_drop
stream_stuff_bad7:
    tst     r16
    breq    stream_stuff_eop7
    rjmp    stream_drop
stream_stuff_eop7:
    rjmp    stream_eop_finish
stream_cooldown_7_1:
    in      r17, T88_IO_PIND
    andi    r17, 6
    breq    stream_cooldown_eop7_before_store
    eor     r16, r17
    subi    r16, 1
    ror     r18
    rjmp    .+0
    subi    r19, 1
    brcs    stream_cooldown_eop7_drop
stream_cooldown_7_2:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_cooldown_eop7_store_only
    eor     r17, r16
    subi    r17, 1
    ror     r18
    mov     r17, r16
    nop
    st      Y+, r20
stream_cooldown_7_3:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_cooldown_eop7_full
    eor     r17, r16
    subi    r17, 1
    ror     r18
    subi    r21, 2
    nop
    subi    r21, 1
    brpl    .+4
    subi    r21, 0xfd
    nop
stream_cooldown_7_4:
    in      r17, T88_IO_PIND
    andi    r17, 6
    eor     r16, r17
    subi    r16, 1
    ror     r18
    rjmp    .+0
    eor     r30, r24
    eor     r30, r20
    rjmp    .+0
stream_cooldown_7_5:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_cooldown_eop7_index
    eor     r17, r16
    subi    r17, 1
    ror     r18
    mov     r24, r25
    ldi     r31, STREAM_CRC_TABLE_HIGH_PAGE
    nop
    rjmp    stream_bit5
stream_cooldown_eop7_before_store:
    rjmp    stream_eop_before_store
stream_cooldown_eop7_store_only:
    rjmp    stream_eop_store_only
stream_cooldown_eop7_full:
    rjmp    stream_eop_full
stream_cooldown_eop7_index:
    rjmp    stream_eop_index
stream_cooldown_eop7_low:
    rjmp    stream_eop_low
stream_cooldown_eop7_finish:
    rjmp    stream_eop_finish
stream_cooldown_eop7_drop:
    rjmp    stream_drop
/* Direct EOP tails avoid a stage variable on the ACK-critical path. */
stream_eop_before_store:
    subi    r19, 1
    brcs    stream_eop_overflow
stream_eop_store_only:
    st      Y+, r20
stream_eop_full:
    subi    r19, 11
    neg     r19
    sub     r28, r19
    out     T88_IO_PCIFR, r22
    mov     r16, r26
    cpi     r16, 0x4b
    breq    stream_eop_full_data
    cpi     r16, 0xc3
    brne    stream_eop_nondata
stream_eop_full_data:
    eor     r30, r24
    mov     r24, r25
    eor     r30, r20
    ldi     r31, STREAM_CRC_TABLE_HIGH_PAGE
    lpm     r25, Z
    ldi     r31, STREAM_CRC_TABLE_LOW_PAGE
    lpm     r30, Z
    eor     r30, r24
stream_crc_compare:
    cpi     r30, 1
    brne    stream_crc_drop
    cpi     r25, 0xb0
    brne    stream_crc_drop
stream_crc_valid:
    ldi     r30, 0
    ldi     r31, 1
    rjmp    L1bf6
stream_crc_drop:
    rjmp    stream_drop
stream_eop_overflow:
    rjmp    stream_drop
stream_eop_index:
    mov     r24, r25
    subi    r19, 11
    neg     r19
    sub     r28, r19
    out     T88_IO_PCIFR, r22
    mov     r16, r26
    cpi     r16, 0x4b
    breq    stream_eop_index_data
    cpi     r16, 0xc3
    brne    stream_eop_nondata
stream_eop_index_data:
    ldi     r31, STREAM_CRC_TABLE_HIGH_PAGE
    lpm     r25, Z
    ldi     r31, STREAM_CRC_TABLE_LOW_PAGE
    lpm     r30, Z
    eor     r30, r24
    rjmp    stream_crc_compare
stream_eop_nondata:
    ldi     r30, 0
    ldi     r31, 1
    rjmp    stream_nondata_dispatch
stream_eop_low:
    subi    r19, 11
    neg     r19
    sub     r28, r19
    out     T88_IO_PCIFR, r22
    mov     r16, r26
    cpi     r16, 0x4b
    breq    stream_eop_low_data
    cpi     r16, 0xc3
    brne    stream_eop_nondata
stream_eop_low_data:
    ldi     r31, STREAM_CRC_TABLE_LOW_PAGE
    lpm     r30, Z
    eor     r30, r24
    rjmp    stream_crc_compare
stream_eop_finish:
    subi    r19, 11
    neg     r19
    sub     r28, r19
    out     T88_IO_PCIFR, r22
    mov     r16, r26
    cpi     r16, 0x4b
    breq    stream_eop_finish_data
    cpi     r16, 0xc3
    brne    stream_eop_nondata
stream_eop_finish_data:
    eor     r30, r24
    rjmp    stream_crc_compare
L1ba2:
    sbi     T88_IO_PCIFR, T88_USB_PIN_CHANGE_FLAG
stream_drop:
L1ba6:
    ldi     r30, 0
    ldi     r31, 1
    std     Z+CTX_TX_ACK_WINDOW, r1
    clr     r16
    rjmp    L1be4
