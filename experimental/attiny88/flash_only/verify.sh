#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 -m tests35.test_avr_model
python3 -m tests35.test_avr_cycles
python3 tests34/test_opcode.py
python3 tests34/test_standard.py
python3 -m tests35.test_ep0_status
python3 -m tests35.test_setup_pending_marker
python3 -m tests35.test_ep0_zero_direction
python3 -m tests35.test_ep0_reply_fragments
python3 -m tests35.test_tx_crc_payloads
python3 -m tests35.test_ep0_read_completion
python3 -m tests35.test_out_completion_lifetime
python3 -m tests35.test_vendor_host_contract
python3 -m tests35.test_sequential_wire
python3 -m tests35.test_tx_eop_counter
python3 -m tests35.test_tx_digital
python3 -m tests35.test_ep0_reset
python3 -m tests35.test_ep0_shadow
python3 -m tests35.test_ep0_ack_timeout
python3 -m tests35.test_ep0_token_timeout
python3 -m tests35.test_ep0_polling
python3 -m tests35.test_ep0_failed_sync
python3 -m tests35.test_token_crc5
python3 -m tests35.test_token_framing_wire
python3 -m tests35.test_rx_context_restore
python3 -m tests35.test_usb_rx_waveforms
python3 -m tests35.test_ack_followup
python3 -m tests35.test_data_framing
python3 -m tests35.test_token_crossover_admission
python3 -m tests35.test_rx_jitter_spec
python3 -m tests35.test_rx_late_entry
python3 -m tests35.test_usb_crossover
python3 tests34/test_phy_timing.py
python3 tests34/test_host.py
python3 tests35/test_host_fail_closed.py
python3 tests35/test_final_readback.py
python3 eeprom_stage/test_stage.py
python3 tests35/test_eeprom_plan_gate.py
python3 -m tests35.test_nvm_state
python3 tests35/test_ack_regression.py
python3 make_release35.py
python3 verify_release35.py
python3 -m compileall -q source host tests tests34 tests35 eeprom_stage
