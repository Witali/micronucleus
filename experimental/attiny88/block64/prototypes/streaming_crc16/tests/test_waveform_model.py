"""Independent harness invariants needed before interpreting firmware traces."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verify_streaming import (TraceCPU,crc16,wire,response_pid,HostPins,TolerancePins,
                             JITTER_PROFILES,differential_edge_errors)


def test_data_space_register_aliases_used_for_handshake():
    cpu=TraceCPU.__new__(TraceCPU)
    cpu.r=list(range(32));cpu.m=bytearray([0xA5]*0x300);cpu.io={}
    for address in range(32):
        assert cpu.memread(address)==address
        cpu.memwrite(address,0xD2)
        assert cpu.r[address]==0xD2
        assert cpu.m[address]==0xA5
    assert cpu.memread(0x100)==0xA5
    cpu.memwrite(0x100,0x5A)
    assert cpu.m[0x100]==0x5A


def test_independent_handshake_decoder_checks_sync_and_pid():
    for pid in (0xD2,0x5A,0x1E,0):
        levels,_=wire(bytes([pid]))
        for origin in (0,1,17,1089):
            events=[];last=2
            for index,level in enumerate(levels):
                if level!=last:
                    events.append((origin+(index*32+2)//3,0x0B,level))
                last=level
            assert response_pid(events,origin)==pid


def test_reference_usb_crc_vectors_and_stuffing():
    assert crc16(b'')==b'\x00\x00'
    assert crc16(b'123456789')==b'\xc8\xb4'
    levels,metadata=wire(b'\x4b'+b'\xff'*8+crc16(b'\xff'*8))
    assert sum(source[0]=='stuff' for source in metadata)>=10
    assert levels[-3:]==[0,0,2]


def test_zero_tolerance_model_matches_original_rational_clock():
    class CPU:
        t=0
        input_pc=0
    cpu=CPU()
    levels,metadata=wire(b'\x4b\xff\x00\x00')
    for phase in range(-47,1):
        nominal=HostPins(cpu,levels,metadata,phase)
        tolerance=TolerancePins(cpu,levels,metadata,phase)
        for at in range(550):
            cpu.t=at
            assert nominal.get(0x09)==tolerance.get(0x09)
            if nominal.reads[-1][2]>=0 and nominal.reads[-1][2]<len(levels):
                assert nominal.reads[-1][2:]==tolerance.reads[-1][2:]
        assert nominal.eop_end_thirds==tolerance.eop_end_thirds


def test_jitter_patterns_obey_both_receiver_interval_constraints():
    for name in JITTER_PROFILES:
        errors=differential_edge_errors(name)
        assert errors['consecutive_ns']<=75
        assert errors['paired_ns']<=45
    assert differential_edge_errors('consecutive')['consecutive_ns']==75
    assert differential_edge_errors('paired')['paired_ns']==45
    assert differential_edge_errors('combined')=={'consecutive_ns':75,'paired_ns':45}
