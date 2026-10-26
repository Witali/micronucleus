/* Experimental 16 MHz streaming RX CRC sampler. Not production validated.
 * Derived from V-USB 18 MHz CRC receive architecture and maintained t88 PHY.
 * GPL-2.0-or-later; original V-USB contributor notices remain in upstream.
 * Tables: low page 0x16, high page 0x17; must match wrapper placement.
 * CRC stages: bit4 finalize/index, bit5 high LPM, bit6 low LPM.
 * Normal bit periods: 11,9,12/13,9,11,11,11,11 = 85/86 clocks.
 * SE0 checks at bit0/bit2 cover ordinary EOP and one/two-bit dribble;
 * longer dribble and all stuffed/SE0 overlaps require independent tests.
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
    ldi     r27, 0xff
    ldi     r30, 0x54
    ldi     r25, 0xfe
    nop

stream_pid_bit0:
    in      r16, T88_IO_PIND
    eor     r17, r16
    bst     r17, 1
    bld     r18, 0
    rjmp    stream_pid_delay_0_4
stream_pid_delay_0_4:
    rjmp    stream_pid_delay_0_6
stream_pid_delay_0_6:
    rjmp    stream_pid_delay_0_8
stream_pid_delay_0_8:
    nop
stream_pid_bit1:
    in      r17, T88_IO_PIND
    mov     r26, r17
    andi    r26, 6
    breq    stream_pid_drop
    eor     r16, r17
    bst     r16, 1
    bld     r18, 1
    rjmp    stream_pid_delay_1_7
stream_pid_delay_1_7:
    nop
stream_pid_bit2:
    in      r16, T88_IO_PIND
    eor     r17, r16
    bst     r17, 1
    bld     r18, 2
    rjmp    stream_pid_delay_2_4
stream_pid_delay_2_4:
    rjmp    stream_pid_delay_2_6
stream_pid_delay_2_6:
    rjmp    stream_pid_delay_2_8
stream_pid_delay_2_8:
    nop
stream_pid_bit3:
    in      r17, T88_IO_PIND
    mov     r26, r17
    andi    r26, 6
    breq    stream_pid_drop
    eor     r16, r17
    bst     r16, 1
    bld     r18, 3
    rjmp    stream_pid_delay_3_7
stream_pid_delay_3_7:
    rjmp    stream_pid_delay_3_9
stream_pid_delay_3_9:
stream_pid_bit4:
    in      r16, T88_IO_PIND
    eor     r17, r16
    bst     r17, 1
    bld     r18, 4
    rjmp    stream_pid_delay_4_4
stream_pid_delay_4_4:
    rjmp    stream_pid_delay_4_6
stream_pid_delay_4_6:
    rjmp    stream_pid_delay_4_8
stream_pid_delay_4_8:
stream_pid_bit5:
    in      r17, T88_IO_PIND
    mov     r26, r17
    andi    r26, 6
    breq    stream_pid_drop
    eor     r16, r17
    bst     r16, 1
    bld     r18, 5
    rjmp    stream_pid_delay_5_7
stream_pid_delay_5_7:
    rjmp    stream_pid_delay_5_9
stream_pid_delay_5_9:
stream_pid_bit6:
    in      r16, T88_IO_PIND
    eor     r17, r16
    bst     r17, 1
    bld     r18, 6
    rjmp    stream_pid_delay_6_4
stream_pid_delay_6_4:
    rjmp    stream_pid_delay_6_6
stream_pid_delay_6_6:
    rjmp    stream_pid_delay_6_8
stream_pid_delay_6_8:
    ldi     r22, 4
stream_pid_bit7:
    in      r17, T88_IO_PIND
    eor     r16, r17
    bst     r16, 1
    bld     r18, 7
    mov     r20, r18
    com     r20
    mov     r24, r20
    mov     r26, r20
    rjmp    stream_bit0

stream_pid_drop:
    rjmp    stream_drop

/* These two out-of-line handlers precede bit4 for branch reach. */
stream_stuff4:
    ori     r18, 0x10
    andi    r27, 0xef
stream_stuff4_sample:
    in      r17, T88_IO_PIND
    subi    r21, 0xff
    eor     r16, r17
    andi    r16, 6
    breq    stream_drop_near46
    mov     r16, r17
    rjmp    stream_after4
stream_stuff6:
    ori     r18, 0x40
    andi    r27, 0xbf
stream_stuff6_sample:
    in      r17, T88_IO_PIND
    subi    r21, 0xff
    eor     r16, r17
    andi    r16, 6
    breq    stream_drop_near46
    mov     r16, r17
    rjmp    stream_after6
stream_drop_near46:
    rjmp    stream_drop

stream_bit4:
    in      r16, T88_IO_PIND
    ldi     r31, STREAM_CRC_TABLE_HIGH_PAGE
    eor     r17, r16
    bst     r17, 1
    bld     r18, 4
    mov     r17, r18
    andi    r17, 0x9f
    breq    stream_stuff4
stream_after4:
    eor     r30, r24
    mov     r24, r25
    eor     r30, r20
stream_bit5:
    in      r17, T88_IO_PIND
    eor     r16, r17
    bst     r16, 1
    bld     r18, 5
    mov     r16, r18
    andi    r16, 0x3f
    brne    stream_after5
stream_stuff5:
    ori     r18, 0x20
    andi    r27, 0xdf
    subi    r21, 0xff
    nop
stream_stuff5_sample:
    in      r16, T88_IO_PIND
    eor     r17, r16
    andi    r17, 6
    breq    stream_drop_near46
    mov     r17, r16
    nop
    rjmp    stream_after5
stream_after5:
    lpm     r25, Z
stream_bit6:
    in      r16, T88_IO_PIND
    ldi     r31, STREAM_CRC_TABLE_LOW_PAGE
    eor     r17, r16
    bst     r17, 1
    bld     r18, 6
    mov     r17, r18
    andi    r17, 0x7e
    breq    stream_stuff6
stream_after6:
    lpm     r30, Z
stream_bit7:
    in      r17, T88_IO_PIND
    eor     r16, r17
    bst     r16, 1
    bld     r18, 7
    mov     r16, r18
    andi    r16, 0xfc
    brne    stream_after7
stream_stuff7:
    ori     r18, 0x80
    andi    r27, 0x7f
    subi    r21, 2
stream_stuff7_sample:
    in      r16, T88_IO_PIND
    eor     r17, r16
    andi    r17, 6
    breq    stream_drop_near03
    mov     r17, r16
    nop
    rjmp    stream_after7
stream_after7:
    eor     r27, r18
    mov     r20, r27
    ldi     r27, 0xff
stream_bit0:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_eop_before_store
    eor     r17, r16
    bst     r17, 1
    bld     r18, 0
    mov     r17, r18
    andi    r17, 0xf9
    breq    stream_stuff0
stream_after0:
    subi    r19, 1
    brcs    stream_drop_near03
stream_bit1:
    in      r17, T88_IO_PIND
    /* Store the preceding byte after this sample, not before it. This moves
       bit1 sampling two clocks earlier without changing later sample times. */
    st      Y+, r20
    eor     r16, r17
    bst     r16, 1
    bld     r18, 1
    mov     r16, r18
    andi    r16, 0xf3
    breq    stream_stuff1
stream_bit2:
    in      r16, T88_IO_PIND
    andi    r16, 6
    breq    stream_eop_after_store
    eor     r17, r16
    bst     r17, 1
    bld     r18, 2
    mov     r17, r18
    andi    r17, 0xe7
    breq    stream_stuff2
stream_after2:
    subi    r21, 1
    brpl    stream_phase_done
    subi    r21, 0xfd
    nop
stream_phase_done:
stream_bit3:
    in      r17, T88_IO_PIND
    eor     r16, r17
    bst     r16, 1
    bld     r18, 3
    mov     r16, r18
    andi    r16, 0xcf
    breq    stream_stuff3
stream_after3:
    rjmp    stream_bit4

stream_eop_before_store:
    rjmp    stream_eop_finish_store
stream_eop_after_store:
    rjmp    stream_eop
stream_drop_near03:
    rjmp    stream_drop
stream_stuff0:
    ori     r18, 1
stream_stuff0_sample:
    in      r17, T88_IO_PIND
    andi    r27, 0xfe
    subi    r21, 0xff
    eor     r16, r17
    andi    r16, 6
    breq    stream_drop_near03
    mov     r16, r17
    rjmp    stream_after0
stream_stuff1:
    ori     r18, 2
stream_stuff1_sample:
    in      r16, T88_IO_PIND
    andi    r27, 0xfd
    subi    r21, 0xff
    eor     r17, r16
    andi    r17, 6
    breq    stream_drop_near03
    mov     r17, r16
    rjmp    stream_bit2
stream_stuff2:
    ori     r18, 4
stream_stuff2_sample:
    in      r17, T88_IO_PIND
    andi    r27, 0xfb
    subi    r21, 0xff
    eor     r16, r17
    andi    r16, 6
    breq    stream_drop_near03
    mov     r16, r17
    rjmp    stream_after2
stream_stuff3:
    ori     r18, 8
    andi    r27, 0xf7
    subi    r21, 0xff
stream_stuff3_sample:
    in      r16, T88_IO_PIND
    eor     r17, r16
    andi    r17, 6
    breq    stream_drop_near03
    mov     r17, r16
    rjmp    stream_after3

stream_eop_finish_store:
    subi    r19, 1
    brcs    stream_drop
    st      Y+, r20
stream_eop:
    /* Account complete bytes once for both DATA and non-DATA paths.
       RX base 0x0116 plus <=11 bytes cannot wrap YL, so YH stays one. */
    subi    r19, 11
    neg     r19
    sub     r28, r19
    out     T88_IO_PCIFR, r22   /* R22=4 was installed in PID padding. */
    mov     r16, r26             /* Full PID shadow installed in PID padding. */
    /* The PID is excluded by the delayed seed R24=PID,R25=FE,ZL=54. */
    cpi     r16, 0x4b
    breq    stream_eop_data
    cpi     r16, 0xc3
    breq    stream_eop_data
    ldi     r30, 0
    ldi     r31, 1
    rjmp    stream_nondata_dispatch
stream_eop_data:
    /* Complete pending byte N-1, then feed the final latched CRC byte N. */
    eor     r30, r24
    mov     r24, r25
    eor     r30, r20
    ldi     r31, STREAM_CRC_TABLE_HIGH_PAGE
    lpm     r25, Z
    ldi     r31, STREAM_CRC_TABLE_LOW_PAGE
    lpm     r30, Z
    eor     r30, r24
    cpi     r30, 0x01
    brne    stream_crc_drop
    cpi     r25, 0xb0
    brne    stream_crc_drop
stream_crc_valid:
    /* Both DATA identity and CRC are proven; common length accounting is
       already complete. Do not repeat generic token/PID classification. */
    ldi     r30, 0
    ldi     r31, 1
    rjmp    L1bf6
stream_crc_drop:
    rjmp    stream_drop
L1ba2:
    sbi     T88_IO_PCIFR, T88_USB_PIN_CHANGE_FLAG
stream_drop:
L1ba6:
    ldi     r30, 0
    ldi     r31, 1
    std     Z+CTX_TX_ACK_WINDOW, r1
    clr     r16
    rjmp    L1be4
