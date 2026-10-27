# V-USB sources

This directory contains the unmodified files needed for a 16 MHz HID application
from [Objective Development's V-USB](https://github.com/obdev/v-usb), commit
`801242072fa035e1839e3571df0d9a18e9cec95c` (driver version 20121206).

The bootloader's separate `firmware/usbdrv` is a reduced, polling-only fork and
cannot supply this application's interrupt endpoint. No bootloader files are
modified by this example. Other clock-rate backends and debug UART support are
not included here.

`SHA256SUMS` records the exact upstream bytes. `verify.py` checks these hashes.
The driver retains its original copyright notices and GPL license in
`License.txt`. The example's first-party sources are GPL-2.0-or-later.

The shared keyboard identity is `16c0:27db`. Its terms are recorded in
`USB-IDs-for-free.txt`, under IDs for discrimination by serial number. A serial
number may be omitted when only the operating system's class driver is used,
as in this example. Manufacturer and product strings are generic project names.
