/* Micronucleus+ compact Pass27 research candidate, ATtiny88 at 16 MHz.
 * Based on the preserved Pass26 assembly checkpoint; GPL-2.0-or-later.
 * Source modules follow the adjacent Block64 layout but use a separate protocol.
 * Original Micronucleus contributors' licensing/provenance remains in the
 * preserved handoff and LICENSE_GPL-2.0.txt. No hardware USB validation yet.
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

/* RESET word is supplied prepatched by the host. Do NOT rewrite it here. */
/* Append one host-supplied word to the temporary Flash page buffer.
 * In: R4:R5 cursor, R25:R24 data, YH=SELFPRGEN=1. Out: cursor +2, R1=0.
 * This does not write Flash; page commit is deferred to the guarded SPM worker.
 */
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
/* Clear USB state and pending EEPROM count after RESET. Do not enter this
 * routine by a software jump: stack and global interrupt state are reset-owned.
 */
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
/* Preserve reset cause, disable the inherited watchdog, disconnect for
 * roughly 301 ms, then enable pin-change flag polling (interrupts stay off).
 */
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
sbi _SFR_IO_ADDR(PCIFR), PCIF2
bootloader_process_pending_command:
wdr
/* EEPROM writes must complete before SPM erase/write/exit. */
rcall ee_check_busy
brne usb_control_process_received_packet
/* Deferred operations run after the USB polling window. R3 uses the real
 * SPM command (erase=3, commit=5), RUN=4, SELECT marker=2, or idle=0.
 * SPM is forbidden while the asynchronous EEPROM worker is active.
 */
bootloader_dispatch_command:
mov r24, r3
/* Only pending erase (3) and page-write (5) have bit zero set.
 * SELECT leaves 2, RUN leaves 4, and idle leaves 0. */
sbrc r24, 0
rjmp flash_erase_selected_page
cpi r24, CMD_EXIT
brne bootloader_clear_command
or r26, r27
brne usb_control_process_received_packet
rjmp bootloader_start_application
flash_erase_selected_page:
flash_commit_buffered_page:
movw r30, r4
/* WRITE ends at the next page; ERASE starts at the selected page. */
sbrc r24, 2
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
out _SFR_IO_ADDR(SPMCSR), r24
spm
bootloader_clear_command:
mov r3, r1
#include "vusb_ep0.inc"

/* Service at most one EEPROM byte per iteration, advance idle timeout,
 * and enter the application only when its postscript is not erased.
 */
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

#include "compact_memory.inc"
#include "vusb_standard.inc"
#include "compact_eeprom.inc"
