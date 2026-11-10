# Compact SYNC qualification, November 10

The complete no-LED Flash-only loader is **1960 bytes at 0x1800**, body SHA256
`e081fcf70a0b03419f26009055eebc59b43f8f4151feb0a4a151f51232ed8ac1`.
It adds 14 bytes to the [1946-byte token transfer](COMPACT_USB_TRANSFER_2026_11_10.md)
and remains **680 bytes above the 1280-byte target**. Identity 0xFFFF is still
unknown to the programming client. No release profile or hardware installation
is introduced; the EEPROM-capable compact v3.0 remains unchanged.

## Conditional SYNC-run qualification

An ordinary one-bit K cell can impersonate the final two-K SYNC run. Capture
the full port two clocks after the existing confirmation, retaining it in
R17. Check that evidence only when PIDbit0 selects the normal K/one path.
ACK ignores this capture: its legitimate PIDbit0 zero can already be near
the additional observation. A rejected normal candidate has not decoded a
bit; reuse its current full-K timestamp for the next confirmation.

R18's initial history and R21's fractional seed move into the existing
ten-clock acquisition interval. T clears in a retired seed slot. This funds
the extra capture without moving accepted PID or DATA observations and
removes the temporary polynomial-delay call. The shadow fixture's peak
stack use falls from six to four bytes; final stack/context checks still pass.

| Event | Before | Current |
| --- | ---: | ---: |
| Confirmation IN | C0 | C0 |
| Extra evidence IN | absent | C0+2 |
| Successful confirmation label | C0+5 | C0+6 |
| PIDbit0 IN | C0+12 | C0+12 |
| PIDbit1 IN, normal and ACK | PID0+10 | PID0+10 |
| Non-K retry | 8 clocks | 8 clocks |

Pristine emitted DATA and ACK traces have identical GPIO observations from
PID0 onward. The additional qualifier repairs 24 false K2/K4 locks. It does
not recover the earlier edge information lost by the remaining phase cases.

## Complete gate and exact comparison

The unchanged corrected-model 69-group exhaustive gate completed on the
linked body: **64 pass, five fail, strict exit 1**. All 156 source/artifact
pins remained unchanged. The [comparison record](compact_sync_pid0_2026_11_10.json)
checks 145 identical frozen reference files against the accepted 1946-byte
control: 24 repaired contexts, zero new failing contexts/groups, and zero
changes to shared failure observations. Its successful regression comparison
does not make the failing USB gate pass.

| Mandatory group | Control failures | Current failures |
| --- | ---: | ---: |
| Adjacent overlong-token excursions | 0/3456 | 0/3456 |
| Asymmetric DATA excursions | 120/2484 | 120/2484 |
| SE1 DATA excursions | 63/2486 | 63/2486 |
| Payload excursions | 69/981 | 69/981 |
| SE0 SYNC excursions | 59/1080 | 35/1080 |
| Short-status interior boundary | 12/108 | 12/108 |

Together with the earlier transfer, the original 1934-byte control's token
failures fall 720 to zero and its SE0 SYNC failures fall 144 to 35. These
are repaired test contexts, not counts of distinct implementation defects.
Full checks retain physical response deadlines, minimum-gap followups,
670 ns EOP, dribble/stuffing, token CRC5, exact payload/count, ACK ownership,
Flash guards and explicit AVR instruction timing. No oracle is weakened.

The independent set-wins PCIF-policy screen completes ten affected groups:
nine pass; only the same 35 SYNC cases fail. ACK crossover/prefix/recovery,
8064 late-entry cases, 6048 OUT responses and 648 deadline probes pass.
Both possible simultaneous set/clear policies remain test cases, rather
than an assumed undocumented silicon priority. The default gate preserves
188 exported files; the separate policy screen preserves 166, verified
against their transfer manifests.

## Additional SE1 coverage

The new mandatory `test_rx_sync_crossover_se1` registers a 70th verifier
group. Its separate exact-body run has 1080 injected cases and 54 pristine
controls. Both 1946- and 1960-byte bodies fail the same 90 injected cases;
all controls pass and every per-case error/response observation matches.
Endpoint and centered placements have independent monotonic-voltage
certificates. These additional inherited SYNC failures remain strict.

The completed 69-group run and the added SE1 run are separately pinned
stages. They cover the maintained 70-group inventory with six failing groups;
no single complete 70-group command is claimed. The default command now
includes the new group automatically:

```sh
python3 verify_receiver.py --source variants/ack_terminal --boot 0x1800 --exhaustive
```

## Maintained build identity

The [canonical rebuild record](compact_sync_pid0_image_2026_11_10.json)
verifies every loaded byte and every fixture/text symbol against the tested
image. Its .text is 8104 bytes at VMA zero: 6144 zero .org bytes followed by
the exact 1960-byte body. The zero prefix is not bootloader code size.
The canonical ELF's metadata differs from the private tested ELF; their
distinct hashes remain explicit. GNU AVR produces the same body too.
The non-ACK 1766-byte control at 0x1900 is byte-identical to its prior image.

Two small alternatives were rejected. Advancing raw-byte observations fixes
the old 12 status contexts but adds six different status failures and 138
pristine/corner STALL failures. Switching six early polls to D+ fixes the
old 35 SE0 contexts but adds 50 others; its SE1 corpus also gains 31 failures.
Neither aggregate counts nor a smaller source change justify those regressions.

The remaining DATA decision has opposite-required waveforms with identical
stored registers, flags, SRAM and PCIF. An uncaptured prior-odd+9 observation
distinguishes two witnesses, but that clock currently executes the loop branch.
Blind recovered-zero handling previously ACKed an EF-to-DB corrupted payload.
Further repair must fund new evidence and its continuation, preserving the
sampling and response budgets, before returning to pure size optimization.

Only incoming numeric DATA CRC16 validation/storage remains waived. This
checkpoint still has mandatory USB failures; digital tests do not establish
analog or board compliance. No image from this transfer has been flashed.
