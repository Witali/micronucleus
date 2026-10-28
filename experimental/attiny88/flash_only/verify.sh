#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 tests34/test_opcode.py
python3 tests34/test_standard.py
python3 tests34/test_phy_timing.py
python3 tests34/test_host.py
python3 tests35/test_host_fail_closed.py
python3 tests35/test_final_readback.py
python3 eeprom_stage/test_stage.py
python3 tests35/test_eeprom_plan_gate.py
python3 tests35/test_nvm_state.py
python3 tests35/test_ack_regression.py
python3 make_release35.py
python3 verify_release35.py
python3 -m compileall -q source host tests tests34 tests35 eeprom_stage
