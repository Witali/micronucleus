# Flash-only vendor protocol v4.1

This target is separate from the EEPROM-capable v3.0 loader. The host selects
geometry from an exact recognized bcdDevice before sending vendor commands.
Unknown identities fail closed; neither a guessed RESET nor a command probe
identifies a device layout.

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
The host validates page/word bounds and the MCU retains the final SPM guard
against erasing or writing its own bootloader pages.

IN DATA/PID stays cached until an eligible, correctly framed ACK. Repeated IN
before ACK must return the same bytes and PID. ACK eligibility is short-lived;
the durable pending-DATA flag is separate and must block SPM/application exit.
A replacement SETUP or bus reset cancels the obsolete transfer and deferred
work. SET_ADDRESS takes effect only after its status ACK.

USB status completion does not mean Flash has finished programming: SPM halts
this CPU. The host defaults to a configurable 7 ms quiet interval and reads back each
page. After an uncertain COMMIT it reads back before deciding what to do;
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
