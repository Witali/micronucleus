# External software USB references

`SOURCES.tsv` pins the fourteen source files inspected for the
[external review](../../docs/SOFTWARE_USB_REFERENCES.md). It records exact
repository commits, Git blob SHA1 identities and SHA256 content hashes.
Original source is not vendored into the firmware or its release selection.

## USBtiny receiver experiment

`audit_usbtiny.py` compiles the pinned eight-bit receive/stuffing excerpt and
executes its actual AVR words. It supplies the native 12 MHz clock scale and
an ideal first-PID sample, then compares minimum observed EOP against nominal
and full-width controls. This is a bounded reference audit, not a device image
or whole-stack qualification.

From the Flash-only directory with the existing LLVM AVR tools:

```sh
python3 tools/external_usb/audit_usbtiny.py --download
python3 tools/external_usb/audit_usbtiny.py --source build/external_usb/usbtiny-int.S
```

The first command explicitly downloads the pinned public source. The second
uses a local copy. Both check its original Git blob before compilation.
Source, generated fixture, linked words and report remain in ignored `build/`.
The generated code must not be programmed onto a board.

The reviewed reference produces 45/45 correct nominal packets and 45/45
correct full-width controls, but 0/45 correct minimum-EOP packets. The tool
therefore **exits with status 1** and records the receiver failures. This is
the expected reproducible finding, not a green USB-conformance result. It is
separate from `verify_receiver.py` and cannot select a programming profile.
