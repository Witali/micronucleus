/* Assembler INCLUDE fragment: keep instruction order and cycles unchanged.
   The PHY and CRC cycle counts are compared byte for byte with Pass 10. */
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
    sbi     T88_IO_PCIFR, 2  /* 2 cycles like original LDI+OUT; PCMSK0/1/3 remain 0 */

L1ba6:
    eor     r16, r16
    rjmp    L1be4

L1baa:
    subi    r19, 0x0b
    neg     r19
    sub     r28, r19
    sbci    r29, 0x00
    sbi     T88_IO_PCIFR, 2  /* 2 cycles like original LDI+OUT; PCMSK0/1/3 remain 0 */
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
    sbic    T88_IO_PCIFR, 2
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
    out     T88_IO_PORTD, r16
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
    sbi     T88_IO_PORTD, 1
    in      r16, 0xb
    out     T88_IO_DDRD, r17
    ldi     r21, 0x06
    ldi     r18, 0x80

L1c64:
    ldi     r22, 0x35

L1c66:
    sbrs    r18, 0
    eor     r16, r21
    out     T88_IO_PORTD, r16
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
    out     T88_IO_PORTD, r16
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
    out     T88_IO_PORTD, r16
    brbc    0, L1c44
    ld      r18, Y+
    dec     r19
    brbc    1, L1c64
    andi    r16, 0xf9
    ldd     r17, Z+19
    add     r17, r17
    subi    r28, 0x16
    sbci    r29, 0x00
    out     T88_IO_PORTD, r16
    brbs    1, L1cb2
    std     Z+12, r17

L1cb2:
    sbi     T88_IO_PCIFR, 2  /* 2 cycles like original LDI+OUT; PCMSK0/1/3 remain 0 */
    ori     r16, 0x02
    in      r17, 0xa
    andi    r17, 0xf9
    mov     r20, r16
    andi    r20, 0xf9
    ldi     r21, 0x04

L1cc2:
    dec     r21
    brbc    1, L1cc2
    out     T88_IO_PORTD, r16
    out     T88_IO_DDRD, r17
    out     T88_IO_PORTD, r20
    rjmp    L1be8

