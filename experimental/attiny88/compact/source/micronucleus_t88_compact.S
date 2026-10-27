/* Micronucleus+ compact Pass28 research candidate, ATtiny88 at 16 MHz.
 * Based on the preserved Pass26 assembly checkpoint; GPL-2.0-or-later.
 * Source modules follow the adjacent Block64 layout but use a separate protocol.
 * Original Micronucleus contributors' licensing/provenance remains in the
 * preserved handoff and LICENSE_GPL-2.0.txt. Permanent no-LED installation and
 * the hardware smoke-test scope are recorded in docs/HARDWARE_INSTALL30.md.
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

/* End-of-PHY anchors retained for the opcode/timing audit. Flash WRITE4 now
 * stages its two words directly in compact_memory.inc; no helper body remains.
 * RESET/postscript patching stays on the host. */
flash_buffer_append_word:
flash_buffer_load_word:
/* Clear USB state and pending EEPROM count after RESET. Do not enter this
 * routine by a software jump: stack and global interrupt state are reset-owned.
 */
startup:
    eor r1, r1
/* Datasheet-defined RESET defaults: SPL/SPH=RAMEND, SREG=0.
 * This firmware entry is legal only through hardware RESET or WDT RESET;
 * a direct software jump into the bootloader without RESET is unsupported. */
    ldi r28, LOW8(USB_CONTEXT_BASE + USB_CONTEXT_BYTES)
    ldi r29, HIGH8(USB_CONTEXT_BASE)
/* Preserve reset cause, disable the inherited watchdog, disconnect for
 * roughly 301 ms, then enable pin-change flag polling (interrupts stay off).
 */
main:
    wdr
    in r24, _SFR_IO_ADDR(MCUSR)
    out _SFR_IO_ADDR(GPIOR0), r24
    out _SFR_IO_ADDR(MCUSR), r1
/* Keep one base pointer for the timed watchdog pair and the later PCINT
 * enables. The disconnect loop does not touch Z; nearby STD stores save
 * words without changing the two-cycle watchdog write separation. */
    ldi r30, LOW8(_SFR_MEM_ADDR(WDTCSR))
    mov r31, r1
    ldi r24, WATCHDOG_UNLOCK_MASK
    st Z, r24
    st Z, r1
    sbi _SFR_IO_ADDR(DDRD), USB_MINUS_BIT
/* Reuse the SRAM cursor as the disconnect-delay outer counter. Clear one
 * byte after each delay, so all 44 bytes are zero and Y=0x0100 before USB
 * is enabled. This removes the separate outer counter and clear loop.
 * R24:R25 finish at zero, also initializing the memory and idle cursors. */
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
/* The countdown ends at zero; clear queue count R2 and command R3 together. */
    movw r2, r24
    movw r4, r24
    movw r6, r24
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
/* Poll for up to 5 ms, recognizing sustained SE0 as a USB bus reset.
 * Every predecessor preserves Y=USB_CONTEXT_BASE; X is the poll countdown.
 */
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
/* Every poll-begin predecessor leaves Y at the USB context base. */
    std Y+CTX_NEW_DEVICE_ADDRESS, r1
    std Y+CTX_DEVICE_ADDRESS, r1
usb_poll_check_packet_pending:
    sbis _SFR_IO_ADDR(PCIFR), PCIF2
    rjmp usb_poll_advance_timeout
    rcall USB_handler
bootloader_process_pending_command:
    wdr
/* The main path proves length without paying a subroutine return on idle.
 * A valid SETUP shares the token validator and discards this one call frame. */
usb_control_process_received_packet:
    ldd r18, Y+CTX_RX_LENGTH
    cpi r18, (USB_SETUP_BYTES + USB_RX_PACKET_OVERHEAD)
    brne .Lsetup_not_received
    rcall usb_validate_setup_token
.Lsetup_not_received:
    std Y+CTX_RX_LENGTH, r1
bootloader_check_pending_command:
/* EEPROM writes must complete before SPM erase/write/exit. This gate also
 * holds an older deferred RUN until a later EEPROM queue has fully drained.
 * With only two readiness sites, these inline IN/OR pairs save a helper/RET. */
    in r24, _SFR_IO_ADDR(EECR)
    or r24, r2
    brne usb_tx_prepare_pending_reply
.Lcommand_eeprom_idle:
/* Deferred operations run after the USB polling window. R3 uses the real
 * SPM command (erase=3, commit=5), RUN=4, SELECT marker=2, or idle=0.
 * SPM is forbidden while the asynchronous EEPROM worker is active.
 */
bootloader_dispatch_command:
/* Only pending erase (3) and page-write (5) have bit zero set.
 * SELECT leaves 2, RUN leaves 4, and idle leaves 0. */
    sbrc r3, 0
    rjmp flash_erase_selected_page
/* Only 0/2/3/4/5 are reachable: after odd SPM commands, bit2 identifies RUN. */
    sbrs r3, 2
    rjmp bootloader_clear_command
    or r26, r27
    brne usb_tx_prepare_pending_reply
    rjmp bootloader_start_application
flash_erase_selected_page:
flash_commit_buffered_page:
    movw r30, r4
/* WRITE ends at the next page; ERASE starts at the selected page. */
    sbrc r3, 2
    sbiw r30, AVR_WORD_BYTES
/* Align to a physical page and protect every address at/above BOOT_AT.
 * The shared executor is the final guard for both erase and write requests.
 */
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
    out _SFR_IO_ADDR(SPMCSR), r3
    spm
bootloader_clear_command:
    mov r3, r1
/* Both idle and completed SPM paths fall into packet preparation. Keeping
 * that hot continuation nearby removes the distant-TX branch trampoline. */
#include "vusb_ep0.inc"

/* Service at most one EEPROM byte per iteration, advance idle timeout,
 * and enter the application only when its postscript is not erased.
 */
bootloader_check_idle_timeout:
/* Bound the no-message path before a ready EEPROM worker starts a byte. */
    rcall usb_service_pending
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
    rcall usb_service_pending
    rjmp bootloader_poll_begin
usb_poll_advance_timeout:
    sbiw r26, 1
    brbs SREG_Z, bootloader_poll_timeout
    rjmp usb_poll_sample_bus
bootloader_poll_timeout:
    rjmp bootloader_process_pending_command
/* Release USB pins/PCINT enables and jump to the host-prepared postscript.
 * The application owns its vector table; the bootloader only redirects RESET.
 */
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

/* Callable request handlers remain adjacent for their short BRxx edges.
 * app_jump above prevents ordinary execution from falling into this block. */
#include "compact_memory.inc"
#include "vusb_requests.inc"
#include "vusb_standard.inc"
#include "compact_eeprom.inc"

/* Cooperative foreground service. PHY preserves X, R24 and R25.
 * R18 and flags are scratch at callers; CRC reconstructs C with SEC.
 * Every caller is reached by a jump, so abort discards just this RCALL.
 */
usb_service_pending:
    sbis _SFR_IO_ADDR(PCIFR), PCIF2
.Lservice_done:
    ret
/* The invalid SETUP validator shares this fast RET. On a new SETUP the
 * accepted path below falls directly into field capture after discarding
 * the original caller frame; it does not return to an obsolete builder. */
    rcall USB_handler
#include "vusb_setup.inc"
