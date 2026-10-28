# Flash-only v4.2 host contract

The `0x0470` device profile identifies the cursor READ8/WRITE4 protocol. The
client rejects all other profile identities before sending vendor commands.
The descriptor profile determines the boot boundary and RESET/postscript
packing; application binaries remain independent of a bootloader layout.

All requests use endpoint zero. Host-to-device commands use `bmRequestType`
`0x40` with no data stage. READ8 uses `0xC0` and an IN data stage. The client
supplies the documented opcode, direction, recipient and parameter fields;
the device's minimal vendor decoder relies on this client contract.

| Opcode | Request | Fields and cursor effect |
| --- | --- | --- |
| 1 | SELECT | `wValue=0`, `wIndex=word-aligned Flash byte address`; clear the staging buffer and select the common cursor. |
| 2 | SELECT_ERASE | Same fields, with an application page-aligned address; additionally erase that 64-byte page. |
| 3 | WRITE4 | The little-endian bytes of `wValue` followed by `wIndex` are four payload bytes. Advance four bytes after the accepted IN status ACK. Completing 64 bytes automatically programs the page. |
| 4 | RUN | `wValue=wIndex=0`; run the application after accepted status. |
| `0xB0` | READ8 | `wValue=wIndex=0`, `wLength=1..8`; read at the common cursor and advance by the actual returned count only after accepted OUT status. |

Opcode 5 has no operation in this protocol. There is no explicit page commit.
The USB packet retry machinery may retransmit a packet; the host must never
reissue a WRITE4 control transfer as an application-level recovery attempt.

The programmer stages complete 64-byte pages. It pads unused image bytes with
`0xFF`, preserves the RESET/postscript image contract and checks all writes
against the descriptor-derived boot boundary. Reads may inspect raw Flash for
verification, but writes and erases must stay below the bootloader.

For each page the client performs:

1. SELECT_ERASE, wait for the configured Flash interval, then verify all 64
   bytes are `0xFF` using sequential READ8 requests.
2. SELECT the page again: verification advanced the common cursor.
3. Issue exactly 16 sequential WRITE4 requests. Do not interleave a read,
   another SELECT or RUN into this partially staged page.
4. Wait after the last WRITE4, then read back the complete page.

The postscript page is erased first and written last. After all immediate page
readbacks succeed, a separate whole-image pass verifies that later page writes
did not damage an earlier page. Only then may the caller request RUN.

The delay defaults to 7 ms and is configurable with `--flash-delay-ms`; it
applies after erase and after automatic programming. The selected firmware
uses separate erase/program operations. A combined erase-and-write sequence
would require a delay covering both operations, not this 7 ms default.

Any USB error, short READ8 or unexpected command completion invalidates the
local cursor, buffer and erase-verification plan. The same transport then
rejects further operations without traffic. Reconnect and begin a new complete
erase/verify/program plan. In particular, a lost final WRITE4 completion can
mean that Flash was already programmed: the client does not blindly retry it.

The hardware temporary-buffer model forbids loading one word twice before
programming (ATtiny88 datasheet, section 19.0.2). The mock records each word
load and rejects duplicates, including identical data. It does not assume
that a repeated WRITE4 is idempotent. SRAM accumulation followed by a single
local temporary-buffer fill has the same host contract.

These tests model host behavior and injected ambiguous completions. They do
not establish USB waveform timing or physical board admission, which require
the separate firmware/wire and hardware checks.
