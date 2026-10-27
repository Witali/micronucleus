/* Frozen GPL-2.0-or-later Micronucleus compact source; see README.md. */
.set led_config_mode, 0
.set led_config_ddr_io, 0x0a
.set led_config_port_io, 0x0b
.set led_config_pin, 0
.set led_config_blink_mask, 0x4c
.macro LED_INIT
.endm
.macro LED_TICK
.endm
.macro LED_EXIT
.endm

.section .text
.org 0x1c00
.global bootloader_start
bootloader_start:
rjmp startup
.byte 9, 2
.byte (((9 + 9)) & 0xff), ((((9 + 9)) >> 8) & 0xff)
.byte 1, 1, 0, 0x80, (100 / 2)
.byte 9, 4, 0, 0, 0, 0, 0, 0, 0
.byte 18, 1
.byte ((0x0110) & 0xff), (((0x0110) >> 8) & 0xff), 0xff, 0, 0, 8
.byte ((0x16d0) & 0xff), (((0x16d0) >> 8) & 0xff), ((0x0753) & 0xff), (((0x0753) >> 8) & 0xff)
.byte ((0x0560) & 0xff), (((0x0560) >> 8) & 0xff), 0, 0, 0, 1
USB_handler:
eor r28, r28
usb_rx_wait_for_j:
inc r28
sbis ((0x09)), 1
brbc 1, usb_rx_wait_for_j
usb_rx_wait_for_k:
sbis ((0x09)), 1
rjmp usb_rx_found_k
sbis ((0x09)), 1
rjmp usb_rx_found_k
sbis ((0x09)), 1
rjmp usb_rx_found_k
sbis ((0x09)), 1
rjmp usb_rx_found_k
sbis ((0x09)), 1
rjmp usb_rx_found_k
sbis ((0x09)), 1
rjmp usb_rx_found_k
sbi ((0x1b)), 2
rjmp usb_return_context
usb_rx_found_k:
ldi r28, ((0x100 + 22) & 0xff)
rcall usb_return_polynomial
ldi r22, 0x55
sbis ((0x09)), 1
rjmp usb_rx_sync_confirmed
push r0
pop r0
rjmp usb_rx_wait_for_k
usb_rx_sync_confirmed:
ldi r30, ((0x100) & 0xff)
ldi r31, (((0x100) >> 8) & 0xff)
rjmp usb_rx_delay_complete
usb_rx_delay_complete:
push r16
ldi r18, 0x00
ldi r20, 0x10
pop r16
in r16, ((0x09))
andi r16, ((1 << 1) | (1 << 2))
bst r16, 1
bld r18, 7
rjmp .+0
ldi r21, 0x00
ldi r23, (8 + 3)
rjmp usb_rx_sample_odd_bit
usb_rx_unstuff_bit6:
andi r17, ((1 << 1) | (1 << 2))
ori r20, (1 << 6)
andi r18, 0x7f
mov r16, r17
subi r21, ((-1) & 0xff)
rjmp usb_rx_sample_bit7
usb_rx_unstuff_bit7:
ori r20, (1 << 7)
in r17, ((0x09))
andi r17, ((1 << 1) | (1 << 2))
andi r18, 0x7f
subi r21, 2
rjmp usb_rx_finish_byte
usb_rx_unstuff_even_bit:
ori r20, (1 << 6)
in r16, ((0x09))
andi r18, 0x7f
andi r16, ((1 << 1) | (1 << 2))
brbs 1, usb_rx_end_packet
subi r21, ((-1) & 0xff)
rjmp usb_rx_unstuff_even_resume_jump
usb_rx_unstuff_even_resume_jump:
rjmp usb_rx_shift_stuff_mask
usb_rx_unstuff_odd_bit:
ori r20, (1 << 5)
in r17, ((0x09))
andi r18, 0x7f
andi r17, ((1 << 1) | (1 << 2))
brbs 1, usb_rx_end_packet
subi r21, ((-1) & 0xff)
rjmp usb_rx_unstuff_odd_resume_jump
usb_rx_unstuff_odd_resume_jump:
rjmp usb_rx_advance_bit_pair
usb_rx_decode_bit6:
andi r16, ((1 << 1) | (1 << 2))
eor r17, r16
subi r21, 0x01
brbc 2, usb_rx_shift_bit6
subi r21, ((-3) & 0xff)
nop
usb_rx_shift_bit6:
subi r17, 0x01
ror r18
usb_rx_sample_bit7:
cpi r18, 0xfc
in r17, ((0x09))
brbc 0, usb_rx_unstuff_bit6
andi r17, ((1 << 1) | (1 << 2))
eor r16, r17
subi r16, 0x01
ror r18
usb_rx_finish_byte:
cpi r18, 0xfc
brbc 0, usb_rx_unstuff_bit7
eor r20, r18
st Y+, r20
usb_rx_sample_even_bit:
in r16, ((0x09))
andi r16, ((1 << 1) | (1 << 2))
eor r17, r16
andi r20, 0x3f
subi r17, 0x01
ror r18
cpi r18, 0xfc
brbc 0, usb_rx_unstuff_even_bit
usb_rx_shift_stuff_mask:
lsr r20
lsr r20
usb_rx_sample_odd_bit:
in r17, ((0x09))
andi r17, ((1 << 1) | (1 << 2))
brbs 1, usb_rx_end_packet
eor r16, r17
subi r16, 0x01
ror r18
cpi r18, 0xfc
brbc 0, usb_rx_unstuff_odd_bit
usb_rx_advance_bit_pair:
subi r22, ((-0x55) & 0xff)
brbs 0, usb_rx_sample_even_bit
subi r23, 0x01
in r16, ((0x09))
brbc 0, usb_rx_decode_bit6
usb_rx_overflow:
sbi ((0x1b)), 2
usb_rx_ignore_packet:
eor r16, r16
rjmp usb_rx_store_token
usb_rx_end_packet:
subi r23, (8 + 3)
neg r23
sub r28, r23
sbci r29, 0x00
sbi ((0x1b)), 2
ldd r16, Y+0
cpi r16, 0xc3
brbs 1, usb_rx_handle_data
cpi r16, 0x4b
brbs 1, usb_rx_handle_data
ldd r18, Z+12
ldd r17, Y+1
add r17, r17
cpse r17, r18
rjmp usb_rx_ignore_packet
cpi r16, 0x69
brbs 1, usb_rx_handle_in
cpi r16, 0x2d
brbs 1, usb_rx_handle_setup_or_out
cpi r16, 0xe1
brbc 1, usb_rx_ignore_packet
usb_rx_handle_setup_or_out:
ldi r28, 10
usb_rx_wait_for_data:
in r17, ((0x1b))
sbrc r17, 2
rjmp usb_rx_store_token
dec r28
brbc 1, usb_rx_wait_for_data
usb_rx_store_token:
std Z+20, r16
usb_handler_packet_done:
in r28, ((0x1b))
sbrc r28, 2
rjmp usb_rx_wait_for_j
rjmp usb_return_context
usb_rx_handle_data:
ldd r18, Z+20
and r18, r18
brbs 1, usb_handler_packet_done
ldd r17, Z+18
and r17, r17
brbc 1, usb_tx_send_nak
cpi r23, (3 + 1)
brbs 2, usb_tx_send_ack
std Z+18, r23
std Z+13, r18
rjmp usb_tx_send_ack
usb_rx_handle_in:
ldd r16, Z+18
cpi r16, 0x01
brbc 4, usb_tx_send_nak
ldi r16, 0x5a
ldd r19, Z+15
sbrc r19, 4
rjmp usb_tx_send_count_handshake
std Z+15, r16
ldi r28, ((0x100 + 1) & 0xff)
ldi r29, (((0x100 + 1) >> 8) & 0xff)
rjmp usb_tx_acquire_bus
usb_tx_stuff_regular_bit:
eor r16, r21
ldi r17, 0x00
rjmp usb_tx_stuff_regular_delay
usb_tx_stuff_regular_delay:
nop
out ((0x0b)), r16
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
ldi r20, 0x5a
rjmp usb_tx_prepare_handshake
usb_tx_send_ack:
ldi r19, 0xd2
usb_tx_send_count_handshake:
mov r20, r19
usb_tx_prepare_handshake:
ldi r28, ((20) & 0xff)
ldi r29, (((20) >> 8) & 0xff)
ldi r19, 2
usb_tx_acquire_bus:
in r17, ((0x0a))
ori r17, ((1 << 1) | (1 << 2))
sbi ((0x0b)), 1
in r16, ((0x0b))
out ((0x0a)), r17
ldi r21, ((1 << 1) | (1 << 2))
ldi r18, 0x80
usb_tx_begin_byte:
ldi r22, 0x3b
usb_tx_send_regular_bit:
sbrs r18, 0
eor r16, r21
out ((0x0b)), r16
ror r18
ror r17
usb_tx_check_regular_stuffing:
cpi r17, 0xfc
brbc 0, usb_tx_stuff_regular_bit
lsr r22
brbc 0, usb_tx_send_regular_bit
brbc 1, usb_tx_send_regular_bit
sbrs r18, 0
eor r16, r21
usb_tx_send_bit6:
out ((0x0b)), r16
ror r18
ror r17
cpi r17, 0xfc
brbc 0, usb_tx_stuff_bit6
ror r18
usb_tx_send_bit7:
ror r17
sbrs r17, 7
eor r16, r21
nop
cpi r17, 0xfc
out ((0x0b)), r16
brbc 0, usb_tx_stuff_bit7
ld r18, Y+
dec r19
brbc 1, usb_tx_begin_byte
andi r16, (0xff ^ ((1 << 1) | (1 << 2)))
ldd r17, Z+19
sbiw r28, (20 + 2)
out ((0x0b)), r16
brbs 1, usb_tx_finish_eop
std Z+12, r17
usb_tx_finish_eop:
ori r16, (1 << 1)
ldi r21, 6
usb_tx_eop_delay:
dec r21
brbc 1, usb_tx_eop_delay
out ((0x0b)), r16
sbi ((0x1b)), 2
in r17, ((0x0a))
andi r17, (0xff ^ ((1 << 1) | (1 << 2)))
mov r20, r16
andi r20, (0xff ^ ((1 << 1) | (1 << 2)))
rjmp .+0
rjmp .+0
out ((0x0a)), r17
out ((0x0b)), r20
usb_return_context:
ldi r28, ((0x100) & 0xff)
ldi r29, (((0x100) >> 8) & 0xff)
usb_return_polynomial:
ldi r21, (((0xa001) >> 8) & 0xff)
usb_handler_return:
ret
flash_buffer_append_word:
flash_buffer_load_word:
startup:
eor r1, r1
mov r8, r1
ldi r28, ((0x100 + 44) & 0xff)
ldi r29, (((0x100) >> 8) & 0xff)
main:
wdr
in r24, ((0x34))
out ((0x1e)), r24
out ((0x34)), r1
ldi r24, ((1 << 4) | (1 << 3))
sts ((0x60)), r24
sts ((0x60)), r1
sbi ((0x0a)), 1
usb_disconnect_delay_outer:
ldi r24, ((27359) & 0xff)
ldi r25, (((27359) >> 8) & 0xff)
usb_disconnect_delay_inner:
sbiw r24, 1
brne usb_disconnect_delay_inner
startup_clear_sram_byte:
st -Y, r1
startup_check_sram_end:
cpi r28, ((0x100) & 0xff)
brne usb_disconnect_delay_outer
cbi ((0x0a)), 1
movw r4, r24
movw r6, r24
ldi r24, 0x5a
std Y+15, r24
ldi r24, 0xff
std Y+0, r24
ldi r24, (1 << 2)
sts ((0x6d)), r24
sts ((0x68)), r24
led_init:
LED_INIT
led_init_done:
mov r3, r1
bootloader_poll_begin:
ldi r26, ((((16000000 / 1000) * 5 / 15)) & 0xff)
ldi r27, (((((16000000 / 1000) * 5 / 15)) >> 8) & 0xff)
ldi r24, 100
usb_poll_sample_bus:
in r25, ((0x09))
andi r25, ((1 << 1) | (1 << 2))
brbs 1, usb_poll_check_reset_duration
ldi r24, 100
usb_poll_check_reset_duration:
subi r24, 0x01
brbc 1, usb_poll_check_packet_pending
std Y+19, r1
std Y+12, r1
usb_poll_check_packet_pending:
sbis ((0x1b)), 2
rjmp usb_poll_advance_timeout
rcall USB_handler
bootloader_process_pending_command:
wdr
usb_control_process_received_packet:
ldd r18, Y+18
ldd r19, Y+13
std Y+18, r1
cpi r18, (8 + 3)
brne bootloader_check_pending_command
cpi r19, 0x2d
brne bootloader_check_pending_command
usb_setup_capture_fields:
ldd r24, Y+23
ldd r25, Y+24
ldd r18, Y+12
std Y+19, r18
ldi r18, 0xc3
mov r9, r18
ldi r18, 0x5a
std Y+15, r18
rcall usb_service_pending
andi r24, 0x60
breq .Lstandard_setup
rjmp bootloader_handle_vendor_request
.Lstandard_setup:
rjmp usb_standard_dispatch
bootloader_check_pending_command:
in r24, ((0x1f))
or r24, r8
breq .Lcommand_eeprom_idle
.Lcommand_wait_for_poll:
rjmp usb_tx_prepare_pending_reply
.Lcommand_eeprom_idle:
bootloader_dispatch_command:
mov r24, r3
sbrc r24, 0
rjmp flash_erase_selected_page
cpi r24, 4
brne bootloader_clear_command
or r26, r27
brne .Lcommand_wait_for_poll
rjmp bootloader_start_application
flash_erase_selected_page:
flash_commit_buffered_page:
movw r30, r4
sbrc r24, 2
sbiw r30, 2
flash_do_spm:
andi r30, (0xff ^ (64 - 1))
cpi r31, (((0x1c00) >> 8) & 0xff)
brsh bootloader_clear_command
out ((0x37)), r24
spm
bootloader_clear_command:
mov r3, r1
rjmp usb_tx_prepare_pending_reply
bootloader_check_set_flash_address:
rcall usb_service_pending
tst r25
breq usb_reply_empty
cpi r25, 3
brsh bootloader_check_write4
ldd r4, Y+27
ldd r5, Y+28
mov r3, r25
inc r3
ldi r24, ((1 << 4) | (1 << 0))
out ((0x37)), r24
spm
usb_reply_empty:
ldi r24, 0x00
rjmp usb_reply_store_length
bootloader_check_write4:
cpi r25, 4
breq bootloader_queue_command
brsh usb_reply_empty
ldd r10, Y+25
ldd r11, Y+26
ldd r12, Y+27
ldd r13, Y+28
rcall usb_service_pending
sbrc r5, 7
rjmp ee_write
.Lflash_load_two_words:
movw r30, r4
movw r0, r10
movw r10, r12
out ((0x37)), r29
spm
eor r1, r1
adiw r30, 2
movw r4, r30
rcall usb_service_pending
sbrc r4, 1
rjmp .Lflash_load_two_words
mov r30, r4
andi r30, (64 - 1)
brbc 1, usb_reply_empty
ldi r25, ((1 << 2) | (1 << 0))
bootloader_queue_command:
mov r3, r25
rjmp usb_reply_empty

bootloader_handle_vendor_request:
mov r7, r1
in r24, ((0x1f))
or r24, r8
brne usb_reply_empty
cpi r25, 0xb0
brne bootloader_check_set_flash_address
memory_read:
movw r18, r4
memory_read_eeprom:
memory_read_advance:
ldi r24, 8
add r4, r24
adc r5, r1
rjmp usb_reply_set_pointer
usb_reply_use_scratch_buffer:
ldi r18, ((0x1c00 + ((2 + 0) + (9 + 9)) + 14) & 0xff)
usb_reply_use_flash_pointer:
ldi r19, (((0x1c00 + ((2 + 0) + (9 + 9)) + 14) >> 8) & 0xff)
usb_reply_set_pointer:
movw r14, r18
usb_reply_limit_length:
rcall usb_service_pending
ldd r25, Y+30
cpse r25, r1
rjmp usb_reply_store_length
ldd r25, Y+29
cp r25, r24
brbc 0, usb_reply_store_length
mov r24, r25
usb_reply_store_length:
std Y+0, r24
usb_rx_release_buffer:
usb_tx_prepare_pending_reply:
eor r0, r0
ldi r25, 0x00
rcall usb_service_pending
ldd r24, Y+15
sbrs r24, 4
rjmp bootloader_check_idle_timeout
ldd r24, Y+0
cpi r24, 0xff
brbs 1, bootloader_check_idle_timeout
mov r23, r24
cpi r24, (8 + 1)
brbs 0, usb_tx_prepare_data_packet
ldi r24, 8
usb_tx_prepare_data_packet:
sub r23, r24
cpi r24, 8
sbci r23, 0
std Y+0, r23
ldi r18, (0xc3 ^ 0x4b)
eor r9, r18
std Y+1, r9
usb_tx_initialize_payload_crc:
ldi r26, ((0x100 + 2) & 0xff)
ldi r27, (((0x100 + 2) >> 8) & 0xff)
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
out ((0x21)), r30
sbi ((0x1f)), 0
in r18, ((0x20))
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
brbs 0, usb_crc16_advance_bit_count
eor r0, r29
eor r25, r21
usb_crc16_advance_bit_count:
subi r24, ((-32) & 0xff)
brbs 0, usb_crc16_shift_bit
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
std Y+15, r26
bootloader_check_idle_timeout:
rcall ee_write_step
movw r24, r6
adiw r24, 1
movw r6, r24
subi r24, (((6000 / 5)) & 0xff)
sbci r25, ((((6000 / 5)) >> 8) & 0xff)
brbc 1, usb_poll_resynchronize
ldi r30, (((0x1c00 - 4) + 1) & 0xff)
ldi r31, ((((0x1c00 - 4) + 1) >> 8) & 0xff)
lpm r30, Z
cpi r30, 0xff
brbc 1, bootloader_start_application
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
brbs 1, bootloader_poll_timeout
rjmp usb_poll_sample_bus
bootloader_poll_timeout:
rjmp bootloader_process_pending_command
bootloader_start_application:
led_exit:
led_exit_done:
out ((0x0a)), r1
sts ((0x68)), r1
sts ((0x6d)), r1
app_jump:
.word (0xc000 | (((bootloader_start - 4 - app_jump - 2) / 2) & 0x0fff))
usb_standard_dispatch:
ldd r24, Y+25
cpse r25, r1
rjmp usb_standard_check_set_address
ldi r24, 2
rjmp usb_reply_use_scratch_buffer
usb_standard_check_set_address:
cpi r25, 5
brbc 1, usb_standard_check_get_descriptor
lsl r24
std Y+19, r24
rjmp usb_reply_empty
usb_standard_check_get_descriptor:
rcall usb_service_pending
cpi r25, 6
brbc 1, usb_standard_check_configuration
ldd r24, Y+26
ldi r18, ((0x1c00 + ((2 + 0) + (9 + 9))) & 0xff)
cpi r24, 1
breq desc_ptr
cpi r24, 2
brne ee_std_empty
ldi r18, ((0x1c00 + (2 + 0)) & 0xff)
desc_ptr:
ldi r19, (((0x1c00 + (2 + 0)) >> 8) & 0xff)
ldi r24, 18
rjmp usb_reply_set_pointer
usb_standard_check_configuration:
cpi r25, 8
brbs 1, usb_standard_get_configuration
cpi r25, 9
brbc 1, usb_standard_check_get_interface
cpi r24, 2
ldd r18, Y+26
cpc r18, r1
brsh ee_std_empty
std Y+21, r24
rjmp usb_reply_empty
usb_standard_get_configuration:
ldd r18, Y+21
subi r18, ((-(0x1c00 + ((2 + 0) + (9 + 9)) + 16)) & 0xff)
ldi r24, 1
rjmp usb_reply_use_flash_pointer
usb_standard_check_get_interface:
cpi r25, 10
brne ee_std_empty
usb_standard_scratch_reply:
usb_reply_pointer_trampoline:
legacy_led_on_anchor:
ee_return_one:
ldi r24, 1
rjmp usb_reply_use_scratch_buffer
ee_std_empty:
ee_empty:
ee_bad_addr:
rjmp usb_reply_empty
ee_write:
mov r18, r4
cpi r18, (0x3f + 1) - 4 + 1
brsh ee_bad_addr
ldi r18, 4
mov r8, r18
rjmp usb_reply_empty
ee_write_step:
cpse r8, r1
sbic ((0x1f)), 1
rjmp usb_service_pending
out ((0x21)), r4
out ((0x20)), r10
mov r10, r11
mov r11, r12
mov r12, r13
sbi ((0x1f)), 2
sbi ((0x1f)), 1
inc r4
dec r8
ee_write_step_done:
rjmp usb_service_pending
usb_service_pending:
sbis ((0x1b)), 2
ret
rcall USB_handler
ldd r18, Y+18
cpi r18, (8 + 3)
brne .Lservice_done
ldd r18, Y+13
cpi r18, 0x2d
brne .Lservice_done
pop r18
pop r18
std Y+18, r1
rjmp usb_setup_capture_fields
.Lservice_done:
ret
