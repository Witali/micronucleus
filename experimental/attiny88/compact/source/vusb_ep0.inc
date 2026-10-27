/* EP0 SETUP dispatch, reply length limiting and staged TX payload/CRC.
 * Restore Y after the PHY before any context access. SETUP resets DATA PID
 * and reply state; private memory requests share the same response machinery.
 */
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
/* Vendor protocol has one IN operation and four small OUT opcodes. */
cpi r25, REQ_UNIFIED_READ
breq memory_read
rjmp bootloader_check_set_flash_address
/* Persistent register allocation:
 * r4:r5 = shared READ8/WRITE4 byte cursor, bit15 selects EEPROM
 * r6:r7 = idle poll count (preserved across USB handler calls)
 * r8 = pending EEPROM write count, r10..r13 = EEPROM four-byte queue
 * r3 = pending Flash SPM command, r2 = current reply memory source.
 * X is the poll counter / reply staging pointer, Y the USB-context scratch
 * and receive buffer pointer, Z the SPM/CRC/read scratch pointer. X/Y/Z
 * are intentionally NOT permanently bound: the V-USB PHY clobbers Y/Z.
 */
memory_read:
/* SELECT loads the persistent r4:r5 byte-address cursor. WRITE4 already
 * advances it by four; READ8 advances it by eight without reselecting. */
movw r18, r4
sbrs r19, 7
rjmp memory_read_advance
memory_read_eeprom:
rcall ee_check_busy
breq .Lread_eeprom_ready
rjmp ee_empty
.Lread_eeprom_ready:
mov r2, r19
mov r19, r1
memory_read_advance:
/* Z is scratch and may be reused after preparing the reply. */
movw r30, r4
adiw r30, USB_EP0_PAYLOAD_BYTES
movw r4, r30
ldi r24, USB_EP0_PAYLOAD_BYTES
rjmp usb_reply_set_pointer
usb_reply_use_scratch_buffer:
ldi r18, LOW8(USB_CONTEXT_BASE + CTX_REPLY_SCRATCH)
ldi r19, HIGH8(USB_CONTEXT_BASE + CTX_REPLY_SCRATCH)
mov r2, r19
usb_reply_set_pointer:
std Y+CTX_MSG_POINTER_HIGH, r19
std Y+CTX_MSG_POINTER_LOW, r18
/* Reply length is min(prepared length, 16-bit SETUP wLength). A nonzero
 * high request-length byte cannot truncate these at-most-18-byte responses.
 */
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
/* Copy Flash/SRAM/EEPROM into the TX buffer while computing USB CRC16.
 * R23 packs remaining bytes in its low five bits and the bit phase above them;
 * adding 32 wraps after eight shifts, then DEC consumes one payload byte.
 * R19:R25 hold the complemented CRC representation used by the original PHY.
 */
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
