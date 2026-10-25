/* MH-Tiny88 application smoke test: three short flashes, one long, then pause. */
#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/power.h>
#include <avr/wdt.h>
#include <util/delay.h>
#include <stdint.h>

int main(void)
{
    cli();
    MCUSR = 0;
    wdt_disable();
    clock_prescale_set(clock_div_1);
    PORTD &= (uint8_t)~_BV(PD0);
    DDRD |= _BV(PD0);

    for (;;) {
        for (uint8_t i = 0; i < 3; ++i) {
            PORTD |= _BV(PD0);
            _delay_ms(120);
            PORTD &= (uint8_t)~_BV(PD0);
            _delay_ms(180);
        }
        PORTD |= _BV(PD0);
        _delay_ms(800);
        PORTD &= (uint8_t)~_BV(PD0);
        _delay_ms(1500);
    }
}
