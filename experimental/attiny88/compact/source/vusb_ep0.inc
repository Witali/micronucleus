/* EP0 reply generation; accepted SETUP dispatch is in vusb_setup.inc. */
bootloader_handle_vendor_request:
mov r7, r1
/* One gate owns private-command readiness. Busy replies are empty and do not
 * advance the shared cursor or touch an active queue. Standard USB requests
 * bypass this gate and remain available while EEPROM programming is pending. */
in r24, _SFR_IO_ADDR(EECR)
or r24, r8
brne usb_reply_empty
/* READ8 falls through; OUT commands branch back to the adjacent NVM module. */
cpi r25, REQ_UNIFIED_READ
brne bootloader_check_set_flash_address
/* Persistent register allocation:
 * r4:r5 = shared READ8/WRITE4 byte cursor, bit15 selects EEPROM
 * r6:r7 = idle poll count (preserved across USB handler calls)
 * r8 = pending EEPROM write count, r9 = DATA PID, r10..r13 = EEPROM queue
 * r14:r15 = reply byte cursor, preserved across PHY and NVM service
 * r3 = pending Flash SPM command; r15.7 tags an EEPROM reply.
 * X is the poll counter / reply staging pointer, Y the USB-context scratch
 * and receive buffer pointer, Z the SPM/CRC/read scratch pointer. X/Y/Z
 * are intentionally NOT permanently bound: the V-USB PHY clobbers Y/Z.
 */
memory_read:
/* SELECT loads the persistent r4:r5 byte-address cursor. WRITE4 already
 * advances it by four; READ8 advances it by eight without reselecting. */
movw r18, r4
/* Keep bit15 as a reply-pointer EEPROM tag. EEARL consumes only ZL. */
memory_read_eeprom:
memory_read_advance:
/* Reuse the reply's eight-byte length as the low-register addend. R1=0;
 * ADD/ADC advances the full cursor without borrowing Z or changing R18:R19. */
ldi r24, USB_EP0_PAYLOAD_BYTES
add r4, r24
adc r5, r1
rjmp usb_reply_set_pointer
/* Device descriptor bytes14/15 are permanent zero string indexes. */
usb_reply_use_scratch_buffer:
ldi r18, LOW8(BOOT_AT + USB_DEVICE_DESCRIPTOR_OFFSET + 14)
usb_reply_use_flash_pointer:
ldi r19, HIGH8(BOOT_AT + USB_DEVICE_DESCRIPTOR_OFFSET + 14)
usb_reply_set_pointer:
/* R14:R15 survives PHY and NVM workers, so no SRAM pointer spills. */
movw r14, r18
/* Reply length is min(prepared length, 16-bit SETUP wLength). A nonzero
 * high request-length byte cannot truncate these at-most-18-byte responses.
 */
usb_reply_limit_length:
rcall usb_service_pending
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
usb_tx_prepare_pending_reply:
/* CRC state is dead until this preparation starts and survives PHY service. */
eor r0, r0
ldi r25, 0x00
rcall usb_service_pending
ldd r24, Y+CTX_TX_LENGTH
sbrs r24, USB_HANDSHAKE_FLAG_BIT
rjmp bootloader_check_idle_timeout
ldd r24, Y+CTX_MSG_LENGTH
cpi r24, USB_NO_MESSAGE
brbs SREG_Z, bootloader_check_idle_timeout
/* Count and complemented CRC stay in PHY-preserved R24/R0/R25.
 * Publish the next message remainder while TX_LENGTH still advertises NAK. */
mov r23, r24
cpi r24, (USB_EP0_PAYLOAD_BYTES + 1)
brbs SREG_C, usb_tx_prepare_data_packet
ldi r24, USB_EP0_PAYLOAD_BYTES
usb_tx_prepare_data_packet:
sub r23, r24
cpi r24, USB_EP0_PAYLOAD_BYTES
sbci r23, 0
std Y+CTX_MSG_LENGTH, r23
/* SETUP initialized R9 to DATA0; first prepared response is DATA1. */
ldi r18, USB_DATA_PID_TOGGLE
eor r9, r18
std Y+CTX_TX_PID, r9
/* Copy Flash/EEPROM into the TX buffer while computing USB CRC16.
 * R24 packs remaining bytes in its low five bits and the bit phase above them;
 * adding 32 wraps after eight shifts, then DEC consumes one payload byte.
 * R0:R25 hold the complemented CRC representation used by the original PHY.
 */
usb_tx_initialize_payload_crc:
ldi r26, LOW8(USB_CONTEXT_BASE + CTX_TX_PAYLOAD)
ldi r27, HIGH8(USB_CONTEXT_BASE + CTX_TX_PAYLOAD)
usb_tx_copy_flash_payload:
rcall usb_service_pending
movw r30, r14
cp r1, r24
breq usb_crc16_payload_complete
sbrc r15, 7
rjmp usb_tx_eeprom_byte
lpm r18, Z+
rjmp usb_tx_store_byte
usb_tx_eeprom_byte:
out _SFR_IO_ADDR(EEARL), r30
sbi _SFR_IO_ADDR(EECR), EERE
in r18, _SFR_IO_ADDR(EEDR)
inc r30
usb_tx_store_byte:
st X+, r18
movw r14, r30
usb_crc16_mix_byte:
eor r0, r18
usb_crc16_shift_bit:
rcall usb_service_pending
sec
ror r25
ror r0
brbs SREG_C, usb_crc16_advance_bit_count
eor r0, r29
eor r25, r21
usb_crc16_advance_bit_count:
subi r24, LOW8(-CRC_BIT_COUNTER_INCREMENT)
brbs SREG_C, usb_crc16_shift_bit
usb_crc16_byte_complete:
dec r24
rjmp usb_tx_copy_flash_payload
usb_crc16_payload_complete:
usb_tx_append_payload_crc:
usb_crc16_append:
st X+, r0
st X+, r25
usb_crc16_core_end:
usb_tx_publish_packet_length:
rcall usb_service_pending
std Y+CTX_TX_LENGTH, r26
