"""Actual post-TX/foreground tests for opt-in ACK publication experiments.

Three strict tracked contracts reproduce baseline defects before raising a
dedicated inherited-violation exception, never a generic setup/assertion error:
  test_strict_minimum_gap_next_out_is_received_with_its_valid_token:
    phase0/gap64, DATA0/8 then OUT + DATA1/8: next token/data are missed.
  test_strict_minimum_gap_next_in_is_received_after_data_ack:
    phase0/gap64, DATA0/8 then IN: the IN token/NAK are missed.
  test_strict_busy_rx_preserves_the_previously_owned_payload:
    phase0/gap2048, an 11-byte RX packet already owned, then DATA0/8:
    the old metadata is retained but its payload is overwritten before NAK.
Strict XPASS requires removing the tracker when a future build fixes a case.
Build the opt-in EOP experiment, or set ACK_PIPELINE_MANIFEST to another mode.
"""
from pathlib import Path
import os
import sys
import pytest

PROTOTYPE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROTOTYPE/'tools'))
from verify_ack_pipeline import (PacketPins,load_build,run_sequence,assess,compare_waveforms,
                                tx_waveform)


class InheritedPipelineViolation(RuntimeError):
    """Raised only after reproducing the exact same named baseline contract."""


@pytest.fixture(scope='module')
def baseline():
    path=PROTOTYPE/'build/streaming-v2/manifest.json'
    if not path.exists():pytest.skip('Build the frozen baseline first')
    return load_build(path)


@pytest.fixture(scope='module')
def candidate():
    path=Path(os.environ.get('ACK_PIPELINE_MANIFEST',str(PROTOTYPE/'build/streaming-v2-eop/manifest.json')))
    if not path.exists():pytest.skip('Build the optional ACK-mode experiment first')
    return load_build(path)


def test_pcif_latches_edges_without_polling_pind():
    class CPU:
        t=0
        input_pc=0
    cpu=CPU();pins=PacketPins(cpu)
    packet=pins.add('packet',b'\xd2',3)
    assert pins.get(0x1b)==0
    cpu.t=2 # SOP at one cycle, no PIND read occurred.
    assert pins.get(0x1b)==4
    pins.flag=0 # The CPU's actual W1C instruction calls this after completion.
    cpu.t=13
    assert pins.get(0x1b)==4
    with pytest.raises(AssertionError):pins.add('too-early',b'\xd2',packet.eop_end+63)


def test_publication_survives_actual_ret_and_foreground(candidate):
    for phase in (-45,-24,-9,0):
        for length in range(9):
            for pid in (0xc3,0x4b):
                if not length and pid==0xc3:continue
                report,_=run_sequence(candidate,'single',phase,length=length,first_pid=pid)
                checks=assess(report)
                assert all(checks.values()),(checks,report)
                assert report['copy_count']==length
                assert report['copied_payload']==bytes(range(length)).hex()


def test_setup_token_count_is_committed_before_command_consumer(candidate):
    for phase in range(-47,1):
        report,_=run_sequence(candidate,'setup-single',phase)
        checks=assess(report)
        assert all(checks.values()),(checks,report)
        assert report['consumers'][0]['token']==0x2d


def test_corrupt_data_never_publishes_later_in_the_tail(candidate):
    for phase in (-45,-24,-9,0):
        for length in (0,1,8):
            report,_=run_sequence(candidate,'corrupt-only',phase,length=length)
            assert report['tx']==[] and report['publications']==[]
            assert report['publication_token_stores']==[]
            assert report['consumers']==[] and report['copy_count']==0
            assert all(assess(report).values()),report


def test_corrupt_packet_after_valid_ack_does_not_republish_stale_registers(candidate):
    for phase in range(-47,1):
        # Isolate stale publication state after foreground consumption; the
        # separate strict minimum-gap contracts retain their baseline faults.
        report,_=run_sequence(candidate,'out-corrupt',phase,4096)
        assert all(assess(report).values()),report
        assert len(report['publications'])==1 and report['publications'][0]['packet']=='first'
        assert not any(item['packet']=='next-data' for item in report['publication_token_stores'])


def test_busy_rx_selects_nak_without_republishing_metadata(candidate):
    for phase in (-45,-24,-9,0):
        report,_=run_sequence(candidate,'busy-rx',phase)
        assert report['tx'][0]['pid']==0x5a
        assert report['publications']==[] and report['publication_token_stores']==[]
        assert not any(event['label'].endswith('_commit') for event in report['publication_labels'])


def test_immediate_host_ack_releases_tx_owner(candidate):
    for phase in range(-47,1):
        report,_=run_sequence(candidate,'in-ack',phase)
        assert all(assess(report).values()),report
        assert report['tx_length']==0x5a and report['ack_window']==0


def test_lost_host_ack_repeats_identical_data_until_ack(candidate):
    for phase in (-45,-24,-9,0):
        report,cpu=run_sequence(candidate,'in-retry',phase,2048)
        assert all(assess(report).values()),report
        assert tx_waveform(cpu,report['tx'][0])==tx_waveform(cpu,report['tx'][1])
        assert report['tx_length']==0x5a and report['ack_window']==0


def test_pairwise_tx_waveforms_flags_and_bounded_pipeline_regressions(candidate,baseline):
    for scenario in ('single','setup-single','out-next','out-retry','out-in','in-ack','in-retry','busy-rx','corrupt-retry'):
        for phase in (-45,-24,-9,0):
            for gap in (64,512,2048):
                new,new_cpu=run_sequence(candidate,scenario,phase,gap)
                old,old_cpu=run_sequence(baseline,scenario,phase,gap)
                for match in compare_waveforms(new,new_cpu,old,old_cpu):
                    assert match['same_port_ddr_waveform'] and match['same_final_flags'] and match['same_wait_counter'],match
                new_checks,old_checks=assess(new),assess(old)
                candidate_only={key:value for key,value in new_checks.items() if key not in old_checks}
                assert all(candidate_only.values()),(candidate_only,new)
                regressions=[key for key,value in new_checks.items() if not value and old_checks.get(key,False)]
                assert not regressions,(regressions,new,old)


@pytest.mark.xfail(strict=True,raises=InheritedPipelineViolation,reason='Tracked baseline foreground CRC loses minimum-gap next OUT token/data')
def test_strict_minimum_gap_next_out_is_received_with_its_valid_token(candidate,baseline):
    old,_=run_sequence(baseline,'out-next',0,64)
    old_checks=assess(old)
    assert not old_checks['following_tokens_validated'] and not old_checks['response_sequence']
    assert old['copy_count']==8
    report,_=run_sequence(candidate,'out-next',0,64)
    checks=assess(report)
    if checks['following_tokens_validated'] and checks['response_sequence'] and report['copy_count']==16:return
    assert not checks['following_tokens_validated'] and not checks['response_sequence'],(checks,report)
    assert report['copy_count']==old['copy_count'] and report['copied_payload']==old['copied_payload'],report
    raise InheritedPipelineViolation('Minimum-gap OUT token/data are missed while foreground validates the previous packet')


@pytest.mark.xfail(strict=True,raises=InheritedPipelineViolation,reason='Tracked baseline foreground CRC loses minimum-gap next IN token')
def test_strict_minimum_gap_next_in_is_received_after_data_ack(candidate,baseline):
    old,_=run_sequence(baseline,'out-in',0,64)
    old_checks=assess(old)
    assert not old_checks['following_tokens_validated'] and not old_checks['response_sequence']
    assert [item['pid'] for item in old['tx']]==[0xd2]
    report,_=run_sequence(candidate,'out-in',0,64)
    checks=assess(report)
    if checks['following_tokens_validated'] and checks['response_sequence']:return
    assert not checks['following_tokens_validated'] and not checks['response_sequence'],(checks,report)
    assert [item['pid'] for item in report['tx']]==[0xd2],report
    raise InheritedPipelineViolation('Minimum-gap IN token is missed while foreground validates the previous packet')


@pytest.mark.xfail(strict=True,raises=InheritedPipelineViolation,reason='Tracked baseline PHY overwrites busy RX scratch before selecting NAK')
def test_strict_busy_rx_preserves_the_previously_owned_payload(candidate,baseline):
    old,_=run_sequence(baseline,'busy-rx',0,2048)
    assert not assess(old)['consumer_has_complete_owned_packet']
    assert old['copy_count']==8 and old['copied_payload']==bytes(range(8)).hex()
    report,_=run_sequence(candidate,'busy-rx',0,2048)
    if assess(report)['consumer_has_complete_owned_packet']:return
    assert report['copy_count']==old['copy_count'] and report['copied_payload']==old['copied_payload'],report
    raise InheritedPipelineViolation('Busy RX metadata still owns the previous packet while its scratch payload was overwritten')
