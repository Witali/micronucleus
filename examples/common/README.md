# Shared ATtiny88 example support

`avr.py` owns offline toolchain discovery, artifact validation, and the common
16 MHz HID build. Each example retains its own sources and Flash/SRAM budgets.
It never opens a USB device. Run each example's existing `build.py` or `verify.py`.

`verification.py` shares artifact decoding and compact application placement checks.
Descriptor expectations and behavior scenarios remain in each example.

`usbdrv/` contains the pinned, unmodified V-USB driver shared by the keyboard
and media remote. Its provenance, license, and hashes are in
[UPSTREAM.md](usbdrv/UPSTREAM.md). The bootloader's separate driver is unchanged.

From the repository root, shared HEX-boundary tests run with:

~~~sh
PYTHONPATH=examples python3 -m unittest discover -s examples/common/tests
~~~

See [validation results](VALIDATION.md) for baseline artifact hashes and checks.
