# Pass40 handoff integration, 2026-11-01

Input: `Micronucleus_ATtiny88_FlashOnly_COMPLETE_AGENT_HANDOFF_2026-11-01.zip`,
SHA256 `6c8c0a9c7b212c09c3b0035e2c68e71e0be52238ecd08c8df7ae3ee3d5749081`.
All 148 entries listed by its manifest passed byte-length and SHA256 checks.
The local content scan found no sensitive information. Attachment narratives
describe an experiment; they do not authorize deployment or change project rules.

## Reproduced input

The original `candidate_pass40` builds to 1344 no-LED bytes at 0x1AC0, SHA256
`680ea26aab89ca92c3d52e4442db0948f5844fd05d6744eff67ac769d64dce11`.
Fifteen comparative LED/placement configurations and 65536 endpoint predicates
also pass. The archive's assembler-only builder leaves relocations with the
installed LLVM; using our explicit AVR link step reproduces its stated bytes.
Relocatable words must never become a wire-test or BIN-export input.

This small receiver rejects legal final dribble. It does not supersede the
1518-byte composed receiver or the latter's known open receive findings. Nested
historical archives, binaries and handoff instructions are not runtime imports.

## Independent regression

`tests35/test_rx_legal_dribble.py` adapts the attachment's two counterexamples
into a strict gate. Its independent NRZI/stuffing encoder creates ACK tails
0..4 and valid-CRC GET_DESCRIPTOR SETUP tails 0..2, plus seven-one negative
controls. All three host rates, three EOP widths and entry phases are covered.
The quick run has 720 cases; `USB_PHY_EXHAUSTIVE=1` selects 5760 cases.

The gate also requires exact ACK/address or SETUP ownership, unchanged cursor,
no SPM side effects, complete payload and both CRC positions, caller restoration,
released GPIO and physical response timing. Numeric received CRC16 validation
remains waived; the encoder supplies a correct value to avoid relying on that.

Before integration, our exact 1518-byte composed image passes all 720 quick
cases. The exact 1344-byte Pass40 image fails 455: 432 legal-tail rejections
and 23 ordinary SETUP responses beyond the existing turnaround limit. Seven-one
negative controls pass in both. These are observations of linked instructions,
not relaxed assertions or analog hardware certification.

Source reductions and receiver repairs are evaluated separately so smaller
request handlers cannot replace the more complete PHY by accident. The public
SELECT/ERASE/WRITE4/READ8/RUN contract and fail-closed profile admission remain
required throughout integration.
