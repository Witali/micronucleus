/* Vendor dispatch and shared EP0 reply helpers. Y is the USB context;
 * pointer/count registers survive cooperative service as documented below.
 * Keep this module beside NVM/standard handlers for short conditional branches.
 */
bootloader_handle_vendor_request:
    mov r7, r1
/* One gate owns private-command readiness. Busy replies are empty and do not
 * advance the shared cursor or touch an active queue. Standard USB requests
 * bypass this gate and remain available while EEPROM programming is pending. */
    in r24, _SFR_IO_ADDR(EECR)
    or r24, r2
    brne usb_reply_empty
/* READ8 falls through; OUT commands branch back to the adjacent NVM module. */
    cpi r25, REQ_UNIFIED_READ
    brne bootloader_check_set_flash_address
/* Persistent register allocation:
 * r4:r5 = shared READ8/WRITE4 byte cursor, bit15 selects EEPROM
 * r6:r7 = idle poll count (preserved across USB handler calls)
 * r2 = pending EEPROM write count, r9 = DATA PID, r10..r13 = EEPROM queue
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
/* Compare the complete request word; LDD preserves the low-byte borrow.
 * R18 is dead after the persistent reply pointer has been published. */
    ldd r25, Y+CTX_SETUP_LENGTH_LOW
    cp r25, r24
    ldd r18, Y+CTX_SETUP_LENGTH_HIGH
    cpc r18, r1
    brsh usb_reply_store_length
    mov r24, r25
usb_reply_store_length:
    std Y+CTX_MSG_LENGTH, r24
    rjmp usb_rx_release_buffer
