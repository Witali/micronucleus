/* Micronucleus+ compact Pass31 FLASH-ONLY optimized research candidate, ATtiny88 at 16 MHz.
 * Derived from Witali/micronucleus Pass28 assembly; GPL-2.0-or-later.
 * Source modules follow the adjacent Block64 layout but use a separate protocol.
 * Original Micronucleus contributors' licensing/provenance remains in the
 * preserved baseline and LICENSE_GPL-2.0.txt. The previous Pass27 no-LED
 * hardware smoke-test is documented upstream in docs/HARDWARE_INSTALL30.md;
 * THIS Pass31 optimization is not hardware-tested.
 */
#include "device_attiny88.inc"
#include "compact_protocol.inc"
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
#include "vusb_phy.inc"
flash_buffer_append_word:
flash_buffer_load_word:
startup:
    eor r1, r1
    ldi r28, LOW8(USB_CONTEXT_BASE + USB_CONTEXT_BYTES)
    ldi r29, HIGH8(USB_CONTEXT_BASE)
main:
    wdr
    in r24, _SFR_IO_ADDR(MCUSR)
    out _SFR_IO_ADDR(GPIOR0), r24
    out _SFR_IO_ADDR(MCUSR), r1
    ldi r30, LOW8(_SFR_MEM_ADDR(WDTCSR))
    mov r31, r1
    ldi r24, WATCHDOG_UNLOCK_MASK
    st Z, r24
    st Z, r1
    sbi _SFR_IO_ADDR(DDRD), USB_MINUS_BIT
usb_disconnect_delay_outer:
    ldi r24, LOW8(USB_DISCONNECT_INNER_LOOPS)
    ldi r25, HIGH8(USB_DISCONNECT_INNER_LOOPS)
usb_disconnect_delay_inner:
    sbiw r24, 1
    brne usb_disconnect_delay_inner
startup_clear_sram_byte:
    st -Y, r1
startup_check_sram_end:
    cpi r28, LOW8(USB_CONTEXT_BASE)
    brne usb_disconnect_delay_outer
    cbi _SFR_IO_ADDR(DDRD), USB_MINUS_BIT
    movw r2, r24
    mov r8, r1          /* TX ACK outstanding: initially none */
    movw r6, r24
    /* r3 is the pending SPM/RUN command, initialized via MOVW r2:r3 above.
     * Persistent r4:r5 is assigned by SELECT before any READ8/WRITE4. */
    ldi r24, USB_PID_NAK
    std Y+CTX_TX_LENGTH, r24
    ldi r24, USB_NO_MESSAGE
    std Y+CTX_MSG_LENGTH, r24
    ldi r24, USB_INTERRUPT_ENABLE_MASK
    std Z+(_SFR_MEM_ADDR(PCMSK2) - _SFR_MEM_ADDR(WDTCSR)), r24
    std Z+(_SFR_MEM_ADDR(PCICR) - _SFR_MEM_ADDR(WDTCSR)), r24
led_init:
    LED_INIT
led_init_done:
bootloader_poll_begin:
    ldi r26, LOW8(USB_POLL_TIMEOUT_COUNT)
    ldi r27, HIGH8(USB_POLL_TIMEOUT_COUNT)
    ldi r24, USB_RESET_SE0_SAMPLES
usb_poll_sample_bus:
    in r25, _SFR_IO_ADDR(PIND)
    andi r25, USB_LINE_MASK
    brbs SREG_Z, usb_poll_check_reset_duration
    ldi r24, USB_RESET_SE0_SAMPLES
usb_poll_check_reset_duration:
    subi r24, 0x01
    brbc SREG_Z, usb_poll_check_packet_pending
    std Y+CTX_NEW_DEVICE_ADDRESS, r1
    std Y+CTX_DEVICE_ADDRESS, r1
    mov r8, r1
    ldi r17, USB_PID_NAK
    std Y+CTX_TX_LENGTH, r17
    ldi r17, USB_NO_MESSAGE
    std Y+CTX_MSG_LENGTH, r17
usb_poll_check_packet_pending:
    sbic _SFR_IO_ADDR(PCIFR), PCIF2
    rjmp .Lpacket_pending
usb_poll_advance_timeout:
    sbiw r26, 1
    brne usb_poll_sample_bus
bootloader_poll_timeout:
    rjmp bootloader_process_pending_command
.Lpacket_pending:
    rcall USB_handler
bootloader_process_pending_command:
    /* Watchdog was disabled at RESET before the 301ms USB disconnect delay. */
usb_control_process_received_packet:
    ldd r18, Y+CTX_RX_LENGTH
    cpi r18, (USB_SETUP_BYTES + USB_RX_PACKET_OVERHEAD)
    brne .Lsetup_not_received
    rcall usb_validate_setup_token
.Lsetup_not_received:
    std Y+CTX_RX_LENGTH, r1
bootloader_check_pending_command:
.Lcommand_eeprom_idle:
bootloader_dispatch_command:
    sbrc r3, 0
    rjmp flash_erase_selected_page
    sbrs r3, 2
    rjmp bootloader_clear_command
    or r26, r27
    brne usb_tx_prepare_pending_reply
    rjmp bootloader_start_application
flash_erase_selected_page:
flash_commit_buffered_page:
    movw r30, r4
    sbrc r3, 2
    sbiw r30, AVR_WORD_BYTES
flash_do_spm:
    andi r30, FLASH_PAGE_ALIGN_MASK
#if LOW8(BOOT_AT) == 0
    cpi r31, HIGH8(BOOT_AT)
#else
    cpi r30, LOW8(BOOT_AT)
    ldi r18, HIGH8(BOOT_AT)
    cpc r31, r18
#endif
    brsh bootloader_clear_command
    out _SFR_IO_ADDR(SPMCSR), r3
    spm
bootloader_clear_command:
    mov r3, r1
#include "vusb_ep0.inc"
bootloader_check_idle_timeout:
    rcall usb_service_pending
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
    rcall usb_service_pending
    rjmp bootloader_poll_begin
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
#if LED_MODE != NONE
    out _SFR_IO_ADDR(DDRD), r1
#endif
    sts _SFR_MEM_ADDR(PCICR), r1
    sts _SFR_MEM_ADDR(PCMSK2), r1
app_jump:
    .word (AVR_RJMP_OPCODE | (((bootloader_start - POSTSCRIPT_BYTES - app_jump - AVR_WORD_BYTES) / AVR_WORD_BYTES) & AVR_RJMP_OFFSET_MASK))
#include "compact_memory.inc"
#include "vusb_requests.inc"
usb_service_pending:
    sbis _SFR_IO_ADDR(PCIFR), PCIF2
.Lservice_done:
    ret
    rcall USB_handler
#include "vusb_setup.inc"
#include "vusb_standard.inc"
