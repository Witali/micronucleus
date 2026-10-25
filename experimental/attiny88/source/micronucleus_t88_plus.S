/* Micronucleus ATtiny88 16 MHz ASM + EEPROM + bounded Flash read.
 * BASED ON Optimized Micronucleus t88_default 16 MHz ATtiny88 bootloader, pass 3.
 * Assembler reconstruction of public Micronucleus firmware with conservative code-size
 * SRAM pointer reuse in V-USB with cycle-neutral sync-stage initialization.
 * RX/TX sampler and sender timings preserved by cycle tests; CRC-16 unchanged.
 * Labels describe control flow; source/label-map.csv records historical names and purposes.
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
    /* Removed 0x1a80: rjmp    startup_check_sram_end (size-optimized, see CHANGES.md) */

/* Clear the next byte in the bootloader SRAM context. */
startup_clear_sram_byte:
    st      X+, r1

/* Repeat SRAM clearing until X reaches 0x012C. */
startup_check_sram_end:
    cpi     r26, 0x2c
    /* Removed 0x1a86: cpc     r27, r18 (size-optimized, see CHANGES.md) */
    brbc    1, startup_clear_sram_byte
    rjmp    main

usb_crc16_append:
    movw    r26, r24
    ldi     r24, 0x00
    ldi     r25, 0x00
    ldi     r20, 0x01
    ldi     r21, 0xa0
    com     r22
    ldi     r19, 0x00
    rjmp    usb_crc16_check_remaining_bytes

/* Read a byte and mix it into the CRC accumulator. */
usb_crc16_next_byte:
    ld      r18, X+
    eor     r24, r18

/* Shift the CRC and conditionally apply polynomial 0xA001. */
usb_crc16_shift_bit:
    ror     r25
    ror     r24
    brbs    0, usb_crc16_advance_bit_count
    eor     r24, r20
    eor     r25, r21

/* Advance the packed eight-bit CRC loop counter. */
usb_crc16_advance_bit_count:
    subi    r19, 0xe0
    brbs    0, usb_crc16_shift_bit

/* Process remaining bytes or append the two CRC bytes. */
usb_crc16_check_remaining_bytes:
    subi    r22, 0xff
    brbs    0, usb_crc16_next_byte
    st      X+, r24
    st      X+, r25
    ret

USB_handler:
    push    r28
    push    r29
    eor     r28, r28

/* Wait for the USB J state with a bounded sync counter. */
usb_rx_wait_for_j:
    inc     r28
    sbis    0x9, 1
    brbc    1, usb_rx_wait_for_j

/* Sample for the next J-to-K sync transition. */
usb_rx_wait_for_k:
    sbis    0x9, 1
    rjmp    usb_rx_found_k
    sbis    0x9, 1
    rjmp    usb_rx_found_k
    sbis    0x9, 1
    rjmp    usb_rx_found_k
    sbis    0x9, 1
    rjmp    usb_rx_found_k
    sbis    0x9, 1
    rjmp    usb_rx_found_k
    sbis    0x9, 1
    rjmp    usb_rx_found_k
    rjmp    usb_handler_return

/* Prepare the receive pointer and test for two consecutive K bits. */
usb_rx_found_k:
    push    r0
    lds     r28, 0x010e
    eor     r29, r29
    subi    r28, 0xea
    sbci    r29, 0xfe
    pop     r0
    ldi     r22, 0x55
    sbis    0x9, 1
    rjmp    usb_rx_sync_confirmed
    push    r0
    pop     r0
    rjmp    usb_rx_wait_for_k

/* Initialize receive state while preserving the first-bit sample phase. */
usb_rx_sync_confirmed:
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
    rjmp    usb_rx_sample_odd_bit

/* Handle stuffing detected at receive bit 6 and adjust the timing accumulator. */
usb_rx_unstuff_bit6:
    andi    r17, 0x06
    ori     r20, 0x40
    andi    r18, 0x7f
    mov     r16, r17
    subi    r21, 0xff
    rjmp    usb_rx_sample_bit7

/* Resample data bit 7 after a stuffed bit and adjust timing. */
usb_rx_unstuff_bit7:
    ori     r20, 0x80
    in      r17, 0x9
    andi    r17, 0x06
    andi    r18, 0x7f
    subi    r21, 0x02
    rjmp    usb_rx_finish_byte

/* Resample an even data bit and detect SE0. */
usb_rx_unstuff_even_bit:
    ori     r20, 0x40
    in      r16, 0x9
    andi    r18, 0x7f
    andi    r16, 0x06
    brbs    1, usb_rx_end_packet
    subi    r21, 0xff
    rjmp    usb_rx_unstuff_even_resume_jump

/* Keep the two-cycle jump into the even-bit resume path. */
usb_rx_unstuff_even_resume_jump:
    rjmp    usb_rx_shift_stuff_mask

/* Resample an odd data bit and detect SE0. */
usb_rx_unstuff_odd_bit:
    ori     r20, 0x20
    in      r17, 0x9
    andi    r18, 0x7f
    andi    r17, 0x06
    brbs    1, usb_rx_end_packet
    subi    r21, 0xff
    rjmp    usb_rx_unstuff_odd_resume_jump

/* Keep the two-cycle jump into the odd-bit resume path. */
usb_rx_unstuff_odd_resume_jump:
    rjmp    usb_rx_advance_bit_pair

/* Decode bit 6 and compensate fractional receive timing. */
usb_rx_decode_bit6:
    andi    r16, 0x06
    eor     r17, r16
    subi    r21, 0x01
    brbc    2, usb_rx_shift_bit6
    subi    r21, 0xfd
    nop

/* Shift the decoded bit-6 value into the receive register. */
usb_rx_shift_bit6:
    subi    r17, 0x01
    ror     r18

/* Sample bit 7 and check whether bit 6 required unstuffing. */
usb_rx_sample_bit7:
    cpi     r18, 0xfc
    in      r17, 0x9
    brbc    0, usb_rx_unstuff_bit6
    andi    r17, 0x06
    eor     r16, r17
    subi    r16, 0x01
    ror     r18

/* Check bit-7 stuffing and store the reconstructed byte. */
usb_rx_finish_byte:
    cpi     r18, 0xfc
    brbc    0, usb_rx_unstuff_bit7
    eor     r20, r18
    st      Y+, r20

/* Sample and decode data bit 0 or 2 or 4. */
usb_rx_sample_even_bit:
    in      r16, 0x9
    andi    r16, 0x06
    eor     r17, r16
    andi    r20, 0x3f
    subi    r17, 0x01
    ror     r18
    cpi     r18, 0xfc
    brbc    0, usb_rx_unstuff_even_bit

/* Advance the reconstruction mask after an even bit. */
usb_rx_shift_stuff_mask:
    lsr     r20
    lsr     r20

/* Sample and decode data bit 1 or 3 or 5 and detect SE0. */
usb_rx_sample_odd_bit:
    in      r17, 0x9
    andi    r17, 0x06
    brbs    1, usb_rx_end_packet
    eor     r16, r17
    subi    r16, 0x01
    ror     r18
    cpi     r18, 0xfc
    brbc    0, usb_rx_unstuff_odd_bit

/* Advance the receive bit-pair counter or finish the byte. */
usb_rx_advance_bit_pair:
    subi    r22, 0xab
    brbs    0, usb_rx_sample_even_bit
    subi    r19, 0x01
    in      r16, 0x9
    brbc    0, usb_rx_decode_bit6
    rjmp    usb_rx_overflow

/* Clear the pending USB edge after receive-buffer overflow. */
usb_rx_overflow:
    sbi     0x1b, 2  /* 2 cycles like original LDI+OUT; PCMSK0/1/3 remain 0 */

/* Discard an unsupported or misaddressed packet by clearing its token. */
usb_rx_ignore_packet:
    eor     r16, r16
    rjmp    usb_rx_store_token

/* Recover packet start after SE0 and dispatch its PID. */
usb_rx_end_packet:
    subi    r19, 0x0b
    neg     r19
    sub     r28, r19
    sbci    r29, 0x00
    sbi     0x1b, 2  /* 2 cycles like original LDI+OUT; PCMSK0/1/3 remain 0 */
    /* Z already initialized without added latency in usb_rx_sync_confirmed. */
    ldd     r16, Y+0
    cpi     r16, 0xc3
    brbs    1, usb_rx_handle_data
    cpi     r16, 0x4b
    brbs    1, usb_rx_handle_data
    ldd     r18, Z+12
    ldd     r17, Y+1
    add     r17, r17
    cpse    r17, r18
    rjmp    usb_rx_ignore_packet
    cpi     r16, 0x69
    brbs    1, usb_rx_handle_in
    cpi     r16, 0x2d
    brbs    1, usb_rx_handle_setup_or_out
    cpi     r16, 0xe1
    brbc    1, usb_rx_ignore_packet

/* Start waiting for the DATA packet following SETUP or OUT. */
usb_rx_handle_setup_or_out:
    ldi     r28, 0x0a

/* Wait for a pending USB edge or the short DATA timeout. */
usb_rx_wait_for_data:
    in      r17, 0x1b
    sbrc    r17, 2
    rjmp    usb_rx_store_token
    dec     r28
    brbc    1, usb_rx_wait_for_data

/* Publish the current token in the USB SRAM context. */
usb_rx_store_token:
    /* Z is guaranteed 0x0100 on every path reaching packet commit.
       STD Z+20 and STS 0x0114 each take two clocks; STD is 2 B shorter. */
    std     Z+20, r16

/* Restore the packet counter and receive another pending packet if needed. */
usb_handler_packet_done:
    pop     r19
    in      r28, 0x1b
    sbrc    r28, 2
    rjmp    usb_rx_wait_for_j

/* Restore Y and return from the polled USB handler. */
usb_handler_return:
    pop     r29
    pop     r28
    ret

/* Accept DATA0 or DATA1 or send NAK when the receive buffer is occupied. */
usb_rx_handle_data:
    ldd     r18, Z+20
    and     r18, r18
    brbs    1, usb_handler_packet_done
    ldd     r17, Z+18
    and     r17, r17
    brbc    1, usb_tx_send_nak
    cpi     r19, 0x04
    brbs    2, usb_tx_send_ack
    std     Z+18, r19
    std     Z+13, r18
    rjmp    usb_tx_send_ack

/* Choose queued endpoint-zero data or a handshake for an IN token. */
usb_rx_handle_in:
    ldd     r16, Z+18
    cpi     r16, 0x01
    brbc    4, usb_tx_send_nak
    ldi     r16, 0x5a
    ldd     r19, Z+15
    sbrc    r19, 4
    rjmp    usb_tx_send_count_handshake
    std     Z+15, r16
    ldi     r28, 0x01
    ldi     r29, 0x01
    rjmp    usb_tx_acquire_bus

/* Insert a stuffed zero during transmission of data bits 0 through 5. */
usb_tx_stuff_regular_bit:
    eor     r16, r21
    ldi     r17, 0x00
    rjmp    usb_tx_stuff_regular_delay

/* Preserve the stuffed-bit output timing before resuming transmission. */
usb_tx_stuff_regular_delay:
    nop
    out     0xb, r16
    rjmp    usb_tx_check_regular_stuffing

/* Handle the bit-6 stuffing path and compensate the shift register. */
usb_tx_stuff_bit6:
    eor     r16, r21
    ldi     r17, 0x00
    adc     r18, r18
    rjmp    usb_tx_send_bit6

/* Reset stuffing history and resume the bit-7 output path. */
usb_tx_stuff_bit7:
    ldi     r17, 0x00
    rjmp    usb_tx_send_bit7

/* Select the NAK handshake PID. */
usb_tx_send_nak:
    ldi     r20, 0x5a
    rjmp    usb_tx_prepare_handshake

/* Select the ACK handshake PID. */
usb_tx_send_ack:
    ldi     r19, 0xd2

/* Use the handshake PID already held in the packet counter. */
usb_tx_send_count_handshake:
    mov     r20, r19

/* Point Y at the handshake register and set the two-byte transmit count. */
usb_tx_prepare_handshake:
    ldi     r28, 0x14
    ldi     r29, 0x00
    ldi     r19, 0x02

/* Drive the USB pins and initialize NRZI transmission including SYNC. */
usb_tx_acquire_bus:
    in      r17, 0xa
    ori     r17, 0x06
    sbi     0xb, 1
    in      r16, 0xb
    out     0xa, r17
    ldi     r21, 0x06
    ldi     r18, 0x80

/* Initialize the packed transmit bit counter for the next byte. */
usb_tx_begin_byte:
    ldi     r22, 0x35

/* Emit the next NRZI bit for data bits 0 through 5. */
usb_tx_send_regular_bit:
    sbrs    r18, 0
    eor     r16, r21
    out     0xb, r16
    ror     r18
    ror     r17

/* Check the six-one history and advance the regular-bit loop. */
usb_tx_check_regular_stuffing:
    cpi     r17, 0xfc
    brbc    0, usb_tx_stuff_regular_bit
    lsr     r22
    brbc    0, usb_tx_send_regular_bit
    brbc    1, usb_tx_send_regular_bit
    sbrs    r18, 0
    eor     r16, r21

/* Emit data bit 6 and handle its stuffing history. */
usb_tx_send_bit6:
    out     0xb, r16
    ror     r18
    ror     r17
    cpi     r17, 0xfc
    brbc    0, usb_tx_stuff_bit6
    ror     r18

/* Emit data bit 7 and advance to the next byte or end of packet. */
usb_tx_send_bit7:
    ror     r17
    sbrs    r17, 7
    eor     r16, r21
    nop
    cpi     r17, 0xfc
    out     0xb, r16
    brbc    0, usb_tx_stuff_bit7
    ld      r18, Y+
    dec     r19
    brbc    1, usb_tx_begin_byte
    andi    r16, 0xf9
    ldd     r17, Z+19
    add     r17, r17
    subi    r28, 0x16
    sbci    r29, 0x00
    out     0xb, r16
    brbs    1, usb_tx_finish_eop
    std     Z+12, r17

/* Clear the TX-generated pending edge and prepare bus release after SE0. */
usb_tx_finish_eop:
    sbi     0x1b, 2  /* 2 cycles like original LDI+OUT; PCMSK0/1/3 remain 0 */
    ori     r16, 0x02
    in      r17, 0xa
    andi    r17, 0xf9
    mov     r20, r16
    andi    r20, 0xf9
    ldi     r21, 0x04

/* Hold the required end-of-packet interval before releasing the USB pins. */
usb_tx_eop_delay:
    dec     r21
    brbc    1, usb_tx_eop_delay
    out     0xb, r16
    out     0xa, r17
    out     0xb, r20
    rjmp    usb_handler_packet_done

/* Protect the RESET word then stage one word in the Flash page buffer. */
flash_buffer_append_word:
    movw    r30, r4
    sbiw    r30, 0
    brbc    1, flash_buffer_load_word
    ldi     r24, ((0xc000 + (BOOT_AT / 2) - 1) & 0xff)
    ldi     r25, ((0xc000 + (BOOT_AT / 2) - 1) >> 8)

/* Execute page-buffer SPM and advance the current address by two bytes. */
flash_buffer_load_word:
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

/* Reload the inner counter for the initial USB disconnect delay. */
usb_disconnect_delay_outer:
    ldi     r24, (63355 & 0xff)
    ldi     r25, (63355 >> 8)

/* Count down one inner USB disconnect delay interval. */
usb_disconnect_delay_inner:
    sbiw    r24, 1
    brne    usb_disconnect_delay_inner
    dec     r18
    brne    usb_disconnect_delay_outer
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

/* Initialize the five-millisecond USB poll and host-reset counters. */
bootloader_poll_begin:
    ldi     r28, 0xd5
    ldi     r29, 0x14
    ldi     r24, 0x64

/* Sample both USB lines and rearm reset detection outside SE0. */
usb_poll_sample_bus:
    in      r25, 0x9
    andi    r25, 0x06
    brbs    1, usb_poll_check_reset_duration
    ldi     r24, 0x64

/* Detect sustained SE0 and clear the active and pending USB addresses. */
usb_poll_check_reset_duration:
    subi    r24, 0x01
    brbc    1, usb_poll_check_packet_pending
    sts     0x0113, r1
    sts     0x010c, r1

/* Call the bit-level handler when a USB pin-change edge is pending. */
usb_poll_check_packet_pending:
    sbis    0x1b, 2
    rjmp    usb_poll_advance_timeout
    rcall   USB_handler
    sbi     0x1b, 2  /* PCIFR.PCIF2 W1C; reset PCMSK0/1/3 stay zero.
                        SBI is 2 cycles vs LDI+OUT 2 cycles. */

/* Service the watchdog and execute a queued application erase. */
bootloader_process_pending_command:
    wdr
    ldi     r18, 0x02
    cpse    r3, r18
    rjmp    bootloader_dispatch_command
    ldi     r30, (BOOT_AT & 0xff)
    ldi     r31, (BOOT_AT >> 8)

/* Erase application pages in reverse order down through page zero. */
flash_erase_application_page:
    subi    r30, 0x40
    sbc     r31, r1
    ldi     r24, 0x03
    out     0x37, r24     /* optimize: I/O address SPMCSR (0x57 - 0x20); 2 B vs 4 B */
    spm
    sbiw    r30, 0
    brbc    1, flash_erase_application_page
    movw    r4, r30 /* erase-loop exit implies Z=0, so R4:R5=0 */

/* Dispatch page commit or application exit while preserving pending work. */
bootloader_dispatch_command:
    mov     r24, r3
    cpi     r24, 0x40
    breq    flash_commit_buffered_page
    /* Fold command==4 and application-idle exit dispatch into the
       previous fallthrough. Both conditional targets are now nearby;
       the long-path RJMP trampoline is unnecessary. */
    cpi     r24, 0x04
    brne    bootloader_clear_command
    or      r28, r29
    brne    usb_control_process_received_packet
    rjmp    bootloader_start_application

/* Bounds-check and write the staged page using a page-aligned SPM address. */
flash_commit_buffered_page:
    movw    r30, r4
    sbiw    r30, 2
#if (BOOT_AT & 0xff) == 0
    cpi     r31, (BOOT_AT >> 8)    /* lower byte of boot boundary is 0: high compare sufficient for carry */
#else
    cpi     r30, (BOOT_AT & 0xff)
    ldi     r24, (BOOT_AT >> 8)
    cpc     r31, r24
#endif
    brbc    0, bootloader_clear_command
    andi    r30, 0xc0   /* AUDIT FIX: zero SPM Page Write PCWORD bits, 64-byte Flash page */
    ldi     r24, 0x05
    out     0x37, r24     /* optimize: I/O address SPMCSR (0x57 - 0x20); 2 B vs 4 B */
    spm

/* Clear the completed or unrecognized queued command. */
bootloader_clear_command:
    mov     r3, r1

/* Check the received payload and dispatch a complete eight-byte SETUP. */
usb_control_process_received_packet:
    /* Y=0x0100 is a base pointer for usbdrv SRAM globals during command/packet handling. */
    ldi     r28, 0x00
    ldi     r29, 0x01
    ldd     r24, Y+18
    subi    r24, 0x03
    brmi    usb_tx_prepare_pending_reply  /* N from SUBI equals previous r24 bit 7; same predicate */
    ldd     r25, Y+13
    cpi     r25, 0x2d
    brbc    1, usb_rx_release_buffer
    cpi     r24, 0x08
    brbc    1, usb_rx_release_buffer
    ldi     r24, 0xc3
    std     Y+1, r24
    ldi     r24, 0x5a
    std     Y+15, r24
    ldd     r24, Y+23
    andi    r24, 0x60
    ldd     r25, Y+24
    /* redundant AND r24,r24 removed: ANDI r24,0x60 already set same Z/N/V/S; LDD does not touch SREG */
    brbc    1, bootloader_handle_vendor_request
    rjmp    usb_dispatch_extended_or_standard_request

/* Refresh the idle timeout and handle device info or legacy Flash commands. */
bootloader_handle_vendor_request:
    mov     r7, r1
    cpse    r25, r1
    rjmp    bootloader_check_set_flash_address
    ldi     r24, ((BOOT_AT + 2) & 0xff)
    ldi     r25, ((BOOT_AT + 2) >> 8)
    std     Y+17, r25
    std     Y+16, r24
    ldi     r24, 0x08

/* Clamp the prepared reply length to the host-requested wLength. */
usb_reply_limit_length:
    ldd     r25, Y+30
    cpse    r25, r1
    rjmp    usb_reply_store_length
    ldd     r25, Y+29
    cp      r25, r24
    brbc    0, usb_reply_store_length
    mov     r24, r25

/* Publish the number of remaining control-reply bytes. */
usb_reply_store_length:
    std     Y+0, r24

/* Mark the received packet buffer available for the next packet. */
usb_rx_release_buffer:
    std     Y+18, r1

/* Build a control-IN block when TX is idle and reply bytes remain. */
usb_tx_prepare_pending_reply:
    ldd     r24, Y+15
    sbrs    r24, 4
    rjmp    bootloader_check_idle_timeout
    ldd     r24, Y+0
    cpi     r24, 0xff
    brbs    1, bootloader_check_idle_timeout
    mov     r23, r24
    cpi     r24, 0x09
    brbs    0, usb_tx_prepare_data_packet
    ldi     r23, 0x08

/* Update remaining length and toggle DATA0 or DATA1 for the next block. */
usb_tx_prepare_data_packet:
    mov     r25, r24
    sub     r25, r23
    std     Y+0, r25
    ldd     r25, Y+1
    ldi     r18, 0x88
    eor     r25, r18
    std     Y+1, r25
    and     r24, r24
    brbs    1, usb_tx_append_payload_crc
    ldd     r30, Y+16
    ldd     r31, Y+17
    ldi     r26, 0x02
    ldi     r27, 0x01
    mov     r24, r23

/* Copy reply bytes from Flash to the endpoint-zero transmit buffer. */
usb_tx_copy_flash_payload:
    lpm     r25, Z+  /* same read and advance; LPM Rd,Z+ supported on tiny88 */
    st      X+, r25
    subi    r24, 0x01
    brbc    1, usb_tx_copy_flash_payload
    std     Y+17, r31
    std     Y+16, r30

/* Append CRC16 and mark the end of a short control reply. */
usb_tx_append_payload_crc:
    mov     r22, r23
    ldi     r24, 0x02
    ldi     r25, 0x01
    rcall   usb_crc16_append
    subi    r23, 0xfc
    cpi     r23, 0x0c
    brbs    1, usb_tx_publish_packet_length
    ldi     r24, 0xff
    std     Y+0, r24

/* Publish the prepared TX block length including protocol overhead. */
usb_tx_publish_packet_length:
    std     Y+15, r23

/* Increment idle polls and start the application at timeout if present. */
bootloader_check_idle_timeout:
    movw    r24, r6
    adiw    r24, 1
    movw    r6, r24
    /* r24:r25 is a disposable copy of r6:r7 here. SUBI/SBCI
       reproduce CPI/CPC zero flag exactly (including Z propagation). */
    subi    r24, 0xb0
    sbci    r25, 0x04
    brbc    1, usb_poll_resynchronize
    ldi     r30, ((BOOT_AT - 3) & 0xff)
    ldi     r31, ((BOOT_AT - 3) >> 8)
    lpm     r30, Z
    cpi     r30, 0xff
    brbc    1, bootloader_start_application

/* Enter the post-poll resynchronization path with LED code omitted. */
usb_poll_resynchronize:
    /* Removed 0x1e7c: andi    r24, 0x4c (size-optimized, see CHANGES.md) */
    /* Removed 0x1e7e: brbc    1, legacy_led_off_anchor (size-optimized, see CHANGES.md) */
    /* Removed 0x1e80: rjmp    legacy_led_on_anchor (size-optimized, see CHANGES.md) */

/* Retain a zero-byte anchor where the removed LED-off code used to be. */
legacy_led_off_anchor:
    /* Removed 0x1e82: cbi     0xb, 0 (size-optimized, see CHANGES.md) */

/* Check whether USB traffic arrived during command and reply processing. */
usb_poll_check_missed_packet:
    sbis    0x1b, 2
    rjmp    bootloader_poll_begin
    ldi     r24, 0x1c

/* Wait for a quiet USB interval before accepting the next packet. */
usb_poll_wait_for_idle:
    sbis    0x9, 1
    ldi     r24, 0x1c
    subi    r24, 0x01
    brbc    1, usb_poll_wait_for_idle
    sbi     0x1b, 2  /* PCIFR.PCIF2 W1C; reset PCMSK0/1/3 stay zero.
                        SBI is 2 cycles vs LDI+OUT 2 cycles. */
    rjmp    bootloader_poll_begin

/* Continue the bus-poll loop until its timeout expires. */
usb_poll_advance_timeout:
    sbiw    r28, 1
    brbs    1, bootloader_poll_timeout
    rjmp    usb_poll_sample_bus

/* Continue with queued commands after the bus-poll timeout. */
bootloader_poll_timeout:
    rjmp    bootloader_process_pending_command

/* Release USB and preserve reset flags before jumping to the application. */
bootloader_start_application:
    /* Removed 0x1eac: cbi     0xb, 0 (size-optimized, see CHANGES.md) */
    out     0xa, r1
    sts     0x0068, r1
    sts     0x006d, r1
    in      r24, 0x34
    out     0x1e, r24
    out     0x34, r1
app_jump:
    .word (0xc000 | (((bootloader_start - 4 - app_jump - 2)/2) & 0x0fff)) /* relative RJMP into application postscript */

/* Recognize the legacy page-transfer command and check the current address. */
bootloader_check_set_flash_address:
    cpi     r25, 0x01
    brbc    1, bootloader_check_write_flash_word_pair
    cp      r4, r1
    cpc     r5, r1
    brbs    1, usb_reply_empty

/* Load the requested page address and clear the temporary page buffer. */
flash_set_address_and_clear_buffer:
    ldd     r24, Y+27
    andi    r24, 0xc0
    mov     r4, r24
    ldd     r5, Y+28
    ldi     r24, 0x11
    out     0x37, r24
    spm


/* Return a zero-length control reply through the common length limiter. */
usb_reply_empty:
    ldi     r24, 0x00
    rjmp    usb_reply_limit_length

/* Recognize the four-byte Flash-data request and queue full-page commits. */
bootloader_check_write_flash_word_pair:
    cpi     r25, 0x03
    brbc    1, bootloader_queue_command
    ldd     r24, Y+25
    ldd     r25, Y+26
    rcall   flash_buffer_append_word
    ldd     r24, Y+27
    ldd     r25, Y+28
    rcall   flash_buffer_append_word
    mov     r24, r4
    andi    r24, 0x3f
    brbc    1, usb_reply_empty
    ldi     r25, 0x40
    mov     r3, r25
    rjmp    usb_reply_limit_length

/* Store the low six request bits as a deferred bootloader command. */
bootloader_queue_command:
    andi    r25, 0x3f
    mov     r3, r25
    rjmp    usb_reply_empty

/* Check EEPROM and Flash extensions before the standard-request fallback. */
usb_dispatch_extended_or_standard_request:
    /* Vendor IN (bmRequestType=0xC0) EEPROM + Flash read extension.
       0xA0 EEPROM read byte, 0xB0 FLASH read 1..8 byte, 0xC0 EEPROM write, 0xF0 RDY/BSY.
       Feature bits in GET_INFO[6] 0x40 for EEPROM and 0x80 for Flash Read.
       Request fields: wValue = EEPROM address, wIndex low = data (write).
       USB protocol extends (NOT replaces) original ISP SPI opcode semantics.
       All new commands return 1 byte via EP0 control-IN; WRITE returns status.
       Non-EEPROM requests retain old Micronucleus dispatch unchanged. */
    ldd     r24, Y+23
    cpi     r24, 0xc0
    brne    usb_standard_dispatch
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

/* Handle standard endpoint-zero requests after the extension checks. */
usb_standard_dispatch:
    ldd     r18, Y+25
    std     Y+10, r1
    cpse    r25, r1
    rjmp    usb_standard_check_set_address
    std     Y+11, r1
    ldi     r24, 0x02                        /* USB reply: number of bytes */
/* Select the shared response scratch buffer at SRAM 0x010A. */
usb_reply_use_scratch_buffer:
    ldi     r18, 0x0a                        /* repeated 16-bit pointer low */
    ldi     r19, 0x01                        /* repeated 16-bit pointer high */
/* Store the prepared response pointer and continue with length limiting. */
usb_reply_set_pointer:
    std     Y+17, r19                       /* send pointer high */
    std     Y+16, r18                       /* send pointer low */
    rjmp    usb_reply_limit_length

/* Handle SET_ADDRESS or continue standard-request dispatch. */
usb_standard_check_set_address:
    cpi     r25, 0x05
    brbc    1, usb_standard_check_get_descriptor
    std     Y+19, r18
    rjmp    usb_reply_use_scratch_buffer                           /* preserve fallthrough semantics */

/* Choose the device or configuration descriptor for GET_DESCRIPTOR. */
usb_standard_check_get_descriptor:
    cpi     r25, 0x06
    brbc    1, usb_standard_check_configuration
    ldd     r24, Y+26
    ldi     r18, ((BOOT_AT + 0x1c) & 0xff)
    cpi     r24, 0x01
    breq    desc_ptr
    cpi     r24, 0x02
    brne    usb_reply_empty
    ldi     r18, ((BOOT_AT + 0x0a) & 0xff)

desc_ptr:
    /* Both descriptors are in the same 256-byte Flash window. */
    ldi     r19, ((BOOT_AT + 0x0a) >> 8)
    ldi     r24, 0x12
    rjmp    usb_reply_set_pointer

/* Dispatch GET_CONFIGURATION and SET_CONFIGURATION. */
usb_standard_check_configuration:
    cpi     r25, 0x08
    brbs    1, usb_standard_get_configuration
    cpi     r25, 0x09
    brbc    1, usb_standard_check_get_interface
    std     Y+21, r18
    rjmp    usb_reply_use_scratch_buffer

/* Return the default interface byte or an empty unsupported-request reply. */
usb_standard_check_get_interface:
    ldi     r24, 0x01
    cpi     r25, 0x0a
    brbs    1, usb_reply_use_scratch_buffer
    ldi     r24, 0x00
    rjmp    usb_reply_use_scratch_buffer

/* Prepare a one-byte reply pointing at the current USB configuration. */
usb_standard_get_configuration:
    ldi     r18, 0x15
    ldi     r19, 0x01
    ldi     r24, 0x01

/* Jump to the common response-pointer stores after configuration setup. */
usb_reply_pointer_trampoline:
    rjmp    usb_reply_set_pointer

/* Retain a zero-byte anchor where the removed LED-on code used to be. */
legacy_led_on_anchor:
    /* Removed 0x1f82: sbi     0xb, 0 (size-optimized, see CHANGES.md) */
    /* Removed 0x1f84: rjmp    usb_poll_check_missed_packet (size-optimized, see CHANGES.md) */

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
    rjmp    usb_reply_empty      /* zero length, no EEPROM access */

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
    rjmp    usb_reply_use_scratch_buffer

/* ---------------- Read user application Flash ---------------------------
 * Request 0xB0 vendor IN; wValue=byte address, wIndex=0, wLength=1..8.
 * No new buffer: set normal usbMsgPtr to requested Flash address and hand
 * off to Micronucleus' existing descriptor-data sender, usb_reply_limit_length.
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
    /* Reuse two pointer stores in usb_reply_set_pointer. The extra RJMP consumes two
       cycles outside the low-level USB sampling/transmit path. */
    rjmp    usb_reply_set_pointer

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

