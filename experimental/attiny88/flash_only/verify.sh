#!/bin/sh
set -eu
cd "$(dirname "$0")"

# Execute the corrected physical receiver once; forward source/placement options.
python3 verify_receiver.py --exhaustive "$@"

# Independent legacy opcode/reference checks retain their own valid geometry.
python3 -m tests35.test_execution_geometry
python3 tests34/test_opcode.py
python3 tests34/test_standard.py
python3 tests34/test_phy_timing.py
python3 tests35/test_ack_regression.py

# Host planning, failure handling and offline EEPROM are independent of PHY.
python3 tests34/test_host.py
python3 tests35/test_host_fail_closed.py
python3 tests35/test_final_readback.py
python3 eeprom_stage/test_stage.py
python3 tests35/test_eeprom_plan_gate.py
python3 -m tests35.test_nvm_state

# Package/read back the recognized strict-source fixture separately. The
# selected experimental receiver remains an unknown profile, not a release.
python3 make_release35.py
python3 verify_release35.py
python3 -m compileall -q source host tests tests34 tests35 eeprom_stage
