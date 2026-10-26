"""Complete host waveforms against assembled streaming-CRC RX instructions."""
from pathlib import Path
import os
import random
import sys

import pytest

PROTOTYPE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROTOTYPE/'tools'))
from verify_streaming import (load_build,receive,require_data,crc16,token,wire,
                              run_suite,diagnose_dribble,HostPins)


@pytest.fixture(scope='module')
def build():
    return load_build(os.environ.get('STREAMING_CRC_MANIFEST',str(PROTOTYPE/'build/streaming-v2/manifest.json')))


def test_minimum_complete_receiver_smoke(build):
    result=run_suite(build,'smoke')
    assert result['valid_frames']>100


def test_minimum_corrupt_crc_gate(build):
    for length in (0,1,8):
        for pid in (0xc3,0x4b):
            payload=bytes(range(length))
            original=bytes([pid])+payload+crc16(payload)
            for byte in (len(original)-2,len(original)-1):
                packet=bytearray(original);packet[byte]^=1
                for phase in (-45,0):
                    obs,_,_=receive(build,bytes(packet),phase)
                    require_data(obs,bytes(packet),valid=False)


def test_all_normal_and_stuffed_arrival_phases(build):
    result=run_suite(build,'positive')
    assert result['valid_frames']==6528
    # run_suite strictly checks physical-bit identity, decoded data/CRC and
    # response deadline. A middle-half sample window is a useful reported
    # margin, not the literal USB 2.0 section 7.1.15.1 receiver requirement.


def test_every_payload_and_crc_bit_corruption_has_no_ack(build):
    # Each payload/trailer bit at all48one-third-cycle entry phases.
    # Stuffing is regenerated after corruption, so this tests DATA CRC rather
    # than relying on an unrelated stuffed-zero violation to hide a bad CRC.
    count=0
    for phase in range(-47,1):
        for length in range(9):
            for pid in (0xc3,0x4b):
                payload=bytes((index*37+0x55)&255 for index in range(length))
                original=bytes([pid])+payload+crc16(payload)
                for bit in range((length+2)*8):
                    packet=bytearray(original);packet[1+bit//8]^=1<<(bit%8)
                    obs,_,_=receive(build,bytes(packet),phase)
                    require_data(obs,bytes(packet),valid=False)
                    count+=1
    assert count==41472


def test_random_payloads_match_independent_crc(build):
    randomizer=random.Random(0x16c16)
    for _ in range(512):
        length=randomizer.randrange(9)
        pid=randomizer.choice((0xc3,0x4b)) if length else 0x4b
        payload=bytes(randomizer.randrange(256) for _ in range(length))
        packet=bytes([pid])+payload+crc16(payload)
        obs,_,_=receive(build,packet,randomizer.randrange(-47,1))
        require_data(obs,packet)


def all_stuff_position_payloads():
    # Repeated-byte patterns miss stuffing after bit0. Select packets by the
    # independent wire builder, then exercise every arrival phase and PID.
    randomizer=random.Random(0x16c001)
    payloads={}
    for _ in range(20000):
        payload=bytes(randomizer.randrange(256) for _ in range(8))
        packet=b'\x4b'+payload+crc16(payload)
        _,metadata=wire(packet)
        for kind,byte,bit in metadata:
            if kind=='stuff' and byte<=6:
                payloads.setdefault(bit,payload)
        if len(payloads)==8:break
    assert len(payloads)==8
    return payloads


def test_every_stuffed_position_and_cooldown_sample(build):
    payloads=all_stuff_position_payloads()
    seen=set()
    sample_names={address:name for name,address in build['symbols'].items()
                  if name.startswith('stream_cooldown_') and name[-1:].isdigit()
                  and '_eop' not in name}
    for payload in payloads.values():
        for pid in (0xc3,0x4b):
            packet=bytes([pid])+payload+crc16(payload)
            for phase in range(-47,1):
                obs,_,pins=receive(build,packet,phase)
                require_data(obs,packet)
                seen.update(sample_names[pc] for _,pc,*_ in pins.reads if pc in sample_names)
    assert seen==set(sample_names.values()),set(sample_names.values())-seen


def test_varying_non_usb_port_bits_do_not_change_receiver(build,monkeypatch):
    original=HostPins.get
    count=0
    seen=set()
    def get_with_other_port_bits(pins,address,default=0):
        nonlocal count
        value=original(pins,address,default)
        if address==0x09:
            selection=(count*37+17)&63
            count+=1;seen.add(selection)
            other_bits=sum(((selection>>index)&1)<<bit
                           for index,bit in enumerate((0,3,4,5,6,7)))
            return value|other_bits
        return value
    monkeypatch.setattr(HostPins,'get',get_with_other_port_bits)
    for payload in all_stuff_position_payloads().values():
        for pid in (0xc3,0x4b):
            packet=bytes([pid])+payload+crc16(payload)
            for phase in (-45,-24,-9,0):
                obs,_,_=receive(build,packet,phase)
                require_data(obs,packet)
    assert seen==set(range(64))


def test_nondata_packets_do_not_use_data_crc_gate(build):
    for phase in range(-47,1):
        obs,_,_=receive(build,b'\xd2',phase,prior_token=0)
        assert obs.response_pid is None and obs.published_length==0
        for address in (0,17,127):
            for length in (0x5a,4,12):
                obs,_,_=receive(build,token(0x69,address),phase,prior_token=0,
                                address=address,tx_length=length)
                assert obs.response_pid==(0x5a if length==0x5a else 0x4b),obs
                assert obs.turnaround_thirds is not None and 64<=obs.turnaround_thirds<=208
            for pid in (0xe1,0x2d):
                obs,_,_=receive(build,token(pid,address),phase,prior_token=0,address=address)
                assert obs.response_pid is None and obs.published_length==0
                assert obs.token==0 # Application RX-token remains unpublished until DATA.


def test_corrupt_token_crc5_has_no_response_or_state_publication(build):
    for phase in range(-47,1):
        for address in (0,17,127):
            for pid in (0x69,0xe1,0x2d):
                for bit in range(3,8):
                    packet=bytearray(token(pid,address));packet[2]^=1<<bit
                    obs,cpu,_=receive(build,bytes(packet),phase,prior_token=0,
                                      tx_length=4,address=address)
                    assert obs.response_pid is None and obs.published_length==0,obs
                    assert cpu.m[0x114]==0 and cpu.m[0x10f]==4,obs


def test_foreign_address_and_endpoint_tokens_are_ignored(build):
    for phase in (-45,-24,-9,0):
        for address in (0,17,127):
            for pid in (0x69,0xe1,0x2d):
                for packet in (token(pid,(address+1)%128),token(pid,address,1),
                               token(pid,address,15)):
                    obs,cpu,_=receive(build,packet,phase,prior_token=0,tx_length=4,address=address)
                    assert obs.response_pid is None and obs.published_length==0,obs
                    assert cpu.m[0x114]==0 and cpu.m[0x10f]==4,obs


def test_bad_stuffed_bits_are_not_acknowledged(build):
    count=0
    for length in range(1,9):
        packet=b'\x4b'+b'\xff'*length+crc16(b'\xff'*length)
        levels,metadata=wire(packet)
        for index,source in enumerate(metadata):
            if source[0]!='stuff':continue
            damaged=list(levels);damaged[index]=damaged[index-1]
            for phase in (-45,-24,-9,0):
                obs,_,_=receive(build,packet,phase,levels=damaged,metadata=metadata)
                assert obs.response_pid is None and obs.published_length==0,obs
                count+=1
    assert count>100


def test_oversize_packet_does_not_publish_or_ack(build):
    for length in (9,10,16,64):
        payload=bytes(range(length));packet=b'\x4b'+payload+crc16(payload)
        for phase in (-45,-24,-9,0):
            obs,_,_=receive(build,packet,phase)
            assert obs.response_pid is None and obs.published_length==0,obs


def test_single_dribble_bit_preserves_crc_and_packet(build):
    # Whole-bit dribble is a stress probe; acceptance here does not establish
    # electrical EOP jitter/dribble conformance by itself.
    for length in range(9):
        payload=bytes([0x7e])*length;packet=b'\x4b'+payload+crc16(payload)
        for bit in (0,1):
            levels,metadata=wire(packet,dribble=(bit,))
            for phase in (-45,-24,-9,0):
                obs,_,_=receive(build,packet,phase,levels=levels,metadata=metadata)
                require_data(obs,packet)


def test_empty_data1_legal_dribble_deadline_at_every_phase(build):
    packet=b'\x4b\x00\x00'
    for extra in (1,3,5):
        levels,metadata=wire(packet,dribble=(1,)*extra)
        for phase in range(-47,1):
            obs,_,_=receive(build,packet,phase,levels=levels,metadata=metadata)
            require_data(obs,packet)


def test_legal_transition_free_dribble_tails(build):
    # USB2.0 section7.1.9.1 limits the TOTAL transition-free final interval,
    # including the original CRC/stuffed-bit tail, to six full bit times.
    report=diagnose_dribble(build,full=False)
    fields=('decoded_failures','crc_gate_failures','ack_failures',
            'publication_failures','sample_bit_failures','turnaround_failures')
    legal=[row for row in report['rows'] if row['within_six_intervals']]
    assert sum(row['cases'] for row in legal)>300
    failed=[row for row in legal if any(row[field] for field in fields)]
    assert not failed,failed
