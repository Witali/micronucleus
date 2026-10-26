# Preserved 512-byte streaming CRC variant

This folder freezes the working CRC-table/sampler combination used by the
default streaming-V2 diagnostic application. It is the known timing
reference while smaller-table experiments continue.

| Quantity | Preserved value |
| --- | ---: |
| CRC table data | 512 Flash bytes: 256 low + 256 high |
| CRC work during normal byte reception | 11 CPU clocks = 0.6875 microseconds at 16 MHz |
| Complete unstuffed receive byte | 85/86 CPU clocks |
| Diagnostic executable/static data before tables | 3262 bytes |
| Diagnostic alignment padding | 322 bytes |
| Complete diagnostic body at 0x0800 | 4096 bytes |

The 4096-byte body includes the diagnostic protocol and padding; it is not
the size of a production bootloader. The CRC update is distributed between
USB bit samples rather than called as a standalone function. Final EOP
pipeline cleanup, residual checking and ACK dispatch are additional work.

## Frozen contents and placement

- `streaming_rx_v2.inc`: exact sampler snapshot, including stuffing,
  cooldown and EOP completion paths.
- `crc_tables.inc`: generated assembler data; 512 bytes once assembled.
- `manifest.json`: source/table/body hashes, source Git checkpoint and
  measured size/timing scope. Text hashes normalize line endings to LF.

The diagnostic build places the low table at 0x1600 and the high table at
0x1700. Both halves start at 256-byte boundaries. The CRC uses reflected
polynomial A001, initialization FFFF and successful raw wire residual B001;
PID is excluded. These definitions follow
[USB 2.0 section 8.3.5.2](https://www.usb.org/document-library/usb-20-specification).

The parent builder's default remains `streaming-v2` with ACK mode
`immediate`. The sampler in this folder is an archival copy; it is not
automatically substituted into later builds. Git checkpoint `1affaac`
preserves the corresponding complete source tree and builder. From that
revision, run the following in `experimental/attiny88/block64`:

```sh
python3 prototypes/streaming_crc16/tools/build.py
python3 prototypes/streaming_crc16/tools/verify_streaming.py --suite smoke
```

The expected diagnostic body SHA256 is
`e5b06459481658af1f0b4296000a97dbd7f0226502caf5dd86c234a4407aba82`.
The default build in the current branch produces the same body.

## What has been verified

The table arithmetic matches the independent serial CRC for all
16,777,216 state/byte pairs. The complete baseline passes 6528 positive
DATA frames, 15648 legal-tail cases and 11664 bounded source-rate/jitter
cases. Nominal legal-tail ACK turnaround is 50 2/3..68 clocks; the bounded
rate/jitter maximum is 68 2/3 clocks against a 69 1/3-clock limit. Thus CRC
fits the tested bit-sampling and ACK schedule. The later optional EOP ACK
experiment retains these tables and increases the response margin;
see [its separate report](../../ACK_EXPERIMENTS.md).

This default image also enumerated and passed an application-only physical
USB read trial on the 16 MHz ATtiny88. The original application and EEPROM
were restored and read back exactly. That trial preserved the installed
1274-byte bootloader. This checkpoint operation did not program hardware.

The scope is CRC and the tested digital timing paths. Minimum-gap token
loss during foreground CRC/copy and busy-RX payload ownership defects remain
open in the surrounding prototype. Analog signal quality, minimum-width
EOP and full continuous USB correctness are not certified by this snapshot.
See the [parent evidence](../../README.md) and
[smaller-table comparison](../../CRC_TABLE_TRADEOFFS.md).
