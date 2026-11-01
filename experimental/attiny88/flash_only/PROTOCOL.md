# Flash-only vendor protocol v4.2

This target is separate from the EEPROM-capable v3.0 loader. The host selects
geometry from an exact recognized bcdDevice before sending vendor commands.
Unknown identities fail closed; neither a guessed RESET nor a command probe
identifies a device layout.

The cursor no-LED candidate uses bcdDevice 0x0470, BOOT_AT 0x1A40 and a
postscript at 0x1A3C. Earlier archive and absolute-address audit profiles are
incompatible and rejected. Alternate placements and LED builds advertise
0xFFFF unless explicitly assigned a new recognized layout.

| Request | Host transfer | Parameters and meaning |
| --- | --- | --- |
| 1 SELECT | Vendor device OUT | wIndex selects a word-aligned common Flash cursor and clears the temporary page buffer |
| 2 SELECT+ERASE | Vendor device OUT | Select an application page and erase it after eligible status ACK |
| 3 WRITE4 | Vendor device OUT | wValue then wIndex carry four little-endian payload bytes; advance four bytes after status ACK |
| 4 RUN | Vendor device OUT | Defer application handoff until eligible status ACK |
| 0xB0 READ8 | Vendor device IN | wValue=wIndex=0; read up to eight bytes at the cursor, advancing by the actual count after valid OUT status |

Opcode5 has no command. The 16th sequential WRITE4 fills the 64-byte page and
queues automatic programming; no explicit COMMIT_PAGE transfer is needed.
The host pads incomplete application pages with 0xFF and never mixes READ8
into a partially staged write page. Standard USB queries do not move the
vendor cursor. EEPROM commands do not exist in this permanent loader.

Vendor OUT/IN use bmRequestType 0x40/0xC0. Vendor OUT parameters are entirely
in SETUP with wLength zero. The client validates fields, geometry and complete
page planning under the [cursor contract](docs/HOST_CURSOR_PROTOCOL_4_2.md).
The loader separates standard, class/reserved and vendor requests; unsupported
class/reserved requests STALL. The final MCU erase/page-program guard protects
the bootloader. Buffer-slot loading cannot itself modify Flash.

IN DATA/PID stays cached until an eligible, correctly framed ACK. Repeated IN
before ACK returns identical bytes and PID. The short ACK eligibility marker
is distinct from the durable outstanding-DATA flag. WRITE4 stages its two
hardware-buffer words inside the validated status-ACK path, before a new
SETUP can replace the accepted payload. That path advances the cursor once.
Only the final slow page program remains deferred to the foreground.

READ8 commits its consumed pointer on valid OUT status; repeated status copies
the same pointer. Standard reads leave the cursor intact. A replacement SETUP
or bus reset cancels the obsolete unacknowledged request and its queued work.
SET_ADDRESS becomes active only after its status ACK.

ACK eligibility and SETUP/OUT token authorization expire if no next SOP appears
within the USB 16..18-bit-time transaction timeout. Cached IN DATA remains
available for retry. Failed SYNC cancels authorization. Accepted SETUP fields
stay in preserved registers, so ignored packets cannot change accepted data.
A control-read OUT status may confirm final IN data whose ACK was lost; it
cannot replace a write request's required IN status ACK.

USB status completion does not mean Flash has finished: SPM erase and page
program halt this CPU. The host uses a configurable 7ms quiet interval after
each separate erase/program operation. It verifies erased Flash, reselects
the page because reads advanced the cursor, sends 16 WRITE4 requests, waits
and verifies the page. A final whole-image pass detects later corruption of
an earlier page before reporting success or allowing RUN.

Any ambiguous USB result invalidates the host cursor and erase/page plan.
The same transport cannot continue or blindly replay WRITE4, including the
last request whose automatic programming may already have completed. Start
a new complete erase/verify/program plan. Hardware buffer words may not be
loaded twice before clearing; even identical repeated loads are not assumed
idempotent. See ATtiny88 datasheet section 19.0.2 and the independent NVM model.

Application images remain linked at zero. Only RESET is redirected, original
interrupt vectors remain intact, and the four-byte postscript carries the
original application entry. Foreign prepatched images need their original
layout metadata; the host must not guess an entry from arbitrary vector bytes.

EEPROM staging is an offline temporary-application plan. A reconnect is not an
independent success proof and must not automatically permit main-image restore.
All hardware programming remains outside software verification.

The user-approved receive CRC exception is explicit: incoming DATA CRC 16 is
not validated, either before ACK or later. This includes SETUP's DATA packet.
Outgoing DATA CRC 16 and incoming token CRC5 remain required. Full-image final
readback improves detection of wrong writes but does not make this exception
USB compliant. No additional protocol waiver is adopted.

The existing idle counter exits after 1024 quiet 5 ms polls, approximately
5.12 seconds plus processing time. It cannot abandon an unacknowledged IN DATA
packet. USB completion-status polling remains deferred; no new vendor status
operation has been added.

Normative audit input is the USB-IF [USB 2.0 specification package](https://www.usb.org/document-library/usb-20-specification).
The local PDF SHA-256 is
`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`.
Relevant sections are 7.1.4.1 (crossover tolerance), 7.1.9.1 (stuffing/dribble),
7.1.13.2.1 (receiver EOP), 7.1.18/19 (turnaround/timeouts), 8.5/8.7 (control and
error recovery), and 9.4 (standard requests).

Dribble is limited by the **entire final run of at most six ones**, including
the original PID/CRC bits. ACK 0xD2 already ends in two ones, so it permits at
most four additional ones. A successfully received stuffed-zero transition
does not form part of a no-transition dribble extension.

The models execute emitted AVR instructions and independently generate USB
signals. Their exact 16 MHz clock excludes analog voltage thresholds, oscillator
drift, metastability and physical hubs. The crossover fixture represents possible
single-ended zero reads during a 210 ns differential transition; below VIH does
not necessarily mean below VIL. It reports premature handler effects separately
from receive mismatches/discards. These are digital qualification results, not
measurements of this board or a USB-IF compliance claim.
