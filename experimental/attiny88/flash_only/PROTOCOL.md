# Flash-only vendor protocol v4.1

This target is separate from the EEPROM-capable v3.0 loader. The host selects
geometry from an exact recognized bcdDevice before sending vendor commands.
Unknown identities fail closed; neither a guessed RESET nor a command probe
identifies a device layout.

The current corrected no-LED candidate uses bcdDevice 0x0460, BOOT_AT 0x1A40,
and a postscript at 0x1A3C. The original 0x0450..0x0452 archive profiles are
preserved as audit inputs and rejected by this corrected client. No LED profile
or alternate placement is admitted by the current client.

| Request | Host transfer | Parameters and meaning |
| --- | --- | --- |
| 1 SELECT | Vendor device OUT | wIndex is a 64-byte Flash page address; clear its temporary page buffer |
| 2 SELECT+ERASE | Vendor device OUT | Select the page and defer physical erase until status ACK |
| 3 WRITE2 | Vendor device OUT | wValue is one little-endian word; wIndex is its absolute byte address |
| 4 RUN | Vendor device OUT | Defer application handoff until the status transfer completes |
| 5 COMMIT_PAGE | Vendor device OUT | Commit the selected page after all 32 words have been staged |
| 0xB0 READ8 | Vendor device IN | wIndex is an absolute Flash byte address; read up to eight bytes |

Vendor device OUT/IN use bmRequestType 0x40/0xC0. WRITE2 and READ8 have no
automatic cursor advancement. EEPROM commands do not exist in this target.
Vendor OUT parameters are entirely in SETUP, with wLength zero. The client
validates vendor direction, recipient, length and parameters under the
[host contract](docs/VENDOR_HOST_CONTRACT.md). The loader sorts standard,
class/reserved and vendor request types; unsupported class/reserved requests
return STALL. Interface class is vendor-specific.
The host validates page/word bounds and the MCU retains the final SPM guard
against erasing or writing its own bootloader pages.

IN DATA/PID stays cached until an eligible, correctly framed ACK. Repeated IN
before ACK must return the same bytes and PID. ACK eligibility is short-lived;
the durable pending-DATA flag is separate and must block SPM/application exit.
A replacement SETUP or bus reset cancels the obsolete transfer and deferred
work. SET_ADDRESS takes effect only after its status ACK.

ACK eligibility and SETUP/OUT token authorization expire if no next SOP appears
within the USB 16..18-bit-time transaction timeout. Cached IN DATA remains
available for retry. A failed SYNC also cancels authorization. Accepted SETUP
parameters remain in preserved registers, so ignored packets cannot overwrite
the values used by foreground Flash commands. A valid control-read OUT status
may confirm a final IN whose ACK was lost; it cannot replace a write's IN status.

USB status completion does not mean Flash has finished programming: SPM halts
this CPU. The host defaults to a configurable 7 ms quiet interval and reads back each
page. It repeats readback across the entire image after all writes to detect
later corruption of an earlier page before reporting success or sending RUN.
After an uncertain COMMIT it reads back before deciding what to do;
it must not blindly issue another COMMIT.

An invalid new SELECT, failed/short READ8, or RUN with either known or unknown
completion invalidates the local page plan. Subsequent WRITE2/COMMIT requires
a fresh validated selection. A successful READ8 preserves the staged words.
The 7 ms default is the established host policy, not v4.1 hardware timing proof.

Application images remain linked at zero. Only RESET is redirected, original
interrupt vectors remain intact, and the four-byte postscript carries the
original application entry. Foreign prepatched images need their original
layout metadata; the host must not guess an entry from arbitrary vector bytes.

EEPROM staging is an offline temporary-application plan. A reconnect is not an
independent success proof and must not automatically permit main-image restore.
All hardware programming remains outside software verification.

The user-approved receive CRC exception is explicit: incoming DATA CRC16 is
not validated, either before ACK or later. This includes SETUP's DATA packet.
Outgoing DATA CRC16 and incoming token CRC5 remain required. Full-image final
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
