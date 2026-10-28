"""Recognized corrected Flash-only layout; LED builds are audit inputs only."""

BOOT_AT = 0x1A40
BCD_DEVICE = 0x0470
NO_LED_CODE_BYTES = 1424
USB_PROFILES = {
    BCD_DEVICE: ('Corrected Flash-only v4.2 / no LED', BOOT_AT, NO_LED_CODE_BYTES),
}
