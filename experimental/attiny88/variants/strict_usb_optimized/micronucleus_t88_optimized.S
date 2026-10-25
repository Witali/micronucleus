/* Strict USB size-optimization candidate: ATtiny88, 16 MHz, EEPROM/Flash read.
 * BASED ON Optimized Micronucleus t88_default 16 MHz ATtiny88 bootloader, pass 3.
 * Assembler reconstruction of public Micronucleus firmware with conservative code-size
 * SRAM pointer reuse in V-USB with cycle-neutral sync-stage initialization.
 * RX/TX sampler and sender timings preserved by cycle tests; CRC-16 unchanged.
 * Labels describe control flow; source/label-map.csv records historical names and purposes.
 * Original Micronucleus contributors and modifications: GPL-2.0-or-later.
 */
/* Official register/bit names and memory geometry; see the pinned provenance. */
#include <avr/io.h>
#include "../strict_usb_verified/led_config.h"
#include "../strict_usb_verified/led_macros.inc"

#ifndef BOOT_AT
#define BOOT_AT 0x1ac0
#endif

/* Byte extraction and AVR instruction encoding. */
#define LOW8(value)  ((value) & 0xff)
#define HIGH8(value) (((value) >> 8) & 0xff)
#define AVR_WORD_BYTES 2
#define AVR_RJMP_OPCODE 0xc000
#define AVR_RJMP_OFFSET_MASK 0x0fff

/* Fixed ATtiny88 layout. The official C header uses byte-addressed sizes. */
#define FLASH_PAGE_BYTES SPM_PAGESIZE
#define FLASH_PAGE_OFFSET_MASK (FLASH_PAGE_BYTES - 1)
#define FLASH_PAGE_ALIGN_MASK (0xff ^ FLASH_PAGE_OFFSET_MASK)
#define EEPROM_BYTES (E2END + 1)
#define FLASH_ERASED_BYTE 0xff
#define POSTSCRIPT_BYTES 4
#define APP_LIMIT (BOOT_AT - POSTSCRIPT_BYTES)

/* Wiring and self-programming commands, using official bit definitions. */
#define USB_MINUS_BIT PD1
#define USB_PLUS_BIT PD2
#define USB_LINE_MASK ((1 << USB_MINUS_BIT) | (1 << USB_PLUS_BIT))
#define USB_LINES_CLEAR_MASK (0xff ^ USB_LINE_MASK)
#define USB_INTERRUPT_ENABLE_MASK (1 << PCINT18) /* Also PCIE2, both bit 2. */
#define WATCHDOG_UNLOCK_MASK ((1 << WDCE) | (1 << WDE))
#define SPM_BUFFER_LOAD (1 << SELFPRGEN)
#define SPM_PAGE_ERASE ((1 << PGERS) | SPM_BUFFER_LOAD)
#define SPM_PAGE_WRITE ((1 << PGWRT) | SPM_BUFFER_LOAD)
#define SPM_BUFFER_CLEAR ((1 << CTPB) | SPM_BUFFER_LOAD)

/* USB global SRAM layout, offsets from RAMSTART (0x0100). */
#define USB_CONTEXT_BASE RAMSTART
#define USB_CONTEXT_BYTES 44
#define CTX_MSG_LENGTH 0
#define CTX_TX_PID 1
#define CTX_TX_PAYLOAD 2
#define CTX_REPLY_SCRATCH 10
#define CTX_REPLY_SCRATCH_HIGH 11
#define CTX_DEVICE_ADDRESS 12
#define CTX_RX_TOKEN 13
#define CTX_INPUT_BUFFER_OFFSET 14
#define CTX_TX_LENGTH 15
#define CTX_MSG_POINTER_LOW 16
#define CTX_MSG_POINTER_HIGH 17
#define CTX_RX_LENGTH 18
#define CTX_NEW_DEVICE_ADDRESS 19
#define CTX_CURRENT_TOKEN 20
#define CTX_CONFIGURATION 21
#define CTX_RX_BUFFER 22
#define CTX_SETUP_REQUEST_TYPE 23
#define CTX_SETUP_REQUEST 24
#define CTX_SETUP_VALUE_LOW 25
#define CTX_SETUP_VALUE_HIGH 26
#define CTX_SETUP_INDEX_LOW 27
#define CTX_SETUP_INDEX_HIGH 28
#define CTX_SETUP_LENGTH_LOW 29
#define CTX_SETUP_LENGTH_HIGH 30
#define USB_PACKET_PID_OFFSET 0
#define USB_PACKET_ADDRESS_OFFSET 1

/* USB packet IDs, control requests and packet lengths. */
#define USB_PID_DATA0 0xc3
#define USB_PID_DATA1 0x4b
#define USB_PID_IN 0x69
#define USB_PID_SETUP 0x2d
#define USB_PID_OUT 0xe1
#define USB_PID_ACK 0xd2
#define USB_PID_NAK 0x5a
#define USB_DATA_PID_TOGGLE (USB_PID_DATA0 ^ USB_PID_DATA1)
#define USB_REQUEST_TYPE_MASK 0x60
#define USB_REQUEST_VENDOR_IN 0xc0
#define USB_REQ_GET_STATUS 0
#define USB_REQ_SET_ADDRESS 5
#define USB_REQ_GET_DESCRIPTOR 6
#define USB_REQ_GET_CONFIGURATION 8
#define USB_REQ_SET_CONFIGURATION 9
#define USB_REQ_GET_INTERFACE 10
#define USB_STATUS_REPLY_BYTES 2
#define USB_SETUP_BYTES 8
#define USB_EP0_PAYLOAD_BYTES 8
#define USB_RX_PACKET_OVERHEAD 3 /* PID + two CRC bytes. */
#define USB_TX_PACKET_OVERHEAD 4 /* SYNC + PID + two CRC bytes. */
#define USB_RX_BUFFER_BYTES (USB_EP0_PAYLOAD_BYTES + USB_RX_PACKET_OVERHEAD)
#define USB_FULL_TX_PACKET_BYTES (USB_EP0_PAYLOAD_BYTES + USB_TX_PACKET_OVERHEAD)
#define USB_NO_MESSAGE 0xff
#define USB_HANDSHAKE_FLAG_BIT 4
#define USB_HANDSHAKE_REGISTER 20 /* Register-file byte address of r20. */
#define USB_HANDSHAKE_TX_BYTES 2
#define USB_HANDSHAKE_END_POINTER (USB_HANDSHAKE_REGISTER + USB_HANDSHAKE_TX_BYTES)
#define USB_SYNC_BYTE 0x80

/* Flash-resident device info and standard USB descriptors. */
#define BOOT_INFO_OFFSET AVR_WORD_BYTES
#define BOOT_INFO_BYTES 8
#define BOOT_FEATURE_RESET_FLAGS 0x20
#define BOOT_FEATURE_EEPROM 0x40
#define BOOT_FEATURE_FLASH_READ 0x80
#define BOOT_FEATURES (BOOT_FEATURE_RESET_FLAGS | BOOT_FEATURE_EEPROM | BOOT_FEATURE_FLASH_READ)
#define FLASH_WRITE_DELAY_MS 5
#define USB_PROTOCOL_BCD 0x0110
#define BOOT_VERSION_BCD 0x0208
#define USB_VENDOR_ID 0x16d0
#define USB_PRODUCT_ID 0x0753
#define USB_DESCRIPTOR_DEVICE 1
#define USB_DESCRIPTOR_CONFIGURATION 2
#define USB_DESCRIPTOR_INTERFACE 4
#define USB_CONFIGURATION_HEADER_BYTES 9
#define USB_INTERFACE_DESCRIPTOR_BYTES 9
#define USB_CONFIGURATION_TOTAL_BYTES (USB_CONFIGURATION_HEADER_BYTES + USB_INTERFACE_DESCRIPTOR_BYTES)
#define USB_DEVICE_DESCRIPTOR_BYTES 18
#define USB_CONFIGURATION_OFFSET (BOOT_INFO_OFFSET + BOOT_INFO_BYTES)
#define USB_DEVICE_DESCRIPTOR_OFFSET (USB_CONFIGURATION_OFFSET + USB_CONFIGURATION_TOTAL_BYTES)
#define USB_CLASS_VENDOR_SPECIFIC 0xff
#define USB_CONFIGURATION_ATTRIBUTES 0x80
#define USB_MAX_POWER_MA 100

/* Bootloader and extension request codes. */
#define CMD_SET_FLASH_ADDRESS 1
#define CMD_ERASE_APPLICATION 2
#define CMD_WRITE_WORD_PAIR 3
#define CMD_EXIT 4
#define CMD_COMMIT_PAGE 0x40
#define CMD_DEFERRED_MASK 0x3f
#define REQ_EEPROM_READ 0xa0
#define REQ_FLASH_READ 0xb0
#define REQ_EEPROM_WRITE 0xc0
#define REQ_READY_STATUS 0xf0
#define STATUS_ACCEPTED 0
#define STATUS_BUSY 1
#define STATUS_INVALID_PARAMETER 2
#define FLASH_READ_MAX_BYTES USB_EP0_PAYLOAD_BYTES

/* Fixed 16 MHz timing. These are audited loop/encoding constants, not knobs. */
#define CPU_CLOCK_HZ 16000000
#define BOOT_POLL_INTERVAL_MS 5
#define USB_POLL_LOOP_CYCLES 15
#define USB_POLL_TIMEOUT_COUNT ((CPU_CLOCK_HZ / 1000) * BOOT_POLL_INTERVAL_MS / USB_POLL_LOOP_CYCLES)
#define BOOT_AUTO_EXIT_MS 6000
#define BOOT_IDLE_TIMEOUT_POLLS (BOOT_AUTO_EXIT_MS / BOOT_POLL_INTERVAL_MS)
#define USB_DISCONNECT_OUTER_LOOPS 19
#define USB_DISCONNECT_INNER_LOOPS 63355
#define USB_RESET_SE0_SAMPLES 100
#define USB_RESYNC_IDLE_SAMPLES 28
#define USB_NEXT_DATA_WAIT_COUNT 10
#define USB_EOP_DELAY_LOOPS 4

/* CRC and cycle-sensitive NRZI/stuffing encodings from the 16 MHz engine. */
#define CRC16_POLYNOMIAL 0xa001
#define CRC_BIT_COUNTER_INCREMENT 32 /* Carry every eight additions. */
#define USB_STUFF_HISTORY_THRESHOLD 0xfc
#define USB_RX_INITIAL_STUFF_MASK 0x10
#define USB_RX_CORRECTION_BIT5_MASK (1 << 5)
#define USB_RX_CORRECTION_BIT6_MASK (1 << 6)
#define USB_RX_CORRECTION_BIT7_MASK (1 << 7)
#define USB_RX_CLEAR_HIGH_BIT_MASK 0x7f
#define USB_RX_LOW_BITS_MASK 0x3f
#define USB_RX_PAIR_COUNTER_INCREMENT 0x55
#define USB_RX_LEAP_PERIOD 3
#define USB_RX_UNSTUFF7_LEAP_ADJUST 2
#define USB_TX_BIT_COUNTER_SEED 0x35


#if PCINT18 != PCIE2
#error The reused PCMSK2 and PCICR enable mask requires identical bit positions
#endif
#if LOW8(APP_LIMIT) < FLASH_READ_MAX_BYTES
#error Optimized Flash range check requires no borrow in APP_LIMIT low byte minus length
#endif
#if HIGH8(BOOT_AT + USB_CONFIGURATION_OFFSET) != HIGH8(BOOT_AT + USB_DEVICE_DESCRIPTOR_OFFSET)
#error USB descriptor pointers cross a 256-byte page; adjust optimized dispatcher
#endif
.section .text
/* Edit BOOT_AT only after the build audits that the loader fits in flash. */
.org BOOT_AT
.global bootloader_start
bootloader_start:
    rjmp startup
/* Device info: application size, page bytes, write delay, signature, features. */
    .byte HIGH8(APP_LIMIT), LOW8(APP_LIMIT), FLASH_PAGE_BYTES, FLASH_WRITE_DELAY_MS
    .byte SIGNATURE_1, SIGNATURE_2, BOOT_FEATURES, 0
/* Configuration descriptor followed by one interface and no extra endpoints. */
    .byte USB_CONFIGURATION_HEADER_BYTES, USB_DESCRIPTOR_CONFIGURATION
    .byte LOW8(USB_CONFIGURATION_TOTAL_BYTES), HIGH8(USB_CONFIGURATION_TOTAL_BYTES)
    .byte 1, 1, 0, USB_CONFIGURATION_ATTRIBUTES, (USB_MAX_POWER_MA / 2)
    .byte USB_INTERFACE_DESCRIPTOR_BYTES, USB_DESCRIPTOR_INTERFACE, 0, 0, 0, 0, 0, 0, 0
/* Device descriptor: USB version, class, EP0 size, VID/PID and loader version.
 * No string descriptors; one configuration. */
    .byte USB_DEVICE_DESCRIPTOR_BYTES, USB_DESCRIPTOR_DEVICE
    .byte LOW8(USB_PROTOCOL_BCD), HIGH8(USB_PROTOCOL_BCD), USB_CLASS_VENDOR_SPECIFIC, 0, 0, USB_EP0_PAYLOAD_BYTES
    .byte LOW8(USB_VENDOR_ID), HIGH8(USB_VENDOR_ID), LOW8(USB_PRODUCT_ID), HIGH8(USB_PRODUCT_ID)
    .byte LOW8(BOOT_VERSION_BCD), HIGH8(BOOT_VERSION_BCD), 0, 0, 0, 1

USB_handler:
    push    r28
    push    r29
    eor     r28, r28

/* Wait for the USB J state with a bounded sync counter. */
usb_rx_wait_for_j:
    inc     r28
    sbis    _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    brbc    SREG_Z, usb_rx_wait_for_j

/* Sample for the next J-to-K sync transition. */
usb_rx_wait_for_k:
    sbis    _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp    usb_rx_found_k
    sbis    _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp    usb_rx_found_k
    sbis    _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp    usb_rx_found_k
    sbis    _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp    usb_rx_found_k
    sbis    _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp    usb_rx_found_k
    sbis    _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    rjmp    usb_rx_found_k
    rjmp    usb_handler_return

/* Prepare the receive pointer and test for two consecutive K bits. */
usb_rx_found_k:
    push    r0
    lds     r28, (USB_CONTEXT_BASE + CTX_INPUT_BUFFER_OFFSET)
    eor     r29, r29
    subi    r28, LOW8(-(USB_CONTEXT_BASE + CTX_RX_BUFFER))
    sbci    r29, HIGH8(-(USB_CONTEXT_BASE + CTX_RX_BUFFER))
    pop     r0
    ldi     r22, USB_RX_PAIR_COUNTER_INCREMENT
    sbis    _SFR_IO_ADDR(PIND), USB_MINUS_BIT
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
    ldi     r30, LOW8(USB_CONTEXT_BASE)
    ldi     r31, HIGH8(USB_CONTEXT_BASE)
    rjmp    usb_rx_delay_complete
usb_rx_delay_complete:
    push    r16
    ldi     r18, 0x00
    ldi     r20, USB_RX_INITIAL_STUFF_MASK
    pop     r16
    in      r16, _SFR_IO_ADDR(PIND)
    andi    r16, USB_LINE_MASK
    bst     r16, USB_MINUS_BIT
    bld     r18, 7
    push    r19
    ldi     r21, 0x00
    ldi     r19, USB_RX_BUFFER_BYTES
    rjmp    usb_rx_sample_odd_bit

/* Handle stuffing detected at receive bit 6 and adjust the timing accumulator. */
usb_rx_unstuff_bit6:
    andi    r17, USB_LINE_MASK
    ori     r20, USB_RX_CORRECTION_BIT6_MASK
    andi    r18, USB_RX_CLEAR_HIGH_BIT_MASK
    mov     r16, r17
    subi    r21, LOW8(-1)
    rjmp    usb_rx_sample_bit7

/* Resample data bit 7 after a stuffed bit and adjust timing. */
usb_rx_unstuff_bit7:
    ori     r20, USB_RX_CORRECTION_BIT7_MASK
    in      r17, _SFR_IO_ADDR(PIND)
    andi    r17, USB_LINE_MASK
    andi    r18, USB_RX_CLEAR_HIGH_BIT_MASK
    subi    r21, USB_RX_UNSTUFF7_LEAP_ADJUST
    rjmp    usb_rx_finish_byte

/* Resample an even data bit and detect SE0. */
usb_rx_unstuff_even_bit:
    ori     r20, USB_RX_CORRECTION_BIT6_MASK
    in      r16, _SFR_IO_ADDR(PIND)
    andi    r18, USB_RX_CLEAR_HIGH_BIT_MASK
    andi    r16, USB_LINE_MASK
    brbs    SREG_Z, usb_rx_end_packet
    subi    r21, LOW8(-1)
    rjmp    usb_rx_unstuff_even_resume_jump

/* Keep the two-cycle jump into the even-bit resume path. */
usb_rx_unstuff_even_resume_jump:
    rjmp    usb_rx_shift_stuff_mask

/* Resample an odd data bit and detect SE0. */
usb_rx_unstuff_odd_bit:
    ori     r20, USB_RX_CORRECTION_BIT5_MASK
    in      r17, _SFR_IO_ADDR(PIND)
    andi    r18, USB_RX_CLEAR_HIGH_BIT_MASK
    andi    r17, USB_LINE_MASK
    brbs    SREG_Z, usb_rx_end_packet
    subi    r21, LOW8(-1)
    rjmp    usb_rx_unstuff_odd_resume_jump

/* Keep the two-cycle jump into the odd-bit resume path. */
usb_rx_unstuff_odd_resume_jump:
    rjmp    usb_rx_advance_bit_pair

/* Decode bit 6 and compensate fractional receive timing. */
usb_rx_decode_bit6:
    andi    r16, USB_LINE_MASK
    eor     r17, r16
    subi    r21, 0x01
    brbc    SREG_N, usb_rx_shift_bit6
    subi    r21, LOW8(-USB_RX_LEAP_PERIOD)
    nop

/* Shift the decoded bit-6 value into the receive register. */
usb_rx_shift_bit6:
    subi    r17, 0x01
    ror     r18

/* Sample bit 7 and check whether bit 6 required unstuffing. */
usb_rx_sample_bit7:
    cpi     r18, USB_STUFF_HISTORY_THRESHOLD
    in      r17, _SFR_IO_ADDR(PIND)
    brbc    SREG_C, usb_rx_unstuff_bit6
    andi    r17, USB_LINE_MASK
    eor     r16, r17
    subi    r16, 0x01
    ror     r18

/* Check bit-7 stuffing and store the reconstructed byte. */
usb_rx_finish_byte:
    cpi     r18, USB_STUFF_HISTORY_THRESHOLD
    brbc    SREG_C, usb_rx_unstuff_bit7
    eor     r20, r18
    st      Y+, r20

/* Sample and decode data bit 0 or 2 or 4. */
usb_rx_sample_even_bit:
    in      r16, _SFR_IO_ADDR(PIND)
    andi    r16, USB_LINE_MASK
    eor     r17, r16
    andi    r20, USB_RX_LOW_BITS_MASK
    subi    r17, 0x01
    ror     r18
    cpi     r18, USB_STUFF_HISTORY_THRESHOLD
    brbc    SREG_C, usb_rx_unstuff_even_bit

/* Advance the reconstruction mask after an even bit. */
usb_rx_shift_stuff_mask:
    lsr     r20
    lsr     r20

/* Sample and decode data bit 1 or 3 or 5 and detect SE0. */
usb_rx_sample_odd_bit:
    in      r17, _SFR_IO_ADDR(PIND)
    andi    r17, USB_LINE_MASK
    brbs    SREG_Z, usb_rx_end_packet
    eor     r16, r17
    subi    r16, 0x01
    ror     r18
    cpi     r18, USB_STUFF_HISTORY_THRESHOLD
    brbc    SREG_C, usb_rx_unstuff_odd_bit

/* Advance the receive bit-pair counter or finish the byte. */
usb_rx_advance_bit_pair:
    subi    r22, LOW8(-USB_RX_PAIR_COUNTER_INCREMENT)
    brbs    SREG_C, usb_rx_sample_even_bit
    subi    r19, 0x01
    in      r16, _SFR_IO_ADDR(PIND)
    brbc    SREG_C, usb_rx_decode_bit6
    rjmp    usb_rx_overflow

/* Clear the pending USB edge after receive-buffer overflow. */
usb_rx_overflow:
    sbi     _SFR_IO_ADDR(PCIFR), PCIF2 /* W1C; same two cycles as LDI+OUT. */

/* Discard an unsupported or misaddressed packet by clearing its token. */
usb_rx_ignore_packet:
    eor     r16, r16
    rjmp    usb_rx_store_token

/* Recover packet start after SE0 and dispatch its PID. */
usb_rx_end_packet:
    subi    r19, USB_RX_BUFFER_BYTES
    neg     r19
    sub     r28, r19
    sbci    r29, 0x00
    sbi     _SFR_IO_ADDR(PCIFR), PCIF2
    /* Z already initialized without added latency in usb_rx_sync_confirmed. */
    ldd     r16, Y+USB_PACKET_PID_OFFSET
    cpi     r16, USB_PID_DATA0
    brbs    SREG_Z, usb_rx_handle_data
    cpi     r16, USB_PID_DATA1
    brbs    SREG_Z, usb_rx_handle_data
    ldd     r18, Z+CTX_DEVICE_ADDRESS
    ldd     r17, Y+USB_PACKET_ADDRESS_OFFSET
    add     r17, r17
    cpse    r17, r18
    rjmp    usb_rx_ignore_packet
    cpi     r16, USB_PID_IN
    brbs    SREG_Z, usb_rx_handle_in
    cpi     r16, USB_PID_SETUP
    brbs    SREG_Z, usb_rx_handle_setup_or_out
    cpi     r16, USB_PID_OUT
    brbc    SREG_Z, usb_rx_ignore_packet

/* Start waiting for the DATA packet following SETUP or OUT. */
usb_rx_handle_setup_or_out:
    ldi     r28, USB_NEXT_DATA_WAIT_COUNT

/* Wait for a pending USB edge or the short DATA timeout. */
usb_rx_wait_for_data:
    in      r17, _SFR_IO_ADDR(PCIFR)
    sbrc    r17, PCIF2
    rjmp    usb_rx_store_token
    dec     r28
    brbc    SREG_Z, usb_rx_wait_for_data

/* Publish the current token in the USB SRAM context. */
usb_rx_store_token:
    /* Sync initialization proves Z == USB_CONTEXT_BASE on every path.
       STD and the former direct STS both take two cycles. */
    std     Z+CTX_CURRENT_TOKEN, r16

/* Restore the packet counter and receive another pending packet if needed. */
usb_handler_packet_done:
    pop     r19
    in      r28, _SFR_IO_ADDR(PCIFR)
    sbrc    r28, PCIF2
    rjmp    usb_rx_wait_for_j

/* Restore Y and return from the polled USB handler. */
usb_handler_return:
    pop     r29
    pop     r28
    ret

/* Accept DATA0 or DATA1 or send NAK when the receive buffer is occupied. */
usb_rx_handle_data:
    ldd     r18, Z+CTX_CURRENT_TOKEN
    and     r18, r18
    brbs    SREG_Z, usb_handler_packet_done
    ldd     r17, Z+CTX_RX_LENGTH
    and     r17, r17
    brbc    SREG_Z, usb_tx_send_nak
    cpi     r19, (USB_RX_PACKET_OVERHEAD + 1)
    brbs    SREG_N, usb_tx_send_ack
    std     Z+CTX_RX_LENGTH, r19
    std     Z+CTX_RX_TOKEN, r18
    rjmp    usb_tx_send_ack

/* Choose queued endpoint-zero data or a handshake for an IN token. */
usb_rx_handle_in:
    ldd     r16, Z+CTX_RX_LENGTH
    cpi     r16, 0x01
    brbc    SREG_S, usb_tx_send_nak
    ldi     r16, USB_PID_NAK
    ldd     r19, Z+CTX_TX_LENGTH
    sbrc    r19, USB_HANDSHAKE_FLAG_BIT
    rjmp    usb_tx_send_count_handshake
    std     Z+CTX_TX_LENGTH, r16
    ldi     r28, LOW8(USB_CONTEXT_BASE + CTX_TX_PID)
    ldi     r29, HIGH8(USB_CONTEXT_BASE + CTX_TX_PID)
    rjmp    usb_tx_acquire_bus

/* Insert a stuffed zero during transmission of data bits 0 through 5. */
usb_tx_stuff_regular_bit:
    eor     r16, r21
    ldi     r17, 0x00
    rjmp    usb_tx_stuff_regular_delay

/* Preserve the stuffed-bit output timing before resuming transmission. */
usb_tx_stuff_regular_delay:
    nop
    out     _SFR_IO_ADDR(PORTD), r16
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
    ldi     r20, USB_PID_NAK
    rjmp    usb_tx_prepare_handshake

/* Select the ACK handshake PID. */
usb_tx_send_ack:
    ldi     r19, USB_PID_ACK

/* Use the handshake PID already held in the packet counter. */
usb_tx_send_count_handshake:
    mov     r20, r19

/* Point Y at the handshake register and set the two-byte transmit count. */
usb_tx_prepare_handshake:
    ldi     r28, LOW8(USB_HANDSHAKE_REGISTER)
    ldi     r29, HIGH8(USB_HANDSHAKE_REGISTER)
    ldi     r19, USB_HANDSHAKE_TX_BYTES

/* Drive the USB pins and initialize NRZI transmission including SYNC. */
usb_tx_acquire_bus:
    in      r17, _SFR_IO_ADDR(DDRD)
    ori     r17, USB_LINE_MASK
    sbi     _SFR_IO_ADDR(PORTD), USB_MINUS_BIT
    in      r16, _SFR_IO_ADDR(PORTD)
    out     _SFR_IO_ADDR(DDRD), r17
    ldi     r21, USB_LINE_MASK
    ldi     r18, USB_SYNC_BYTE

/* Initialize the packed transmit bit counter for the next byte. */
usb_tx_begin_byte:
    ldi     r22, USB_TX_BIT_COUNTER_SEED

/* Emit the next NRZI bit for data bits 0 through 5. */
usb_tx_send_regular_bit:
    sbrs    r18, 0
    eor     r16, r21
    out     _SFR_IO_ADDR(PORTD), r16
    ror     r18
    ror     r17

/* Check the six-one history and advance the regular-bit loop. */
usb_tx_check_regular_stuffing:
    cpi     r17, USB_STUFF_HISTORY_THRESHOLD
    brbc    SREG_C, usb_tx_stuff_regular_bit
    lsr     r22
    brbc    SREG_C, usb_tx_send_regular_bit
    brbc    SREG_Z, usb_tx_send_regular_bit
    sbrs    r18, 0
    eor     r16, r21

/* Emit data bit 6 and handle its stuffing history. */
usb_tx_send_bit6:
    out     _SFR_IO_ADDR(PORTD), r16
    ror     r18
    ror     r17
    cpi     r17, USB_STUFF_HISTORY_THRESHOLD
    brbc    SREG_C, usb_tx_stuff_bit6
    ror     r18

/* Emit data bit 7 and advance to the next byte or end of packet. */
usb_tx_send_bit7:
    ror     r17
    sbrs    r17, 7
    eor     r16, r21
    nop
    cpi     r17, USB_STUFF_HISTORY_THRESHOLD
    out     _SFR_IO_ADDR(PORTD), r16
    brbc    SREG_C, usb_tx_stuff_bit7
    ld      r18, Y+
    dec     r19
    brbc    SREG_Z, usb_tx_begin_byte
    andi    r16, USB_LINES_CLEAR_MASK
    ldd     r17, Z+CTX_NEW_DEVICE_ADDRESS
    add     r17, r17
    subi    r28, USB_HANDSHAKE_END_POINTER
    sbci    r29, 0x00
    out     _SFR_IO_ADDR(PORTD), r16
    brbs    SREG_Z, usb_tx_finish_eop
    std     Z+CTX_DEVICE_ADDRESS, r17

/* Clear the TX-generated pending edge and prepare bus release after SE0. */
usb_tx_finish_eop:
    sbi     _SFR_IO_ADDR(PCIFR), PCIF2
    ori     r16, (1 << USB_MINUS_BIT)
    in      r17, _SFR_IO_ADDR(DDRD)
    andi    r17, USB_LINES_CLEAR_MASK
    mov     r20, r16
    andi    r20, USB_LINES_CLEAR_MASK
    ldi     r21, USB_EOP_DELAY_LOOPS

/* Hold the required end-of-packet interval before releasing the USB pins. */
usb_tx_eop_delay:
    dec     r21
    brbc    SREG_Z, usb_tx_eop_delay
    out     _SFR_IO_ADDR(PORTD), r16
    out     _SFR_IO_ADDR(DDRD), r17
    out     _SFR_IO_ADDR(PORTD), r20
    rjmp    usb_handler_packet_done

/* Protect the RESET word then stage one word in the Flash page buffer. */
flash_buffer_append_word:
    movw    r30, r4
    sbiw    r30, 0
    brbc    SREG_Z, flash_buffer_load_word
    ldi     r24, LOW8(AVR_RJMP_OPCODE + BOOT_AT / AVR_WORD_BYTES - 1)
    ldi     r25, HIGH8(AVR_RJMP_OPCODE + BOOT_AT / AVR_WORD_BYTES - 1)

/* Execute page-buffer SPM and advance the current address by two bytes. */
flash_buffer_load_word:
    ldi     r18, SPM_BUFFER_LOAD
    movw    r0, r24
    out     _SFR_IO_ADDR(SPMCSR), r18     /* optimize: I/O address SPMCSR (0x57 - 0x20); 2 B vs 4 B */
    spm
    eor     r1, r1
    adiw    r30, AVR_WORD_BYTES  /* update page fill pointer in Z; only callers overwrite r24 after return */
    movw    r4, r30
    ret

/* Startup now falls through into main; stack and SRAM setup are retained. */
startup:
    eor     r1, r1
    out     _SFR_IO_ADDR(SREG), r1
    ldi     r28, LOW8(RAMEND)
    ldi     r29, HIGH8(RAMEND)
    out     _SFR_IO_ADDR(SPL), r28
    out     _SFR_IO_ADDR(SPH), r29
    /* Removed 0x1a7a: ldi     r18, 0x01 (size-optimized, see CHANGES.md) */
    ldi     r26, LOW8(USB_CONTEXT_BASE)
    ldi     r27, HIGH8(USB_CONTEXT_BASE)
    /* Removed 0x1a80: rjmp    startup_check_sram_end (size-optimized, see CHANGES.md) */

/* Clear the next byte in the bootloader SRAM context. */
startup_clear_sram_byte:
    st      X+, r1

/* Repeat SRAM clearing until X reaches 0x012C. */
startup_check_sram_end:
    cpi     r26, LOW8(USB_CONTEXT_BASE + USB_CONTEXT_BYTES)
    /* Removed 0x1a86: cpc     r27, r18 (size-optimized, see CHANGES.md) */
    brbc    SREG_Z, startup_clear_sram_byte

main:
    wdr
    in      r24, _SFR_IO_ADDR(MCUSR)
    out     _SFR_IO_ADDR(GPIOR0), r24
    out     _SFR_IO_ADDR(MCUSR), r1
    /* WDT unlock: WDCE|WDE=0x18 is sufficient regardless of the
       previous prescaler and interrupt settings. Next store, immediately,
       clears WDE/WDCE; timed sequence is unchanged. Saves four bytes. */
    ldi     r24, WATCHDOG_UNLOCK_MASK
    sts     _SFR_MEM_ADDR(WDTCSR), r24
    sts     _SFR_MEM_ADDR(WDTCSR), r1
    sbi     _SFR_IO_ADDR(DDRD), USB_MINUS_BIT
    /* 300.94 ms initial USB disconnect: 19 x 63355 inner loops.
       Previous 3000 x 400 countdown cost 4,815,001 cycles;
       this takes 4,815,056 cycles at 16 MHz (difference 55 cycles),
       two bytes less while preserving the USB disconnect duration. */
    ldi     r18, USB_DISCONNECT_OUTER_LOOPS

/* Reload the inner counter for the initial USB disconnect delay. */
usb_disconnect_delay_outer:
    ldi     r24, LOW8(USB_DISCONNECT_INNER_LOOPS)
    ldi     r25, HIGH8(USB_DISCONNECT_INNER_LOOPS)

/* Count down one inner USB disconnect delay interval. */
usb_disconnect_delay_inner:
    sbiw    r24, 1
    brne    usb_disconnect_delay_inner
    dec     r18
    brne    usb_disconnect_delay_outer
    cbi     _SFR_IO_ADDR(DDRD), USB_MINUS_BIT
    /* The final SBIW leaves r24:r25 == 0. Initialize the Flash pointer
       after releasing USB so the disconnect duration stays unchanged. */
    movw    r4, r24
    ldi     r24, USB_PID_NAK
    sts     (USB_CONTEXT_BASE + CTX_TX_LENGTH), r24
    ldi     r24, USB_NO_MESSAGE
    sts     (USB_CONTEXT_BASE + CTX_MSG_LENGTH), r24
    /* After reset both PCMSK2 and PCICR are zero.  Only PCINT18 / PCIE2
       are required: direct writes avoid redundant read-modify-write. */
    ldi     r24, USB_INTERRUPT_ENABLE_MASK
    sts     _SFR_MEM_ADDR(PCMSK2), r24
    sts     _SFR_MEM_ADDR(PCICR), r24
led_init:
    LED_INIT
led_init_done:
    mov     r7, r1
    mov     r3, r1

/* Initialize the five-millisecond USB poll and host-reset counters. */
bootloader_poll_begin:
    ldi     r28, LOW8(USB_POLL_TIMEOUT_COUNT)
    ldi     r29, HIGH8(USB_POLL_TIMEOUT_COUNT)
    ldi     r24, USB_RESET_SE0_SAMPLES

/* Sample both USB lines and rearm reset detection outside SE0. */
usb_poll_sample_bus:
    in      r25, _SFR_IO_ADDR(PIND)
    andi    r25, USB_LINE_MASK
    brbs    SREG_Z, usb_poll_check_reset_duration
    ldi     r24, USB_RESET_SE0_SAMPLES

/* Detect sustained SE0 and clear the active and pending USB addresses. */
usb_poll_check_reset_duration:
    subi    r24, 0x01
    brbc    SREG_Z, usb_poll_check_packet_pending
    sts     (USB_CONTEXT_BASE + CTX_NEW_DEVICE_ADDRESS), r1
    sts     (USB_CONTEXT_BASE + CTX_DEVICE_ADDRESS), r1

/* Call the bit-level handler when a USB pin-change edge is pending. */
usb_poll_check_packet_pending:
    sbis    _SFR_IO_ADDR(PCIFR), PCIF2
    rjmp    usb_poll_advance_timeout
    rcall   USB_handler
    sbi     _SFR_IO_ADDR(PCIFR), PCIF2  /* PCIFR.PCIF2 W1C; reset PCMSK0/1/3 stay zero.
                        SBI is 2 cycles vs LDI+OUT 2 cycles. */

/* Service the watchdog and execute a queued application erase. */
bootloader_process_pending_command:
    wdr
    ldi     r18, CMD_ERASE_APPLICATION
    cpse    r3, r18
    rjmp    bootloader_dispatch_command
    ldi     r30, LOW8(BOOT_AT)
    ldi     r31, HIGH8(BOOT_AT)

/* Erase application pages in reverse order down through page zero. */
flash_erase_application_page:
    subi    r30, FLASH_PAGE_BYTES
    sbc     r31, r1
    ldi     r24, SPM_PAGE_ERASE
    out     _SFR_IO_ADDR(SPMCSR), r24     /* optimize: I/O address SPMCSR (0x57 - 0x20); 2 B vs 4 B */
    spm
    /* SUBI/SBC already report Z==0 for the full 16-bit page address.
       LDI, OUT and SPM preserve SREG; only Z is live at this branch. */
    brbc    SREG_Z, flash_erase_application_page
    movw    r4, r30 /* erase-loop exit implies Z=0, so R4:R5=0 */

/* Dispatch page commit or application exit while preserving pending work. */
bootloader_dispatch_command:
    mov     r24, r3
    cpi     r24, CMD_COMMIT_PAGE
    breq    flash_commit_buffered_page
    /* Fold command==4 and application-idle exit dispatch into the
       previous fallthrough. Both conditional targets are now nearby;
       the long-path RJMP trampoline is unnecessary. */
    cpi     r24, CMD_EXIT
    brne    bootloader_clear_command
    or      r28, r29
    brne    usb_control_process_received_packet
    rjmp    bootloader_start_application

/* Bounds-check and write the staged page using a page-aligned SPM address. */
flash_commit_buffered_page:
    movw    r30, r4
    sbiw    r30, AVR_WORD_BYTES
#if LOW8(BOOT_AT) == 0
    cpi     r31, HIGH8(BOOT_AT)    /* lower byte of boot boundary is 0: high compare sufficient for carry */
#else
    cpi     r30, LOW8(BOOT_AT)
    ldi     r24, HIGH8(BOOT_AT)
    cpc     r31, r24
#endif
    brbc    SREG_C, bootloader_clear_command
    andi    r30, FLASH_PAGE_ALIGN_MASK   /* AUDIT FIX: zero SPM Page Write PCWORD bits, 64-byte Flash page */
    ldi     r24, SPM_PAGE_WRITE
    out     _SFR_IO_ADDR(SPMCSR), r24     /* optimize: I/O address SPMCSR (0x57 - 0x20); 2 B vs 4 B */
    spm

/* Clear the completed or unrecognized queued command. */
bootloader_clear_command:
    mov     r3, r1

/* Check the received payload and dispatch a complete eight-byte SETUP. */
usb_control_process_received_packet:
    /* Y=0x0100 is a base pointer for usbdrv SRAM globals during command/packet handling. */
    ldi     r28, LOW8(USB_CONTEXT_BASE)
    ldi     r29, HIGH8(USB_CONTEXT_BASE)
    ldd     r24, Y+CTX_RX_LENGTH
    /* Only a complete SETUP may dispatch a memory command. Zero length
       also releases the already-empty buffer; all malformed lengths drop. */
    cpi     r24, (USB_SETUP_BYTES + USB_RX_PACKET_OVERHEAD)
    brne    usb_rx_release_buffer
    ldd     r25, Y+CTX_RX_TOKEN
    cpi     r25, USB_PID_SETUP
    brbc    SREG_Z, usb_rx_release_buffer
    ldi     r24, USB_PID_DATA0
    std     Y+CTX_TX_PID, r24
    ldi     r24, USB_PID_NAK
    std     Y+CTX_TX_LENGTH, r24
    mov     r2, r1    /* New SETUP defaults to Flash replies. */
    ldd     r24, Y+CTX_SETUP_REQUEST_TYPE
    andi    r24, USB_REQUEST_TYPE_MASK
    ldd     r25, Y+CTX_SETUP_REQUEST
    /* redundant AND r24,r24 removed: ANDI r24,0x60 already set same Z/N/V/S; LDD does not touch SREG */
    brbc    SREG_Z, bootloader_handle_vendor_request
    rjmp    usb_dispatch_extended_or_standard_request

/* Refresh the idle timeout and handle device info or legacy Flash commands. */
bootloader_handle_vendor_request:
    mov     r7, r1
    cpi     r25, REQ_EEPROM_READ
    brlo    bootloader_legacy_vendor_request
    rjmp    usb_dispatch_extended_or_standard_request
bootloader_legacy_vendor_request:
    cpse    r25, r1
    rjmp    bootloader_check_set_flash_address
    ldi     r18, LOW8(BOOT_AT + BOOT_INFO_OFFSET)
    ldi     r19, HIGH8(BOOT_AT + BOOT_INFO_OFFSET)
    ldi     r24, BOOT_INFO_BYTES
    rjmp    usb_reply_set_pointer

/* Select the shared response scratch buffer at SRAM 0x010A. */
usb_reply_use_scratch_buffer:
    ldi     r18, LOW8(USB_CONTEXT_BASE + CTX_REPLY_SCRATCH)                        /* repeated 16-bit pointer low */
    ldi     r19, HIGH8(USB_CONTEXT_BASE + CTX_REPLY_SCRATCH)
    mov     r2, r19    /* Shared scratch response is SRAM. */
/* Store the prepared response pointer and continue with length limiting. */
usb_reply_set_pointer:
    std     Y+CTX_MSG_POINTER_HIGH, r19                       /* send pointer high */
    std     Y+CTX_MSG_POINTER_LOW, r18                       /* send pointer low */


/* Clamp the prepared reply length to the host-requested wLength. */
usb_reply_limit_length:
    ldd     r25, Y+CTX_SETUP_LENGTH_HIGH
    cpse    r25, r1
    rjmp    usb_reply_store_length
    ldd     r25, Y+CTX_SETUP_LENGTH_LOW
    cp      r25, r24
    brbc    SREG_C, usb_reply_store_length
    mov     r24, r25

/* Publish the number of remaining control-reply bytes. */
usb_reply_store_length:
    std     Y+CTX_MSG_LENGTH, r24

/* Mark the received packet buffer available for the next packet. */
usb_rx_release_buffer:
    std     Y+CTX_RX_LENGTH, r1

/* Build a control-IN block when TX is idle and reply bytes remain. */
usb_tx_prepare_pending_reply:
    ldd     r24, Y+CTX_TX_LENGTH
    sbrs    r24, USB_HANDSHAKE_FLAG_BIT
    rjmp    bootloader_check_idle_timeout
    ldd     r24, Y+CTX_MSG_LENGTH
    cpi     r24, USB_NO_MESSAGE
    brbs    SREG_Z, bootloader_check_idle_timeout
    mov     r23, r24
    cpi     r24, (USB_EP0_PAYLOAD_BYTES + 1)
    brbs    SREG_C, usb_tx_prepare_data_packet
    ldi     r23, USB_EP0_PAYLOAD_BYTES

/* Update remaining length and toggle DATA0 or DATA1 for the next block. */
usb_tx_prepare_data_packet:
    mov     r25, r24
    sub     r25, r23
    std     Y+CTX_MSG_LENGTH, r25
    ldd     r25, Y+CTX_TX_PID
    ldi     r18, USB_DATA_PID_TOGGLE
    eor     r25, r18
    std     Y+CTX_TX_PID, r25
    and     r24, r24
    brbs    SREG_Z, usb_tx_append_payload_crc
    ldd     r30, Y+CTX_MSG_POINTER_LOW
    ldd     r31, Y+CTX_MSG_POINTER_HIGH
    ldi     r26, LOW8(USB_CONTEXT_BASE + CTX_TX_PAYLOAD)
    ldi     r27, HIGH8(USB_CONTEXT_BASE + CTX_TX_PAYLOAD)
    mov     r24, r23

/* Copy reply bytes from Flash to the endpoint-zero transmit buffer. */
usb_tx_copy_flash_payload:
    sbrc    r2, 0
    ld      r25, Z+
    sbrs    r2, 0
    lpm     r25, Z+
    st      X+, r25
    subi    r24, 0x01
    brbc    SREG_Z, usb_tx_copy_flash_payload
    std     Y+CTX_MSG_POINTER_HIGH, r31
    std     Y+CTX_MSG_POINTER_LOW, r30

/* Append CRC16 and mark the end of a short control reply. */
usb_tx_append_payload_crc:
    mov     r22, r23
    /* The inlined CRC consumes X directly; no ABI pointer copy is needed. */
    ldi     r26, LOW8(USB_CONTEXT_BASE + CTX_TX_PAYLOAD)
    ldi     r27, HIGH8(USB_CONTEXT_BASE + CTX_TX_PAYLOAD)
usb_crc16_append:
    ldi     r24, 0x00
    ldi     r25, 0x00
    ldi     r20, LOW8(CRC16_POLYNOMIAL)
    ldi     r21, HIGH8(CRC16_POLYNOMIAL)
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
    brbs    SREG_C, usb_crc16_advance_bit_count
    eor     r24, r20
    eor     r25, r21

/* Advance the packed eight-bit CRC loop counter. */
usb_crc16_advance_bit_count:
    subi    r19, LOW8(-CRC_BIT_COUNTER_INCREMENT)
    brbs    SREG_C, usb_crc16_shift_bit

/* Process remaining bytes or append the two CRC bytes. */
usb_crc16_check_remaining_bytes:
    subi    r22, LOW8(-1)
    brbs    SREG_C, usb_crc16_next_byte
    st      X+, r24
    st      X+, r25
usb_crc16_core_end:
    subi    r23, LOW8(-USB_TX_PACKET_OVERHEAD)
    cpi     r23, USB_FULL_TX_PACKET_BYTES
    brbs    SREG_Z, usb_tx_publish_packet_length
    ldi     r24, USB_NO_MESSAGE
    std     Y+CTX_MSG_LENGTH, r24

/* Publish the prepared TX block length including protocol overhead. */
usb_tx_publish_packet_length:
    std     Y+CTX_TX_LENGTH, r23

/* Increment idle polls and start the application at timeout if present. */
bootloader_check_idle_timeout:
    movw    r24, r6
    adiw    r24, 1
    movw    r6, r24
    /* r24:r25 is a disposable copy of r6:r7 here. SUBI/SBCI
       reproduce CPI/CPC zero flag exactly (including Z propagation). */
    subi    r24, LOW8(BOOT_IDLE_TIMEOUT_POLLS)
    sbci    r25, HIGH8(BOOT_IDLE_TIMEOUT_POLLS)
    brbc    SREG_Z, usb_poll_resynchronize
    ldi     r30, LOW8(APP_LIMIT + 1)
    ldi     r31, HIGH8(APP_LIMIT + 1)
    lpm     r30, Z
    cpi     r30, FLASH_ERASED_BYTE
    brbc    SREG_Z, bootloader_start_application

/* Enter the post-poll resynchronization path with LED code omitted. */
usb_poll_resynchronize:
led_tick:
    LED_TICK
led_tick_done:
    /* Removed 0x1e7c: andi    r24, 0x4c (size-optimized, see CHANGES.md) */
    /* Removed 0x1e7e: brbc    1, legacy_led_off_anchor (size-optimized, see CHANGES.md) */
    /* Removed 0x1e80: rjmp    legacy_led_on_anchor (size-optimized, see CHANGES.md) */

/* Retain a zero-byte anchor where the removed LED-off code used to be. */
legacy_led_off_anchor:
    /* Removed 0x1e82: cbi     0xb, 0 (size-optimized, see CHANGES.md) */

/* Check whether USB traffic arrived during command and reply processing. */
usb_poll_check_missed_packet:
    sbis    _SFR_IO_ADDR(PCIFR), PCIF2
    rjmp    bootloader_poll_begin
    ldi     r24, USB_RESYNC_IDLE_SAMPLES

/* Wait for a quiet USB interval before accepting the next packet. */
usb_poll_wait_for_idle:
    sbis    _SFR_IO_ADDR(PIND), USB_MINUS_BIT
    ldi     r24, USB_RESYNC_IDLE_SAMPLES
    subi    r24, 0x01
    brbc    SREG_Z, usb_poll_wait_for_idle
    sbi     _SFR_IO_ADDR(PCIFR), PCIF2  /* PCIFR.PCIF2 W1C; reset PCMSK0/1/3 stay zero.
                        SBI is 2 cycles vs LDI+OUT 2 cycles. */
    rjmp    bootloader_poll_begin

/* Continue the bus-poll loop until its timeout expires. */
usb_poll_advance_timeout:
    sbiw    r28, 1
    brbs    SREG_Z, bootloader_poll_timeout
    rjmp    usb_poll_sample_bus

/* Continue with queued commands after the bus-poll timeout. */
bootloader_poll_timeout:
    rjmp    bootloader_process_pending_command

/* Release USB and preserve reset flags before jumping to the application. */
bootloader_start_application:
led_exit:
#if LED_DDR_IO == 0x0a
    /* The following unconditional DDRD clear releases this LED too. */
#if LED_MODE == ACTIVE_HIGH
    cbi     LED_PORT_IO, LED_PIN
#endif
#else
    LED_EXIT
#endif
led_exit_done:
    /* Removed 0x1eac: cbi     0xb, 0 (size-optimized, see CHANGES.md) */
    out     _SFR_IO_ADDR(DDRD), r1
    sts     _SFR_MEM_ADDR(PCICR), r1
    sts     _SFR_MEM_ADDR(PCMSK2), r1
app_jump:
    .word (AVR_RJMP_OPCODE | (((bootloader_start - POSTSCRIPT_BYTES - app_jump - AVR_WORD_BYTES) / AVR_WORD_BYTES) & AVR_RJMP_OFFSET_MASK)) /* relative RJMP into application postscript */

/* Recognize the legacy page-transfer command and check the current address. */
bootloader_check_set_flash_address:
    cpi     r25, CMD_SET_FLASH_ADDRESS
    brbc    SREG_Z, bootloader_check_write_flash_word_pair
    cp      r4, r1
    cpc     r5, r1
    brbs    SREG_Z, usb_reply_empty

/* Load the requested page address and clear the temporary page buffer. */
flash_set_address_and_clear_buffer:
    ldd     r24, Y+CTX_SETUP_INDEX_LOW
    andi    r24, FLASH_PAGE_ALIGN_MASK
    mov     r4, r24
    ldd     r5, Y+CTX_SETUP_INDEX_HIGH
    ldi     r24, SPM_BUFFER_CLEAR
    out     _SFR_IO_ADDR(SPMCSR), r24
    spm


/* Return a zero-length control reply through the common length limiter. */
usb_reply_empty:
    ldi     r24, 0x00
    rjmp    usb_reply_limit_length

/* Recognize the four-byte Flash-data request and queue full-page commits. */
bootloader_check_write_flash_word_pair:
    cpi     r25, CMD_WRITE_WORD_PAIR
    brbc    SREG_Z, bootloader_queue_command
    ldd     r24, Y+CTX_SETUP_VALUE_LOW
    ldd     r25, Y+CTX_SETUP_VALUE_HIGH
    rcall   flash_buffer_append_word
    ldd     r24, Y+CTX_SETUP_INDEX_LOW
    ldd     r25, Y+CTX_SETUP_INDEX_HIGH
    rcall   flash_buffer_append_word
    mov     r24, r4
    andi    r24, FLASH_PAGE_OFFSET_MASK
    brbc    SREG_Z, usb_reply_empty
    ldi     r25, CMD_COMMIT_PAGE
    mov     r3, r25
    rjmp    usb_reply_limit_length

/* Store the low six request bits as a deferred bootloader command. */
bootloader_queue_command:
    andi    r25, CMD_DEFERRED_MASK
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
    ldd     r24, Y+CTX_SETUP_REQUEST_TYPE
    cpi     r24, USB_REQUEST_VENDOR_IN
    brne    usb_standard_dispatch
    cpi     r25, REQ_EEPROM_READ
    breq    ee_read

ee_check_flash:
    cpi     r25, REQ_FLASH_READ
    brne    ee_check_write
    rjmp    flash_read

ee_check_write:
    cpi     r25, REQ_EEPROM_WRITE
    breq    ee_write

ee_check_busy:
    cpi     r25, REQ_READY_STATUS
    breq    ee_ready

/* Handle standard endpoint-zero requests after the extension checks. */
usb_standard_dispatch:
    ldd     r18, Y+CTX_SETUP_VALUE_LOW
    std     Y+CTX_REPLY_SCRATCH, r1
    cpse    r25, r1
    rjmp    usb_standard_check_set_address
    std     Y+CTX_REPLY_SCRATCH_HIGH, r1
    ldi     r24, USB_STATUS_REPLY_BYTES      /* GET_STATUS reply length. */
    rjmp    usb_reply_use_scratch_buffer
/* Handle SET_ADDRESS or continue standard-request dispatch. */
usb_standard_check_set_address:
    cpi     r25, USB_REQ_SET_ADDRESS
    brbc    SREG_Z, usb_standard_check_get_descriptor
    std     Y+CTX_NEW_DEVICE_ADDRESS, r18
    rjmp    usb_reply_use_scratch_buffer                           /* preserve fallthrough semantics */

/* Choose the device or configuration descriptor for GET_DESCRIPTOR. */
usb_standard_check_get_descriptor:
    cpi     r25, USB_REQ_GET_DESCRIPTOR
    brbc    SREG_Z, usb_standard_check_configuration
    ldd     r24, Y+CTX_SETUP_VALUE_HIGH
    ldi     r18, LOW8(BOOT_AT + USB_DEVICE_DESCRIPTOR_OFFSET)
    cpi     r24, USB_DESCRIPTOR_DEVICE
    breq    desc_ptr
    cpi     r24, USB_DESCRIPTOR_CONFIGURATION
    brne    usb_reply_empty
    ldi     r18, LOW8(BOOT_AT + USB_CONFIGURATION_OFFSET)

desc_ptr:
    /* Both descriptors are in the same 256-byte Flash window. */
    ldi     r19, HIGH8(BOOT_AT + USB_CONFIGURATION_OFFSET)
    ldi     r24, USB_DEVICE_DESCRIPTOR_BYTES
    rjmp    usb_reply_set_pointer

/* Dispatch GET_CONFIGURATION and SET_CONFIGURATION. */
usb_standard_check_configuration:
    cpi     r25, USB_REQ_GET_CONFIGURATION
    brbs    SREG_Z, usb_standard_get_configuration
    cpi     r25, USB_REQ_SET_CONFIGURATION
    brbc    SREG_Z, usb_standard_check_get_interface
    std     Y+CTX_CONFIGURATION, r18
    rjmp    usb_reply_use_scratch_buffer

/* Return the default interface byte or an empty unsupported-request reply. */
usb_standard_check_get_interface:
    ldi     r24, 0x01
    cpi     r25, USB_REQ_GET_INTERFACE
    brbs    SREG_Z, usb_standard_scratch_reply
    ldi     r24, 0x00
usb_standard_scratch_reply:
    rjmp    usb_reply_use_scratch_buffer

/* Prepare a one-byte reply pointing at the current USB configuration. */
usb_standard_get_configuration:
    ldd     r18, Y+CTX_CONFIGURATION
usb_reply_pointer_trampoline:
    rjmp    ee_return_one

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

/* 0xF0 readiness shares the busy status and one-byte response tail. */
ee_ready:
    ldi     r18, STATUS_ACCEPTED
    sbis    _SFR_IO_ADDR(EECR), EEPE
    rjmp    ee_return_one

ee_busy:
    ldi     r18, STATUS_BUSY
    /* Fall through to common 1-byte response. */

/* Shared 1-byte USB response buffer at SRAM 0x010A, reused by legacy
   Micronucleus vendor responses. Fall through to common setup-response code. */
ee_return_one:
    std     Y+CTX_REPLY_SCRATCH, r18
    ldi     r24, 1
    rjmp    usb_reply_use_scratch_buffer

ee_bad_addr:
    ldi     r18, STATUS_INVALID_PARAMETER
    rjmp    ee_return_one

/* 0xA0 read EEPROM address. wIndex ignored (as SPI dummy field).
   If EEPROM busy, zero-length reply; host should poll 0xF0. */
ee_read:
    rcall   ee_validate_addr
    brcc    ee_empty
    sbic    _SFR_IO_ADDR(EECR), EEPE
    rjmp    ee_empty
    out     _SFR_IO_ADDR(EEARL), r16
    sbi     _SFR_IO_ADDR(EECR), EERE
    in      r18, _SFR_IO_ADDR(EEDR)
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
    ldd     r19, Y+CTX_SETUP_INDEX_HIGH
    mov     r18, r4
    andi    r18, FLASH_PAGE_OFFSET_MASK
    or      r19, r18
    brne    ee_bad_addr
    sbic    _SFR_IO_ADDR(EECR), EEPE      /* EEPROM write active? */
    rjmp    ee_busy
    /* On ATtiny88 a Flash Page Erase/Write SPM stalls the CPU until
       the operation completes. Page-buffer operations clear SELFPRGEN
       before another USB SETUP can be processed. Hence reaching this
       handler already implies SPM cannot be in progress. */
    ldd     r19, Y+CTX_SETUP_INDEX_LOW   /* data byte */
    out     _SFR_IO_ADDR(EEARL), r16   /* EEARL, address 0..63 */
    out     _SFR_IO_ADDR(EEDR), r19   /* EEDR */
    out     _SFR_IO_ADDR(EECR), r1    /* EECR=0: erase/write, no EERIE */
    sbi     _SFR_IO_ADDR(EECR), EEMPE    /* EEMPE = 1; 2 clocks */
    sbi     _SFR_IO_ADDR(EECR), EEPE    /* EEPE = 1; next instruction, within 4 clocks */
    /* The page-offset/high-index guard proved r18 == 0. The subsequent
       loads and bit-I/O preserve it and the accepted-path flags. */
    rjmp    ee_return_one

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
    ldd     r18, Y+CTX_SETUP_INDEX_LOW
    ldd     r19, Y+CTX_SETUP_INDEX_HIGH
    or      r18, r19
    ldd     r19, Y+CTX_SETUP_LENGTH_HIGH
    or      r18, r19
    brne    ee_empty
    ldd     r24, Y+CTX_SETUP_LENGTH_LOW            /* wLength low, reply length */
    tst     r24
    breq    ee_empty
    cpi     r24, (FLASH_READ_MAX_BYTES + 1)
    brsh    ee_empty            /* reject length > 8 */
    ldd     r18, Y+CTX_SETUP_VALUE_LOW            /* wValue low - start address */
    ldd     r19, Y+CTX_SETUP_VALUE_HIGH            /* wValue high */
    /* Require start <= APP_LIMIT-length. The compile-time guard proves
       that subtracting a valid length cannot borrow from the high byte.
       CP/CPC then compare the complete unsigned 16-bit start address. */
    ldi     r30, LOW8(APP_LIMIT)
    sub     r30, r24
    cp      r30, r18
    ldi     r30, HIGH8(APP_LIMIT)
    cpc     r30, r19
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
    ldd     r16, Y+CTX_SETUP_VALUE_LOW
    cpi     r16, EEPROM_BYTES
    ldd     r18, Y+CTX_SETUP_VALUE_HIGH
    cpc     r18, r1
    ret
