# Physical comparison: legacy 2.8 and guarded streaming V2

Measured on 2026-10-26 on the same ATtiny88 board, configured for an external
16 MHz clock, Windows libusb0, and the same USB connection. Old code was the
installed 1274-byte loader; new code ran as a protected application. The
installed loader was preserved throughout. Detailed non-sensitive statistics
are in [the result JSON](results/2026-10-26.json).

## Measured wall time

Values below are medians. Write/erase readback verification is outside its
timer. USB calls include host scheduling, firmware work and retries; Flash
write times include the configured host pause.

| Operation | Bytes | Legacy 2.8 | New V2 | Median speedup |
| --- | ---: | ---: | ---: | ---: |
| Flash read, common range | 6908 | 2591.813 ms | 1079.871 ms | 2.40x |
| Flash read, identical controlled payload | 512 | 190.698 ms | 79.965 ms | 2.38x |
| Flash write, eight already erased pages | 512 | 321.229 ms | 239.982 ms | 1.34x |
| Flash write, one page | 64 | 40.008 ms | 29.976 ms | 1.33x |
| EEPROM read | 64 | 191.882 ms | 9.928 ms | 19.33x |
| EEPROM write | 64 | 642.906 ms | 269.898 ms | 2.38x |
| EEPROM write FF | 64 | 643.951 ms | 269.977 ms | 2.39x |

Reads and EEPROM operations have three samples per configuration. Legacy
Flash uses one 512-byte round with eight per-page samples; new Flash uses
three erased-page rounds, giving 24 per-page samples. No un-erased Flash
page was programmed repeatedly. The controlled 512-byte payload is identical
between configurations; full common reads contain different applications.
The JSON speedup field uses means, while this table uses medians.

## What produces the gain

Legacy reads use eight-byte Flash requests and one-byte EEPROM requests.
New native requests carry up to 64 bytes. At the same eight-byte Flash
request size, new reading takes 2591.887 ms for 6908 bytes, effectively the
same as legacy. At one byte per EEPROM request it takes 191.902 ms, also
effectively identical. Packet grouping accounts for the measured read gain.

Legacy Flash pages use 17 control requests and a nominal 7 ms host wait.
New Flash WRITE uses one 64-byte control transfer, a nominal 18 ms wait,
and completion polling. The longer new wait limits the write speed gain;
these timings are not intrinsic Flash programming times. Legacy's one-time
buffer-cursor preparation took 8.887 ms and is reported separately.

The new code erased eight scratch pages (512 bytes) in a median 175.932 ms.
The necessary stock-CLI transition's whole-application erase phase took
2520.897 ms for 108 pages/6912 bytes. That interval was measured between
flushed erase-progress events and includes CLI pacing, whose advertised
wait was 756 ms. Different scopes prevent a direct erase-speed ratio.
EEPROM FF measurements use normal atomic erase/write, not EEPM erase-only.

## Preservation and checks

The guarded image was read back byte for byte before mutation. The same
checks after the new benchmark verified unchanged executable bytes,
unchanged installed-loader SHA, erased scratch pages and original EEPROM.
The original Lumiere Stereo was then restored through the old loader.
Two complete reads of 6908 application bytes and two reads of all 64
EEPROM bytes matched the private baseline exactly; the application-start
request succeeded. Audio output was not evaluated.

The host and firmware tests total 48 passes. The legacy cursor proof rebuilds
the exact installed image and distinguishes temporary page-buffer loading
from actual Flash programming. Hardware logs, restore images and raw dumps
remain private; only code and measurement statistics are committed.

## Remaining optimization candidates

The frozen receiver's worst bounded digital ACK time is 68 2/3 CPU clocks
(4.292 microseconds), within the 69 1/3-clock limit. Restoring a normalized
context pointer with MOVW may save one clock; deferred RX publication may
save about two before ACK, at a cost in post-response state and service
latency. These changes have not been implemented or physically measured.

The current Flash host pause is deliberately 18 ms. A smaller pause must
cover approximately 5 ms of firmware quiet polling plus the documented
Flash busy interval and setup. A separate 12 ms profile is a future
experiment, not part of these measured results. Minimum EOP width/skew,
analog timing and worst-case continuous foreground service remain separate
verification work; this benchmark is not USB electrical certification.
