/* Control transfer EP0 dispatcher and TX payload assembly.
   Included at original location to preserve relative branch encodings. */
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
    /* A damaged SETUP must not reset EP0 state or dispatch a command.
       The PHY has already selected its handshake; this application gate
       protects command fields but does not fix premature USB ACK. */
    ldi     r23, 8
    rcall   block_verify_rx_crc
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
    /* Tail dispatch instead of RCALL + RJMP: the DATA OUT parser
       returns directly to the common EP0 path. */
    rjmp    block_accept_out

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
    ldd     r18, Y+57
    cpi     r18, ST_FLASH_WAIT_PREP
    brne    L1e64
    ldi     r18, ST_SPM_WAIT_SENT
    std     Y+57, r18

