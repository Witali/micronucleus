/* Strict USB size-optimization candidate: ATtiny88, 16 MHz, EEPROM/Flash read.
 * BASED ON Optimized Micronucleus t88_default 16 MHz ATtiny88 bootloader, pass 3.
 * Assembler reconstruction of public Micronucleus firmware with conservative code-size
 * SRAM pointer reuse in V-USB with cycle-neutral sync-stage initialization.
 * RX/TX sampler and sender timings preserved by cycle tests; CRC-16 unchanged.
 * Labels describe control flow; source/label-map.csv records historical names and purposes.
 * Original Micronucleus contributors and modifications: GPL-2.0-or-later.
 */
#include <avr/io.h>
#include "../strict_usb_verified/led_config.h"
#include "../strict_usb_verified/led_macros.inc"
#ifndef BOOT_AT
#define BOOT_AT 0x1ac0
#endif
#define LOW8(value) ((value) & 0xff)
#define HIGH8(value) (((value) >> 8) & 0xff)
#define AVR_WORD_BYTES 2
#define AVR_RJMP_OPCODE 0xc000
#define AVR_RJMP_OFFSET_MASK 0x0fff
#define FLASH_PAGE_BYTES SPM_PAGESIZE
#define FLASH_PAGE_OFFSET_MASK (FLASH_PAGE_BYTES - 1)
#define FLASH_PAGE_ALIGN_MASK (0xff ^ FLASH_PAGE_OFFSET_MASK)
#define EEPROM_BYTES (E2END + 1)
#define FLASH_ERASED_BYTE 0xff
#define POSTSCRIPT_BYTES 4
#define APP_LIMIT (BOOT_AT - POSTSCRIPT_BYTES)
#define USB_MINUS_BIT PD1
#define USB_PLUS_BIT PD2
#define USB_LINE_MASK ((1 << USB_MINUS_BIT) | (1 << USB_PLUS_BIT))
#define USB_LINES_CLEAR_MASK (0xff ^ USB_LINE_MASK)
#define USB_INTERRUPT_ENABLE_MASK (1 << PCINT18)
#define WATCHDOG_UNLOCK_MASK ((1 << WDCE) | (1 << WDE))
#define SPM_BUFFER_LOAD (1 << SELFPRGEN)
#define SPM_PAGE_ERASE ((1 << PGERS) | SPM_BUFFER_LOAD)
#define SPM_PAGE_WRITE ((1 << PGWRT) | SPM_BUFFER_LOAD)
#define SPM_BUFFER_CLEAR ((1 << CTPB) | SPM_BUFFER_LOAD)
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
#define USB_RX_PACKET_OVERHEAD 3
#define USB_TX_PACKET_OVERHEAD 4
#define USB_RX_BUFFER_BYTES (USB_EP0_PAYLOAD_BYTES + USB_RX_PACKET_OVERHEAD)
#define USB_FULL_TX_PACKET_BYTES (USB_EP0_PAYLOAD_BYTES + USB_TX_PACKET_OVERHEAD)
#define USB_NO_MESSAGE 0xff
#define USB_HANDSHAKE_FLAG_BIT 4
#define USB_HANDSHAKE_REGISTER 20
#define USB_HANDSHAKE_TX_BYTES 2
#define USB_HANDSHAKE_END_POINTER (USB_HANDSHAKE_REGISTER + USB_HANDSHAKE_TX_BYTES)
#define USB_SYNC_BYTE 0x80
#define BOOT_INFO_OFFSET AVR_WORD_BYTES
#define BOOT_INFO_BYTES 0
#define BOOT_FEATURE_RESET_FLAGS 0x20
#define BOOT_FEATURE_EEPROM 0x40
#define BOOT_FEATURE_FLASH_READ 0x80
#define BOOT_FEATURES (BOOT_FEATURE_RESET_FLAGS | BOOT_FEATURE_EEPROM | BOOT_FEATURE_FLASH_READ)
#define FLASH_WRITE_DELAY_MS 5
#define USB_PROTOCOL_BCD 0x0110
/* Host-driven v5.3, select-and-erase combined; standard USB control preserved. */
/* Device-descriptor bcdDevice identifies the complete known build on the host.
 * No INFO, checksum table or firmware fingerprinting on the MCU. */
#if LED_MODE == NONE
#define BOOT_VERSION_BCD 0x0530
#elif LED_MODE == ACTIVE_HIGH
#define BOOT_VERSION_BCD 0x0531
#else
#define BOOT_VERSION_BCD 0x0532
#endif
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
#define CMD_SET_MEMORY_ADDRESS 1
#define CMD_SELECT_AND_ERASE 2
#define CMD_WRITE4 3
#define CMD_EXIT 4
#define CMD_COMMIT_PAGE SPM_PAGE_WRITE
#define CMD_DEFERRED_MASK 0x3f
/* For READ8 and SET_ADDRESS, the 16-bit field is a block address:
 * bit15 selects EEPROM; bits0..14 select a 4-byte unit.
 * READ8 always returns the selected block and the next block.
 * WRITE4 carries its four data bytes in wValue and wIndex.
 */
#define REQ_UNIFIED_READ 0xb0
#define ADDRESS_EEPROM_FLAG 0x80
#define EEPROM_BLOCKS (EEPROM_BYTES / 4)
#define MAX_FLASH_READ_BLOCK ((8192 - USB_EP0_PAYLOAD_BYTES)/4)
#define MAX_FLASH_START_BLOCK ((BOOT_AT - FLASH_PAGE_BYTES)/4)
#define EEPROM_WRITE_BLOCK_BYTES 4
#define STATUS_READY 0
#define STATUS_ACCEPTED 0
#define STATUS_BUSY 1
#define STATUS_INVALID_PARAMETER 2
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
#define CRC16_POLYNOMIAL 0xa001
#define CRC_BIT_COUNTER_INCREMENT 32
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
#if HIGH8(BOOT_AT + USB_CONFIGURATION_OFFSET) != HIGH8(BOOT_AT + USB_DEVICE_DESCRIPTOR_OFFSET)
#error USB descriptor pointers cross a 256-byte page; adjust optimized dispatcher
#endif
#if HIGH8(USB_CONTEXT_BASE) != LOW8(CRC16_POLYNOMIAL)
#error CRC polynomial low byte must match the context pointer high byte in Y
#endif
#if HIGH8(USB_CONTEXT_BASE) != SPM_BUFFER_LOAD
#error Flash buffer load command must match the context pointer high byte in Y
#endif
#if USB_EP0_PAYLOAD_BYTES >= CRC_BIT_COUNTER_INCREMENT
#error Packed CRC counter requires the payload byte count to fit below the bit phase increment
#endif
#if LOW8(USB_CONTEXT_BASE + CTX_TX_PAYLOAD) + 2 != USB_TX_PACKET_OVERHEAD
#error Final X low byte must equal the complete packet length after appending CRC
#endif
#if USB_FULL_TX_PACKET_BYTES > 255
#error Packet length must not carry out of X low byte
#endif
.section .text
.org BOOT_AT
.global bootloader_start
bootloader_start:
rjmp startup
.byte USB_CONFIGURATION_HEADER_BYTES, USB_DESCRIPTOR_CONFIGURATION
.byte LOW8(USB_CONFIGURATION_TOTAL_BYTES), HIGH8(USB_CONFIGURATION_TOTAL_BYTES)
.byte 1, 1, 0, USB_CONFIGURATION_ATTRIBUTES, (USB_MAX_POWER_MA / 2)
.byte USB_INTERFACE_DESCRIPTOR_BYTES, USB_DESCRIPTOR_INTERFACE, 0, 0, 0, 0, 0, 0, 0
.byte USB_DEVICE_DESCRIPTOR_BYTES, USB_DESCRIPTOR_DEVICE
.byte LOW8(USB_PROTOCOL_BCD), HIGH8(USB_PROTOCOL_BCD), USB_CLASS_VENDOR_SPECIFIC, 0, 0, USB_EP0_PAYLOAD_BYTES
.byte LOW8(USB_VENDOR_ID), HIGH8(USB_VENDOR_ID), LOW8(USB_PRODUCT_ID), HIGH8(USB_PRODUCT_ID)
.byte LOW8(BOOT_VERSION_BCD), HIGH8(BOOT_VERSION_BCD), 0, 0, 0, 1
USB_handler:
push r28
push r29
eor r28, r28
usb_rx_wait_for_j:
inc r28
sbis _SFR_IO_ADDR(PIND), USB_MINUS_BIT
brbc SREG_Z, usb_rx_wait_for_j
usb_rx_wait_for_k:
sbis _SFR_IO_ADDR(PIND), USB_MINUS_BIT
rjmp usb_rx_found_k
sbis _SFR_IO_ADDR(PIND), USB_MINUS_BIT
rjmp usb_rx_found_k
sbis _SFR_IO_ADDR(PIND), USB_MINUS_BIT
rjmp usb_rx_found_k
sbis _SFR_IO_ADDR(PIND), USB_MINUS_BIT
rjmp usb_rx_found_k
sbis _SFR_IO_ADDR(PIND), USB_MINUS_BIT
rjmp usb_rx_found_k
sbis _SFR_IO_ADDR(PIND), USB_MINUS_BIT
rjmp usb_rx_found_k
rjmp usb_handler_return
usb_rx_found_k:
push r0
lds r28, (USB_CONTEXT_BASE + CTX_INPUT_BUFFER_OFFSET)
eor r29, r29
subi r28, LOW8(-(USB_CONTEXT_BASE + CTX_RX_BUFFER))
sbci r29, HIGH8(-(USB_CONTEXT_BASE + CTX_RX_BUFFER))
pop r0
ldi r22, USB_RX_PAIR_COUNTER_INCREMENT
sbis _SFR_IO_ADDR(PIND), USB_MINUS_BIT
rjmp usb_rx_sync_confirmed
push r0
pop r0
rjmp usb_rx_wait_for_k
usb_rx_sync_confirmed:
ldi r30, LOW8(USB_CONTEXT_BASE)
ldi r31, HIGH8(USB_CONTEXT_BASE)
rjmp usb_rx_delay_complete
usb_rx_delay_complete:
push r16
ldi r18, 0x00
ldi r20, USB_RX_INITIAL_STUFF_MASK
pop r16
in r16, _SFR_IO_ADDR(PIND)
andi r16, USB_LINE_MASK
bst r16, USB_MINUS_BIT
bld r18, 7
push r19
ldi r21, 0x00
ldi r19, USB_RX_BUFFER_BYTES
rjmp usb_rx_sample_odd_bit
usb_rx_unstuff_bit6:
andi r17, USB_LINE_MASK
ori r20, USB_RX_CORRECTION_BIT6_MASK
andi r18, USB_RX_CLEAR_HIGH_BIT_MASK
mov r16, r17
subi r21, LOW8(-1)
rjmp usb_rx_sample_bit7
usb_rx_unstuff_bit7:
ori r20, USB_RX_CORRECTION_BIT7_MASK
in r17, _SFR_IO_ADDR(PIND)
andi r17, USB_LINE_MASK
andi r18, USB_RX_CLEAR_HIGH_BIT_MASK
subi r21, USB_RX_UNSTUFF7_LEAP_ADJUST
rjmp usb_rx_finish_byte
usb_rx_unstuff_even_bit:
ori r20, USB_RX_CORRECTION_BIT6_MASK
in r16, _SFR_IO_ADDR(PIND)
andi r18, USB_RX_CLEAR_HIGH_BIT_MASK
andi r16, USB_LINE_MASK
brbs SREG_Z, usb_rx_end_packet
subi r21, LOW8(-1)
rjmp usb_rx_unstuff_even_resume_jump
usb_rx_unstuff_even_resume_jump:
rjmp usb_rx_shift_stuff_mask
usb_rx_unstuff_odd_bit:
ori r20, USB_RX_CORRECTION_BIT5_MASK
in r17, _SFR_IO_ADDR(PIND)
andi r18, USB_RX_CLEAR_HIGH_BIT_MASK
andi r17, USB_LINE_MASK
brbs SREG_Z, usb_rx_end_packet
subi r21, LOW8(-1)
rjmp usb_rx_unstuff_odd_resume_jump
usb_rx_unstuff_odd_resume_jump:
rjmp usb_rx_advance_bit_pair
usb_rx_decode_bit6:
andi r16, USB_LINE_MASK
eor r17, r16
subi r21, 0x01
brbc SREG_N, usb_rx_shift_bit6
subi r21, LOW8(-USB_RX_LEAP_PERIOD)
nop
usb_rx_shift_bit6:
subi r17, 0x01
ror r18
usb_rx_sample_bit7:
cpi r18, USB_STUFF_HISTORY_THRESHOLD
in r17, _SFR_IO_ADDR(PIND)
brbc SREG_C, usb_rx_unstuff_bit6
andi r17, USB_LINE_MASK
eor r16, r17
subi r16, 0x01
ror r18
usb_rx_finish_byte:
cpi r18, USB_STUFF_HISTORY_THRESHOLD
brbc SREG_C, usb_rx_unstuff_bit7
eor r20, r18
st Y+, r20
usb_rx_sample_even_bit:
in r16, _SFR_IO_ADDR(PIND)
andi r16, USB_LINE_MASK
eor r17, r16
andi r20, USB_RX_LOW_BITS_MASK
subi r17, 0x01
ror r18
cpi r18, USB_STUFF_HISTORY_THRESHOLD
brbc SREG_C, usb_rx_unstuff_even_bit
usb_rx_shift_stuff_mask:
lsr r20
lsr r20
usb_rx_sample_odd_bit:
in r17, _SFR_IO_ADDR(PIND)
andi r17, USB_LINE_MASK
brbs SREG_Z, usb_rx_end_packet
eor r16, r17
subi r16, 0x01
ror r18
cpi r18, USB_STUFF_HISTORY_THRESHOLD
brbc SREG_C, usb_rx_unstuff_odd_bit
usb_rx_advance_bit_pair:
subi r22, LOW8(-USB_RX_PAIR_COUNTER_INCREMENT)
brbs SREG_C, usb_rx_sample_even_bit
subi r19, 0x01
in r16, _SFR_IO_ADDR(PIND)
brbc SREG_C, usb_rx_decode_bit6
rjmp usb_rx_overflow
usb_rx_overflow:
sbi _SFR_IO_ADDR(PCIFR), PCIF2
usb_rx_ignore_packet:
eor r16, r16
rjmp usb_rx_store_token
usb_rx_end_packet:
subi r19, USB_RX_BUFFER_BYTES
neg r19
sub r28, r19
sbci r29, 0x00
sbi _SFR_IO_ADDR(PCIFR), PCIF2
ldd r16, Y+USB_PACKET_PID_OFFSET
cpi r16, USB_PID_DATA0
brbs SREG_Z, usb_rx_handle_data
cpi r16, USB_PID_DATA1
brbs SREG_Z, usb_rx_handle_data
ldd r18, Z+CTX_DEVICE_ADDRESS
ldd r17, Y+USB_PACKET_ADDRESS_OFFSET
add r17, r17
cpse r17, r18
rjmp usb_rx_ignore_packet
cpi r16, USB_PID_IN
brbs SREG_Z, usb_rx_handle_in
cpi r16, USB_PID_SETUP
brbs SREG_Z, usb_rx_handle_setup_or_out
cpi r16, USB_PID_OUT
brbc SREG_Z, usb_rx_ignore_packet
usb_rx_handle_setup_or_out:
ldi r28, USB_NEXT_DATA_WAIT_COUNT
usb_rx_wait_for_data:
in r17, _SFR_IO_ADDR(PCIFR)
sbrc r17, PCIF2
rjmp usb_rx_store_token
dec r28
brbc SREG_Z, usb_rx_wait_for_data
usb_rx_store_token:
std Z+CTX_CURRENT_TOKEN, r16
usb_handler_packet_done:
pop r19
in r28, _SFR_IO_ADDR(PCIFR)
sbrc r28, PCIF2
rjmp usb_rx_wait_for_j
usb_handler_return:
pop r29
pop r28
ret
usb_rx_handle_data:
ldd r18, Z+CTX_CURRENT_TOKEN
and r18, r18
brbs SREG_Z, usb_handler_packet_done
ldd r17, Z+CTX_RX_LENGTH
and r17, r17
brbc SREG_Z, usb_tx_send_nak
cpi r19, (USB_RX_PACKET_OVERHEAD + 1)
brbs SREG_N, usb_tx_send_ack
std Z+CTX_RX_LENGTH, r19
std Z+CTX_RX_TOKEN, r18
rjmp usb_tx_send_ack
usb_rx_handle_in:
ldd r16, Z+CTX_RX_LENGTH
cpi r16, 0x01
brbc SREG_S, usb_tx_send_nak
ldi r16, USB_PID_NAK
ldd r19, Z+CTX_TX_LENGTH
sbrc r19, USB_HANDSHAKE_FLAG_BIT
rjmp usb_tx_send_count_handshake
std Z+CTX_TX_LENGTH, r16
ldi r28, LOW8(USB_CONTEXT_BASE + CTX_TX_PID)
ldi r29, HIGH8(USB_CONTEXT_BASE + CTX_TX_PID)
rjmp usb_tx_acquire_bus
usb_tx_stuff_regular_bit:
eor r16, r21
ldi r17, 0x00
rjmp usb_tx_stuff_regular_delay
usb_tx_stuff_regular_delay:
nop
out _SFR_IO_ADDR(PORTD), r16
rjmp usb_tx_check_regular_stuffing
usb_tx_stuff_bit6:
eor r16, r21
ldi r17, 0x00
adc r18, r18
rjmp usb_tx_send_bit6
usb_tx_stuff_bit7:
ldi r17, 0x00
rjmp usb_tx_send_bit7
usb_tx_send_nak:
ldi r20, USB_PID_NAK
rjmp usb_tx_prepare_handshake
usb_tx_send_ack:
ldi r19, USB_PID_ACK
usb_tx_send_count_handshake:
mov r20, r19
usb_tx_prepare_handshake:
ldi r28, LOW8(USB_HANDSHAKE_REGISTER)
ldi r29, HIGH8(USB_HANDSHAKE_REGISTER)
ldi r19, USB_HANDSHAKE_TX_BYTES
usb_tx_acquire_bus:
in r17, _SFR_IO_ADDR(DDRD)
ori r17, USB_LINE_MASK
sbi _SFR_IO_ADDR(PORTD), USB_MINUS_BIT
in r16, _SFR_IO_ADDR(PORTD)
out _SFR_IO_ADDR(DDRD), r17
ldi r21, USB_LINE_MASK
ldi r18, USB_SYNC_BYTE
usb_tx_begin_byte:
ldi r22, USB_TX_BIT_COUNTER_SEED
usb_tx_send_regular_bit:
sbrs r18, 0
eor r16, r21
out _SFR_IO_ADDR(PORTD), r16
ror r18
ror r17
usb_tx_check_regular_stuffing:
cpi r17, USB_STUFF_HISTORY_THRESHOLD
brbc SREG_C, usb_tx_stuff_regular_bit
lsr r22
brbc SREG_C, usb_tx_send_regular_bit
brbc SREG_Z, usb_tx_send_regular_bit
sbrs r18, 0
eor r16, r21
usb_tx_send_bit6:
out _SFR_IO_ADDR(PORTD), r16
ror r18
ror r17
cpi r17, USB_STUFF_HISTORY_THRESHOLD
brbc SREG_C, usb_tx_stuff_bit6
ror r18
usb_tx_send_bit7:
ror r17
sbrs r17, 7
eor r16, r21
nop
cpi r17, USB_STUFF_HISTORY_THRESHOLD
out _SFR_IO_ADDR(PORTD), r16
brbc SREG_C, usb_tx_stuff_bit7
ld r18, Y+
dec r19
brbc SREG_Z, usb_tx_begin_byte
andi r16, USB_LINES_CLEAR_MASK
ldd r17, Z+CTX_NEW_DEVICE_ADDRESS
add r17, r17
subi r28, USB_HANDSHAKE_END_POINTER
sbci r29, 0x00
out _SFR_IO_ADDR(PORTD), r16
brbs SREG_Z, usb_tx_finish_eop
std Z+CTX_DEVICE_ADDRESS, r17
usb_tx_finish_eop:
sbi _SFR_IO_ADDR(PCIFR), PCIF2
ori r16, (1 << USB_MINUS_BIT)
in r17, _SFR_IO_ADDR(DDRD)
andi r17, USB_LINES_CLEAR_MASK
mov r20, r16
andi r20, USB_LINES_CLEAR_MASK
ldi r21, USB_EOP_DELAY_LOOPS
usb_tx_eop_delay:
dec r21
brbc SREG_Z, usb_tx_eop_delay
out _SFR_IO_ADDR(PORTD), r16
out _SFR_IO_ADDR(DDRD), r17
out _SFR_IO_ADDR(PORTD), r20
rjmp usb_handler_packet_done
/* RESET word is supplied prepatched by the host. Do NOT rewrite it here. */
flash_buffer_append_word:
movw r30, r4
flash_buffer_load_word:
movw r0, r24
out _SFR_IO_ADDR(SPMCSR), r29
spm
eor r1, r1
adiw r30, AVR_WORD_BYTES
movw r4, r30
ret
startup:
eor r1, r1
mov r8, r1             /* no pending EEPROM write */
/* Datasheet-defined RESET defaults: SPL/SPH=RAMEND, SREG=0.
 * This firmware entry is legal only through hardware RESET or WDT RESET;
 * a direct software jump into the bootloader without RESET is unsupported. */
ldi r28, LOW8(USB_CONTEXT_BASE + USB_CONTEXT_BYTES)
ldi r29, HIGH8(USB_CONTEXT_BASE)
startup_clear_sram_byte:
st -Y, r1
startup_check_sram_end:
cpi r28, LOW8(USB_CONTEXT_BASE)
brbc SREG_Z, startup_clear_sram_byte
main:
wdr
in r24, _SFR_IO_ADDR(MCUSR)
out _SFR_IO_ADDR(GPIOR0), r24
out _SFR_IO_ADDR(MCUSR), r1
ldi r24, WATCHDOG_UNLOCK_MASK
sts _SFR_MEM_ADDR(WDTCSR), r24
sts _SFR_MEM_ADDR(WDTCSR), r1
sbi _SFR_IO_ADDR(DDRD), USB_MINUS_BIT
ldi r18, USB_DISCONNECT_OUTER_LOOPS
usb_disconnect_delay_outer:
ldi r24, LOW8(USB_DISCONNECT_INNER_LOOPS)
ldi r25, HIGH8(USB_DISCONNECT_INNER_LOOPS)
usb_disconnect_delay_inner:
sbiw r24, 1
brne usb_disconnect_delay_inner
dec r18
brne usb_disconnect_delay_outer
cbi _SFR_IO_ADDR(DDRD), USB_MINUS_BIT
movw r4, r24
movw r6, r24
ldi r24, USB_PID_NAK
std Y+CTX_TX_LENGTH, r24
ldi r24, USB_NO_MESSAGE
std Y+CTX_MSG_LENGTH, r24
ldi r24, USB_INTERRUPT_ENABLE_MASK
sts _SFR_MEM_ADDR(PCMSK2), r24
sts _SFR_MEM_ADDR(PCICR), r24
led_init:
LED_INIT
led_init_done:
mov r3, r1
bootloader_poll_begin:
ldi r28, LOW8(USB_POLL_TIMEOUT_COUNT)
ldi r29, HIGH8(USB_POLL_TIMEOUT_COUNT)
ldi r24, USB_RESET_SE0_SAMPLES
usb_poll_sample_bus:
in r25, _SFR_IO_ADDR(PIND)
andi r25, USB_LINE_MASK
brbs SREG_Z, usb_poll_check_reset_duration
ldi r24, USB_RESET_SE0_SAMPLES
usb_poll_check_reset_duration:
subi r24, 0x01
brbc SREG_Z, usb_poll_check_packet_pending
sts (USB_CONTEXT_BASE + CTX_NEW_DEVICE_ADDRESS), r1
sts (USB_CONTEXT_BASE + CTX_DEVICE_ADDRESS), r1
usb_poll_check_packet_pending:
sbis _SFR_IO_ADDR(PCIFR), PCIF2
rjmp usb_poll_advance_timeout
rcall USB_handler
sbi _SFR_IO_ADDR(PCIFR), PCIF2
bootloader_process_pending_command:
wdr
/* EEPROM writes must complete before SPM erase/write/exit. */
tst r8
brne usb_control_process_received_packet
sbic _SFR_IO_ADDR(EECR), EEPE
rjmp usb_control_process_received_packet
bootloader_dispatch_command:
mov r24, r3
cpi r24, SPM_PAGE_ERASE
breq flash_erase_selected_page
cpi r24, SPM_PAGE_WRITE
breq flash_commit_buffered_page
cpi r24, CMD_EXIT
brne bootloader_clear_command
or r28, r29
brne usb_control_process_received_packet
rjmp bootloader_start_application
flash_erase_selected_page:
movw r30, r4
rjmp flash_do_spm
flash_commit_buffered_page:
movw r30, r4
sbiw r30, AVR_WORD_BYTES
flash_do_spm:
andi r30, FLASH_PAGE_ALIGN_MASK
/* Do not allow erase or write in the bootloader's own protected pages. */
#if LOW8(BOOT_AT) == 0
cpi r31, HIGH8(BOOT_AT)
#else
cpi r30, LOW8(BOOT_AT)
ldi r18, HIGH8(BOOT_AT)
cpc r31, r18
#endif
brsh bootloader_clear_command
out _SFR_IO_ADDR(SPMCSR), r24
spm
bootloader_clear_command:
mov r3, r1
usb_control_process_received_packet:
ldi r28, LOW8(USB_CONTEXT_BASE)
ldi r29, HIGH8(USB_CONTEXT_BASE)
ldd r24, Y+CTX_RX_LENGTH
cpi r24, (USB_SETUP_BYTES + USB_RX_PACKET_OVERHEAD)
brne usb_rx_release_buffer
ldd r25, Y+CTX_RX_TOKEN
cpi r25, USB_PID_SETUP
brbc SREG_Z, usb_rx_release_buffer
ldi r24, USB_PID_DATA0
std Y+CTX_TX_PID, r24
ldi r24, USB_PID_NAK
std Y+CTX_TX_LENGTH, r24
mov r2, r1
ldd r24, Y+CTX_SETUP_REQUEST_TYPE
andi r24, USB_REQUEST_TYPE_MASK
ldd r25, Y+CTX_SETUP_REQUEST
brbc SREG_Z, bootloader_handle_vendor_request
rjmp usb_standard_dispatch
bootloader_handle_vendor_request:
mov r7, r1
/* No GET_INFO: identify 0x0530/31/32 using standard USB descriptor. */
cpi r25, 5
brsh usb_vendor_extended
rjmp bootloader_check_set_flash_address
usb_vendor_extended:
rjmp usb_dispatch_extended_or_standard_request
usb_reply_use_scratch_buffer:
ldi r18, LOW8(USB_CONTEXT_BASE + CTX_REPLY_SCRATCH)
ldi r19, HIGH8(USB_CONTEXT_BASE + CTX_REPLY_SCRATCH)
mov r2, r19
usb_reply_set_pointer:
std Y+CTX_MSG_POINTER_HIGH, r19
std Y+CTX_MSG_POINTER_LOW, r18
usb_reply_limit_length:
ldd r25, Y+CTX_SETUP_LENGTH_HIGH
cpse r25, r1
rjmp usb_reply_store_length
ldd r25, Y+CTX_SETUP_LENGTH_LOW
cp r25, r24
brbc SREG_C, usb_reply_store_length
mov r24, r25
usb_reply_store_length:
std Y+CTX_MSG_LENGTH, r24
usb_rx_release_buffer:
std Y+CTX_RX_LENGTH, r1
usb_tx_prepare_pending_reply:
ldd r24, Y+CTX_TX_LENGTH
sbrs r24, USB_HANDSHAKE_FLAG_BIT
rjmp bootloader_check_idle_timeout
ldd r24, Y+CTX_MSG_LENGTH
cpi r24, USB_NO_MESSAGE
brbs SREG_Z, bootloader_check_idle_timeout
mov r23, r24
cpi r24, (USB_EP0_PAYLOAD_BYTES + 1)
brbs SREG_C, usb_tx_prepare_data_packet
ldi r23, USB_EP0_PAYLOAD_BYTES
usb_tx_prepare_data_packet:
sub r24, r23
ldd r25, Y+CTX_TX_PID
ldi r18, USB_DATA_PID_TOGGLE
eor r25, r18
std Y+CTX_TX_PID, r25
usb_tx_initialize_payload_crc:
ldi r19, 0x00
ldi r25, 0x00
ldi r21, HIGH8(CRC16_POLYNOMIAL)
ldi r26, LOW8(USB_CONTEXT_BASE + CTX_TX_PAYLOAD)
ldi r27, HIGH8(USB_CONTEXT_BASE + CTX_TX_PAYLOAD)
ldd r30, Y+CTX_MSG_POINTER_LOW
ldd r31, Y+CTX_MSG_POINTER_HIGH
usb_tx_copy_flash_payload:
cp r1, r23
breq usb_crc16_payload_complete
sbrc r2, 7
rjmp usb_tx_eeprom_byte
sbrc r2, 0
ld r18, Z+
sbrs r2, 0
lpm r18, Z+
rjmp usb_tx_store_byte
usb_tx_eeprom_byte:
out _SFR_IO_ADDR(EEARL), r30
sbi _SFR_IO_ADDR(EECR), EERE
in r18, _SFR_IO_ADDR(EEDR)
inc r30
usb_tx_store_byte:
st X+, r18
usb_crc16_mix_byte:
eor r19, r18
usb_crc16_shift_bit:
ror r25
ror r19
brbs SREG_C, usb_crc16_advance_bit_count
eor r19, r29
eor r25, r21
usb_crc16_advance_bit_count:
subi r23, LOW8(-CRC_BIT_COUNTER_INCREMENT)
brbs SREG_C, usb_crc16_shift_bit
usb_crc16_byte_complete:
dec r23
rjmp usb_tx_copy_flash_payload
usb_crc16_payload_complete:
std Y+CTX_MSG_POINTER_HIGH, r31
std Y+CTX_MSG_POINTER_LOW, r30
usb_tx_append_payload_crc:
usb_crc16_append:
st X+, r19
st X+, r25
usb_crc16_core_end:
cpi r26, USB_FULL_TX_PACKET_BYTES
sbci r24, 0
std Y+CTX_MSG_LENGTH, r24
usb_tx_publish_packet_length:
std Y+CTX_TX_LENGTH, r26
bootloader_check_idle_timeout:
rcall ee_write_step
movw r24, r6
adiw r24, 1
movw r6, r24
subi r24, LOW8(BOOT_IDLE_TIMEOUT_POLLS)
sbci r25, HIGH8(BOOT_IDLE_TIMEOUT_POLLS)
brbc SREG_Z, usb_poll_resynchronize
ldi r30, LOW8(APP_LIMIT + 1)
ldi r31, HIGH8(APP_LIMIT + 1)
lpm r30, Z
cpi r30, FLASH_ERASED_BYTE
brbc SREG_Z, bootloader_start_application
usb_poll_resynchronize:
led_tick:
LED_TICK
led_tick_done:
legacy_led_off_anchor:
usb_poll_check_missed_packet:
sbis _SFR_IO_ADDR(PCIFR), PCIF2
rjmp bootloader_poll_begin
ldi r24, USB_RESYNC_IDLE_SAMPLES
usb_poll_wait_for_idle:
sbis _SFR_IO_ADDR(PIND), USB_MINUS_BIT
ldi r24, USB_RESYNC_IDLE_SAMPLES
subi r24, 0x01
brbc SREG_Z, usb_poll_wait_for_idle
sbi _SFR_IO_ADDR(PCIFR), PCIF2
rjmp bootloader_poll_begin
usb_poll_advance_timeout:
sbiw r28, 1
brbs SREG_Z, bootloader_poll_timeout
rjmp usb_poll_sample_bus
bootloader_poll_timeout:
rjmp bootloader_process_pending_command
bootloader_start_application:
led_exit:
#if LED_DDR_IO == 0x0a
#if LED_MODE == ACTIVE_HIGH
cbi LED_PORT_IO, LED_PIN
#endif
#else
LED_EXIT
#endif
led_exit_done:
out _SFR_IO_ADDR(DDRD), r1
sts _SFR_MEM_ADDR(PCICR), r1
sts _SFR_MEM_ADDR(PCMSK2), r1
app_jump:
.word (AVR_RJMP_OPCODE | (((bootloader_start - POSTSCRIPT_BYTES - app_jump - AVR_WORD_BYTES) / AVR_WORD_BYTES) & AVR_RJMP_OFFSET_MASK))
bootloader_check_set_flash_address:
/* EEPROM's asynchronous writer must be idle before NVM mode changes. */
tst r8
brne usb_reply_empty
sbic _SFR_IO_ADDR(EECR), EEPE
rjmp usb_reply_empty
/* Opcodes 1 (select) and 2 (select + erase) share the address decoder;
 * the queued erase runs only after the main USB polling interval. */
cpi r25, CMD_WRITE4
brsh bootloader_check_write4
/* Save the request, but queue erase only after the EEPROM/Flash selector.
 * Invalid EEPROM set-address requests cannot erase a previously selected page. */
mov r18, r25
/* Vendor 1: select page / block. Vendor 2: select and queue page erase.
 * Both carry the new block address in wIndex; only Flash is erasable. */
ldd r24, Y+CTX_SETUP_INDEX_LOW
ldd r25, Y+CTX_SETUP_INDEX_HIGH
sbrc r25, 7
rjmp set_address_eeprom
subi r18, 0xff
mov r3, r18
/* Host validates the block index. The shared erase/commit SPM executor
 * STILL protects all pages >= BOOT_AT, including the loader itself. */
/* Discard low four block bits => align to Flash's 64-byte page. */
andi r24, 0xf0
lsl r24
rol r25
lsl r24
rol r25
movw r4, r24
ldi r24, SPM_BUFFER_CLEAR
out _SFR_IO_ADDR(SPMCSR), r24
spm
rjmp usb_reply_empty
set_address_eeprom:
/* 16 blocks of four bytes. Keep bit7 of r5 as the memory selector. */
cpi r25, ADDRESS_EEPROM_FLAG
brne usb_reply_empty
cpi r24, EEPROM_BLOCKS
brsh usb_reply_empty
lsl r24
lsl r24
mov r4, r24
mov r5, r25
usb_reply_empty:
ldi r24, 0x00
rjmp usb_reply_limit_length
bootloader_check_write4:
cpi r25, CMD_WRITE4
brbc SREG_Z, bootloader_queue_command
sbrc r5, 7
rjmp ee_write
ldd r24, Y+CTX_SETUP_VALUE_LOW
ldd r25, Y+CTX_SETUP_VALUE_HIGH
rcall flash_buffer_append_word
ldd r24, Y+CTX_SETUP_INDEX_LOW
ldd r25, Y+CTX_SETUP_INDEX_HIGH
rcall flash_buffer_append_word
andi r30, FLASH_PAGE_OFFSET_MASK
brbc SREG_Z, usb_reply_empty
ldi r25, SPM_PAGE_WRITE
bootloader_queue_command:
mov r3, r25
rjmp usb_reply_empty
usb_dispatch_extended_or_standard_request:
cpi r25, REQ_UNIFIED_READ
brne usb_standard_dispatch
memory_read:
/* Fixed READ8: allow the whole 8-KiB Flash, including the loader.
 * Read-only access supports PC-side firmware fingerprinting; the separate
 * SPM erase/write guards remain intact. No checksum code on the MCU. */
ldd r18, Y+CTX_SETUP_VALUE_LOW
ldd r19, Y+CTX_SETUP_VALUE_HIGH
sbrs r19, 7
rjmp memory_read_shift
/* Shared READ8: EEPROM path falls through, Flash skips the EEPROM peripheral. */
memory_read_eeprom:
tst r8
brne ee_empty
sbic _SFR_IO_ADDR(EECR), EEPE
rjmp ee_empty
mov r2, r19
mov r19, r1
memory_read_shift:
lsl r18
rol r19
lsl r18
rol r19
ldi r24, USB_EP0_PAYLOAD_BYTES
rjmp usb_reply_set_pointer
usb_standard_dispatch:
ldd r18, Y+CTX_SETUP_VALUE_LOW
std Y+CTX_REPLY_SCRATCH, r1
cpse r25, r1
rjmp usb_standard_check_set_address
std Y+CTX_REPLY_SCRATCH_HIGH, r1
ldi r24, USB_STATUS_REPLY_BYTES
rjmp usb_reply_use_scratch_buffer
usb_standard_check_set_address:
cpi r25, USB_REQ_SET_ADDRESS
brbc SREG_Z, usb_standard_check_get_descriptor
std Y+CTX_NEW_DEVICE_ADDRESS, r18
rjmp usb_reply_use_scratch_buffer
usb_standard_check_get_descriptor:
cpi r25, USB_REQ_GET_DESCRIPTOR
brbc SREG_Z, usb_standard_check_configuration
ldd r24, Y+CTX_SETUP_VALUE_HIGH
ldi r18, LOW8(BOOT_AT + USB_DEVICE_DESCRIPTOR_OFFSET)
cpi r24, USB_DESCRIPTOR_DEVICE
breq desc_ptr
cpi r24, USB_DESCRIPTOR_CONFIGURATION
brne ee_std_empty
ldi r18, LOW8(BOOT_AT + USB_CONFIGURATION_OFFSET)
desc_ptr:
ldi r19, HIGH8(BOOT_AT + USB_CONFIGURATION_OFFSET)
ldi r24, USB_DEVICE_DESCRIPTOR_BYTES
rjmp usb_reply_set_pointer
usb_standard_check_configuration:
cpi r25, USB_REQ_GET_CONFIGURATION
brbs SREG_Z, usb_standard_get_configuration
cpi r25, USB_REQ_SET_CONFIGURATION
brbc SREG_Z, usb_standard_check_get_interface
std Y+CTX_CONFIGURATION, r18
rjmp usb_reply_use_scratch_buffer
usb_standard_check_get_interface:
cpi r25, USB_REQ_GET_INTERFACE
brne ee_std_empty
ldi r24, 0x01
usb_standard_scratch_reply:
rjmp usb_reply_use_scratch_buffer
ee_std_empty:
ee_empty:
rjmp usb_reply_empty
usb_standard_get_configuration:
ldd r18, Y+CTX_CONFIGURATION
usb_reply_pointer_trampoline:
legacy_led_on_anchor:
ee_return_one:
std Y+CTX_REPLY_SCRATCH, r18
ldi r24, 1
rjmp usb_reply_use_scratch_buffer
ee_bad_addr:
rjmp usb_reply_empty
/* Write one aligned block of four EEPROM bytes, packed in SETUP fields.
 * R8 = pending byte count; R9 = next address; R10:R13 = queued data.
 * Rejected while EEPROM/Flash is busy; no legacy byte-write command.
 */
ee_write:
/* 4 data bytes arrive in SETUP fields; R4 is the EEPROM byte address. */
mov r18, r4
cpi r18, EEPROM_BYTES - EEPROM_WRITE_BLOCK_BYTES + 1
brsh ee_bad_addr
ldd r10, Y+CTX_SETUP_VALUE_LOW
ldd r11, Y+CTX_SETUP_VALUE_HIGH
ldd r12, Y+CTX_SETUP_INDEX_LOW
ldd r13, Y+CTX_SETUP_INDEX_HIGH
ldi r18, EEPROM_WRITE_BLOCK_BYTES
mov r8, r18
rjmp usb_reply_empty

/* Reuses the AVR register file as a four-byte queue (address 0x0A..0x0D).
 * Never spin on EEPE: advance one byte between USB poll windows. */
ee_write_step:
tst r8
breq ee_write_step_done
sbic _SFR_IO_ADDR(EECR), EEPE
ret
ldi r30, 14
sub r30, r8
mov r31, r1
ld r18, Z
out _SFR_IO_ADDR(EEARL), r4
out _SFR_IO_ADDR(EEDR), r18
/* Only the bootloader touches EECR and keeps EEPM=00, EERIE=0;
 * the timed pair of SBIs performs erase/write without extra OUT EECR=0. */
sbi _SFR_IO_ADDR(EECR), EEMPE
sbi _SFR_IO_ADDR(EECR), EEPE
inc r4
dec r8
ee_write_step_done:
ret
