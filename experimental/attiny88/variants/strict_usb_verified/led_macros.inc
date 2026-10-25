/* Called only outside the cycle-sensitive USB bit engine.
 * ACTIVE_LOW uses an open-drain output: low = on, input = off.
 * r24 and arithmetic flags are disposable at LED_TICK; r6 is the idle tick.
 */
.set led_config_mode, LED_MODE
.set led_config_ddr_io, LED_DDR_IO
.set led_config_port_io, LED_PORT_IO
.set led_config_pin, LED_PIN
.set led_config_blink_mask, LED_BLINK_MASK

.macro LED_INIT
#if LED_MODE != NONE
    cbi LED_PORT_IO, LED_PIN
#if LED_MODE == ACTIVE_HIGH
    sbi LED_DDR_IO, LED_PIN
#else
    cbi LED_DDR_IO, LED_PIN
#endif
#endif
.endm

.macro LED_TICK
#if LED_MODE != NONE
    mov r24, r6
    andi r24, LED_BLINK_MASK
    brne .Lled_off\@
#if LED_MODE == ACTIVE_HIGH
    sbi LED_PORT_IO, LED_PIN
#else
    sbi LED_DDR_IO, LED_PIN
#endif
    rjmp .Lled_done\@
.Lled_off\@:
#if LED_MODE == ACTIVE_HIGH
    cbi LED_PORT_IO, LED_PIN
#else
    cbi LED_DDR_IO, LED_PIN
#endif
.Lled_done\@:
#endif
.endm

.macro LED_EXIT
#if LED_MODE != NONE
#if LED_MODE == ACTIVE_HIGH
    cbi LED_PORT_IO, LED_PIN
#endif
    cbi LED_DDR_IO, LED_PIN
#endif
.endm
