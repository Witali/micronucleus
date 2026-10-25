/* ATtiny88 adaptation of the in-place flow in firmware/upgrade.c.
 * Original Micronucleus contributors and this adaptation: GPL-2.0-or-later.
 * Application at 0x0080; embedded image and code remain below both loaders.
 */
#include <avr/boot.h>
#include <avr/eeprom.h>
#include <avr/interrupt.h>
#include <avr/io.h>
#include <avr/pgmspace.h>
#include <avr/wdt.h>
#include <stdint.h>
#include "image.h"

#if !defined(__AVR_ATtiny88__) || SPM_PAGESIZE != 64 || FLASHEND != 8191
#error This updater is only for the 8 KiB ATtiny88 with 64-byte Flash pages
#endif

#define APP_ENTRY 0x0080u
#define POSTSCRIPT_PAGE (IMAGE_ADDRESS - SPM_PAGESIZE)
#define RESET_TO(address) (0xc000u | (((address) / 2u - 1u) & 0x0fffu))

void updater_abort(uint8_t code) __attribute__((noinline, noreturn));
void updater_complete(void) __attribute__((noinline, noreturn));

void updater_abort(uint8_t code)
{
    /* A failed byte verification never commits RESET to the new loader. */
    (void)code;
    PORTD &= (uint8_t)~_BV(PD0);
    for (;;) { __asm__ __volatile__("nop"); }
}

void updater_complete(void)
{
    PORTD |= _BV(PD0);
    wdt_enable(WDTO_15MS);
    for (;;) { __asm__ __volatile__("nop"); }
}

static uint16_t crc_image(void)
{
    uint16_t crc = 0xffff;
    for (uint16_t i = 0; i < sizeof bootloader_image; ++i) {
        crc ^= (uint16_t)pgm_read_byte(bootloader_image + i) << 8;
        for (uint8_t bit = 0; bit < 8; ++bit)
            crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
    }
    return crc;
}

static void replace_page(uint16_t address, const uint16_t *words)
{
    if ((address & (SPM_PAGESIZE - 1)) ||
        !(address == 0 || address == POSTSCRIPT_PAGE ||
          (address >= IMAGE_ADDRESS && address <= FLASHEND - SPM_PAGESIZE + 1)))
        updater_abort(3);
    eeprom_busy_wait();
    boot_spm_busy_wait();
    uint8_t clear = _BV(CTPB) | _BV(SELFPRGEN);
    __asm__ __volatile__("out %0, %1\n\tspm" ::
                         "I" (_SFR_IO_ADDR(SPMCSR)), "r" (clear) : "memory");
    boot_page_erase(address);
    boot_spm_busy_wait();
    for (uint8_t i = 0; i < SPM_PAGESIZE / 2; ++i)
        boot_page_fill(address + 2u * i, words[i]);
    /* Keep Z page-aligned for PGWRT, independently of the last fill word. */
    boot_page_write(address);
    boot_spm_busy_wait();
    for (uint8_t i = 0; i < SPM_PAGESIZE / 2; ++i)
        if (pgm_read_word(address + 2u * i) != words[i])
            updater_abort(4);
}

int main(void)
{
    cli();
    MCUSR = 0;
    wdt_disable();
    PCICR = 0;
    PCMSK2 = 0;
    /* MH-Tiny88 D- is PD1; disconnect only USB and drive the PD0 LED. */
    PORTD &= (uint8_t)~(_BV(PD0) | _BV(PD1) | _BV(PD2));
    DDRD = (DDRD & (uint8_t)~_BV(PD2)) | _BV(PD0) | _BV(PD1);
    eeprom_busy_wait();
    if (boot_lock_fuse_bits_get(GET_EXTENDED_FUSE_BITS) & 1)
        updater_abort(1);
    if (crc_image() != IMAGE_CRC)
        updater_abort(2);

    uint16_t page[SPM_PAGESIZE / 2];
    for (uint8_t i = 0; i < SPM_PAGESIZE / 2; ++i)
        page[i] = pgm_read_word(2u * i);
    /* A reset between completed operations restarts this intact application. */
    page[0] = RESET_TO(APP_ENTRY);
    replace_page(0, page);

    for (uint16_t offset = 0; offset < sizeof bootloader_image; offset += SPM_PAGESIZE) {
        for (uint8_t i = 0; i < SPM_PAGESIZE / 2; ++i)
            page[i] = pgm_read_word(bootloader_image + offset + 2u * i);
        replace_page(IMAGE_ADDRESS + offset, page);
    }
    /* Force the new loader to stay active: no application postscript exists. */
    for (uint8_t i = 0; i < SPM_PAGESIZE / 2; ++i) page[i] = 0xffff;
    replace_page(POSTSCRIPT_PAGE, page);

    /* Commit a new RESET only after every target byte has passed readback. */
    for (uint8_t i = 0; i < SPM_PAGESIZE / 2; ++i)
        page[i] = pgm_read_word(2u * i);
    page[0] = RESET_TO(IMAGE_ADDRESS);
    replace_page(0, page);
    updater_complete();
}
