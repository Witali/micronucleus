#!/usr/bin/env python3
"""Independent actual-opcode USB waveform checks for the isolated RX prototype.

The transmitter clock is a rational32/3 AVR cycles per low-speed bit. These
are nominal digital traces, not electrical compliance or a measured clock.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from bisect import bisect_right
from fractions import Fraction
from pathlib import Path
import argparse
import hashlib
import importlib
import json
import random
import re
import sys

PROTOTYPE = Path(__file__).resolve().parents[1]
PROJECT = PROTOTYPE.parents[1]
_saved_path, _saved_argv = sys.path[:], sys.argv[:]
try:
    sys.path.insert(0, str(PROJECT.parent/'tests'))
    Timed = importlib.import_module('test_vusb_timing').Timed
finally:
    sys.path[:], sys.argv[:] = _saved_path, _saved_argv


def number(value):
    return int(value, 0) if isinstance(value, str) else value


@dataclass(frozen=True)
class FrozenImage:
    data: bytes

    def read_bytes(self):
        return self.data


def crc16(payload):
    value = 0xffff
    for byte in payload:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xa001 if value & 1 else 0)
    return ((~value) & 0xffff).to_bytes(2, 'little')


def token(pid, address=0, endpoint=0):
    field, value = address | endpoint << 7, 0x1f
    for bit in range(11):
        feedback = (value ^ (field >> bit)) & 1
        value = (value >> 1) ^ (0x14 if feedback else 0)
    field |= ((~value) & 0x1f) << 11
    return bytes([pid, field & 255, field >> 8])


def wire(packet, *, dribble=(), early_eop=None):
    """Build independent stuffed NRZI symbols and map each to its source bit."""
    bits = [(0x80 >> bit) & 1 for bit in range(8)]
    metadata = [('sync', -1, bit) for bit in range(8)]
    ones = 0
    for byte_index, byte in enumerate(packet):
        for bit in range(8):
            value = (byte >> bit) & 1
            bits.append(value)
            metadata.append(('data', byte_index, bit))
            ones = ones + 1 if value else 0
            if ones == 6:
                bits.append(0)
                metadata.append(('stuff', byte_index, bit))
                ones = 0
    if early_eop is not None:
        bits, metadata = bits[:early_eop], metadata[:early_eop]
    for value in dribble:
        bits.append(value)
        metadata.append(('dribble', len(packet), 0))
    state, levels = 2, []
    for value in bits:
        if not value:
            state ^= 6
        levels.append(state)
    return levels+[0, 0, 2], metadata+[('eop', -1, index) for index in range(3)]


class TraceCPU(Timed):
    def memread(self, address):
        # AVR data addresses0..31 are the register file. The inherited TX
        # engine deliberately uses Y=0x0014 to read handshake byte R20.
        if 0 <= address < 32:
            return self.r[address]
        return super().memread(address)

    def memwrite(self, address, value):
        if 0 <= address < 32:
            self.r[address] = value & 255
            return
        return super().memwrite(address, value)

    def step(self):
        self.input_pc = self.pc
        return super().step()


class HostPins(dict):
    def __init__(self, cpu, levels, metadata, phase_thirds):
        super().__init__({0x09:2,0x0a:0,0x0b:2,0x1b:0})
        self.cpu, self.levels, self.metadata = cpu, levels, metadata
        self.phase_thirds = phase_thirds
        self.eop_end_thirds = phase_thirds+(len(levels)-1)*32
        self.reads = []

    def get(self, address, default=0):
        if address == 0x09:
            at = self.cpu.t*3-self.phase_thirds
            index, within = divmod(at, 32)
            level = self.levels[index] if 0 <= index < len(self.levels) else 2
            source = self.metadata[index] if 0 <= index < len(self.metadata) else ('idle',-1,-1)
            self.reads.append((self.cpu.t,self.cpu.input_pc,index,within,source,level))
            return level
        return super().get(address,default)


JITTER_PROFILES = {
    # Edge displacement patterns in nanoseconds. Transition polarity alternates,
    # so adjacent entries are consecutive and entries two apart are paired.
    'consecutive': (Fraction(-75, 2), Fraction(75, 2)),
    'paired': (Fraction(-45, 2), Fraction(-45, 2), Fraction(45, 2), Fraction(45, 2)),
    'combined': (Fraction(-75, 2), Fraction(75, 2), Fraction(15, 2), Fraction(-15, 2)),
}


def differential_edge_errors(profile):
    """Interval errors, rather than independent per-edge +/-75 ns noise."""
    values = JITTER_PROFILES[profile]
    return {
        'consecutive_ns': max(abs(values[i]-values[(i-1)%len(values)]) for i in range(len(values))),
        'paired_ns': max(abs(values[i]-values[(i-2)%len(values)]) for i in range(len(values))),
    }


class TolerancePins(HostPins):
    """Optional exact rational clock/edge model; EOP width remains nominal.

    Clock drift and receiver interval-jitter bounds are exercised separately:
    USB 2.0 section 7.1.15.1 allocates frequency tolerance within jitter budgets.
    This model has ideal differential edges, no analog transition/SE0 glitches.
    """
    def __init__(self, cpu, levels, metadata, phase_thirds, *, source_ppm=0,
                 jitter_profile=None, jitter_sign=1):
        super().__init__(cpu, levels, metadata, phase_thirds)
        period = Fraction(32*1_000_000, 1_000_000+source_ppm)
        self.boundaries = [Fraction(phase_thirds)+index*period for index in range(len(levels)+1)]
        previous, transition = 2, 0
        for index, level in enumerate(levels):
            if level in (2, 4) and previous in (2, 4) and level != previous:
                if jitter_profile:
                    displacement = JITTER_PROFILES[jitter_profile][transition%len(JITTER_PROFILES[jitter_profile])]
                    self.boundaries[index] += jitter_sign*displacement*Fraction(6, 125)
                transition += 1
            previous = level
        assert all(a < b for a, b in zip(self.boundaries, self.boundaries[1:]))
        self.eop_end_thirds = self.boundaries[len(levels)-1]

    def get(self, address, default=0):
        if address == 0x09:
            at = self.cpu.t*3
            index = bisect_right(self.boundaries, at)-1
            if 0 <= index < len(self.levels):
                start, end = self.boundaries[index:index+2]
                within = float((at-start)*32/(end-start))
                level, source = self.levels[index], self.metadata[index]
            else:
                within, level, source = 0, 2, ('idle', -1, -1)
            self.reads.append((self.cpu.t,self.cpu.input_pc,index,within,source,level))
            return level
        return dict.get(self,address,default)


def load_build(manifest):
    path = Path(manifest).resolve()
    meta = json.loads(path.read_text())
    start = number(meta.get('image_address',meta.get('bootloader_start',meta.get('start',0))))
    filename = meta.get('body_file',meta.get('binary_file','prototype.bin'))
    binary = Path(filename)
    if not binary.is_absolute():
        binary = path.parent/binary
    labels = meta.get('symbols')
    if labels is None:
        text = (path.parent/meta.get('symbols_file','symbols.txt')).read_text()
        labels = {name:int(address,16) for name,address in
                  re.findall(r'^(\S+)\s+0x([0-9a-fA-F]+)$',text,re.M)}
    labels = {name:number(value) for name,value in labels.items()}
    for alias, alternatives in {
        'usb_control_process_received_packet':['L1d9c','USB_handler'],
        'bootloader_poll_begin':['L1d3a','USB_handler'],
        'bootloader_start_application':['L1eac','USB_handler'],
    }.items():
        if alias not in labels:
            labels[alias] = next(labels[name] for name in alternatives if name in labels)
    image = binary.read_bytes()
    assert start >= 0 and start+len(image) <= 8192
    digest = hashlib.sha256(image).hexdigest()
    expected = meta.get('body_sha256', meta.get('sha256_body'))
    if expected:
        assert digest == expected, 'Manifest/image changed during test setup'
    return {'name':'streaming-prototype','start':start,'bin':FrozenImage(image),'o':None,
            'sha256':digest,
            'symbols':labels,'step_limit':30000,'manifest':meta}


@dataclass
class Observation:
    packet_hex:str
    phase_thirds:int
    selected:str|None
    decoded_hex:str
    published_length:int
    token:int
    stop:str
    cycles:int
    response_pid:int|None
    turnaround_thirds:int|None
    crc_snapshots:list
    sample_phases:list
    sample_mismatches:list
    lpm_reads:int


def response_pid(events,sop):
    state, previous, bits = 2, 2, []
    outputs=[(time,value&6) for time,port,value in events if port==0x0b]
    for bit in range(16):
        sample_thirds=sop*3+bit*32+16
        for time,value in outputs:
            if time*3<=sample_thirds:
                state=value
        if state not in (2,4):
            return None
        bits.append(int(state==previous));previous=state
    if sum(value<<bit for bit,value in enumerate(bits[:8]))!=0x80:
        return None
    return sum(value<<bit for bit,value in enumerate(bits[8:16]))


def receive(build,packet,phase_thirds=0,*,prior_token=0xe1,tx_length=0x5a,
            address=0,levels=None,metadata=None,source_ppm=0,
            jitter_profile=None,jitter_sign=1):
    memory,registers=bytearray(0x300),[0]*32
    memory[0x114]=prior_token;memory[0x10f]=tx_length;memory[0x10c]=address<<1
    memory[0x12e]=token(0x69,address)[2]
    payload=bytes(range(max(0,tx_length-4))) if tx_length!=0x5a else b''
    queued=bytes([0x4b])+payload+crc16(payload)
    memory[0x101:0x101+len(queued)]=queued
    cpu=TraceCPU(build,{'memory':memory,'registers':registers})
    cpu.pc=cpu.labels['USB_handler']
    if levels is None:
        levels,metadata=wire(packet)
    if source_ppm or jitter_profile:
        pins=TolerancePins(cpu,levels,metadata,phase_thirds,source_ppm=source_ppm,
                           jitter_profile=jitter_profile,jitter_sign=jitter_sign)
    else:
        pins=HostPins(cpu,levels,metadata,phase_thirds)
    cpu.io=pins
    selected=None;crc_snapshots=[];lpm_reads=0
    done = 'stream_publication_done' if build['manifest'].get('ack_mode') == 'deferred' else 'L1be8'
    terminals={cpu.labels[name]:name for name in (done,'L1bf0','prototype_done','prototype_drop') if name in cpu.labels}
    for _ in range(20000):
        if cpu.pc in terminals:
            stop=terminals[cpu.pc];break
        for name in ('stream_crc_valid','stream_crc_drop'):
            if name in cpu.labels and cpu.pc==cpu.labels[name]:
                crc_snapshots.append([name,cpu.t,cpu.r[25],cpu.r[30],cpu.r[24]])
        if cpu.pc==cpu.labels.get('L1c4c'):
            selected='ACK'
        if cpu.pc==cpu.labels.get('L1c48'):
            selected='NAK'
        instruction=cpu.step()
        if instruction.op=='lpm':lpm_reads+=1
        if instruction.op=='sbi' and instruction.operands.startswith('0x1b,'):
            pins[0x1b]=0
    else:
        raise AssertionError('Receiver exceeded its instruction bound')
    sop=next((time for time,port,value in cpu.bus_events if port==0x0b and value&6==4),None)
    eop_end_thirds=pins.eop_end_thirds
    turnaround=None if sop is None else sop*3-eop_end_thirds
    if isinstance(turnaround,Fraction):turnaround=float(turnaround)
    sample_addresses={cpu.labels[f'{prefix}{bit}']:(bit,pid)
                      for prefix,pid in (('stream_bit',False),('stream_pid_bit',True))
                      for bit in range(8) if f'{prefix}{bit}' in cpu.labels}
    # V2 routes the next five real bits through dedicated unrolled paths after
    # a stuffed bit. They remain data samples and need the same timestamp check.
    for label,address in cpu.labels.items():
        match=re.fullmatch(r'stream_cooldown_([0-7])_([1-5])',label)
        if match:
            stuffed_bit,step=map(int,match.groups())
            sample_addresses[address]=((stuffed_bit+step)%8,False)
    phases=[];mismatches=[]
    for at,pc,index,within,source,level in pins.reads:
        if pc not in sample_addresses:continue
        expected,pid=sample_addresses[pc]
        if source[0]=='data':
            phases.append(within)
            if source[2]!=expected or (pid and source[1]!=0) or (not pid and source[1]==0):
                mismatches.append([at,expected,list(source),within])
        elif source[0] not in ('eop','dribble','stuff'):
            mismatches.append([at,expected,list(source),within])
    obs=Observation(packet.hex(),phase_thirds,selected,
        bytes(cpu.m[0x116:0x116+len(packet)]).hex(),cpu.m[0x112],cpu.m[0x10d],
        stop,cpu.t,None if sop is None else response_pid(cpu.bus_events,sop),
        turnaround,crc_snapshots,phases,mismatches,lpm_reads)
    return obs,cpu,pins


def require_data(obs,packet,valid=True):
    assert obs.decoded_hex==packet.hex(),('decoded',asdict(obs))
    if valid:
        assert obs.selected=='ACK' and obs.response_pid==0xd2,('ACK',asdict(obs))
        assert obs.published_length==len(packet),('publication',asdict(obs))
        assert obs.turnaround_thirds is not None and 64<=obs.turnaround_thirds<=208,('turnaround',asdict(obs))
        assert not obs.sample_mismatches,('sample bit',asdict(obs))
        # Quarter-bit boundaries are reported separately. Exact same-bit
        # sampling is mandatory; electrical jitter margins need more than it.
    else:
        # Empty DATA0 is suppressed later by inherited packet classification.
        # Check CRC rejection itself so that suppression cannot mask a bad gate.
        assert not any(item[0]=='stream_crc_valid' for item in obs.crc_snapshots),('corrupt CRC gate',asdict(obs))
        assert obs.selected is None and obs.response_pid is None,('corrupt ACK',asdict(obs))
        assert obs.published_length==0,('corrupt publication',asdict(obs))


def data_cases(suite):
    phases=[-45,-24,-9,0] if suite=='smoke' else list(range(-47,1))
    values=(0,255) if suite=='smoke' else (0,255,0x55,0xaa,0x3f,0xfc,0x7e,0x81)
    for phase in phases:
        for length in range(9):
            for pid in (0xc3,0x4b):
                for value in values:
                    if not length and pid==0xc3:continue
                    payload=bytes([value])*length
                    yield bytes([pid])+payload+crc16(payload),phase


def run_suite(build,suite='smoke'):
    count=0;delays=[];phases=[];max_lpm=0
    for packet,phase in data_cases(suite):
        obs,_,_=receive(build,packet,phase)
        require_data(obs,packet)
        if 'stream_crc_valid' in build['symbols']:
            assert any(snapshot[0]=='stream_crc_valid' and snapshot[2:4]==[0xb0,0x01]
                       for snapshot in obs.crc_snapshots), ('streaming residual',asdict(obs))
        count+=1;delays.append(obs.turnaround_thirds);phases.extend(obs.sample_phases)
        max_lpm=max(max_lpm,obs.lpm_reads)
    report={'suite':suite,'valid_frames':count,'turnaround_cycle_range':[min(delays)/3,max(delays)/3],
            'normal_sample_phase_thirds':[min(phases),max(phases)],
            'quarter_bit_sample_window':[8,24],
            'quarter_bit_window_is_conservative_margin_only':True,
            'all_samples_in_middle_half':all(8<=value<=24 for value in phases),
            'max_table_reads':max_lpm,'nominal_bit_cycles':'32/3',
            'physical_usb_verified':False}
    return report


def diagnose(build, full=False):
    """Continue after failures to expose independent problems; never a pass."""
    summaries={}; failures=[]; cases=0
    for packet,phase in data_cases('positive' if full else 'smoke'):
        obs,_,_=receive(build,packet,phase)
        length=len(packet)-3
        row=summaries.setdefault((length,packet[0]),{
            'payload_bytes':length,'pid':hex(packet[0]),'cases':0,
            'decoded_failures':0,'crc_gate_failures':0,'ack_failures':0,
            'publication_failures':0,'sample_bit_failures':0,
            'turnaround_failures':0,'quarter_window_failures':0,
            'turnaround_thirds':[],'sample_phase_thirds':[]})
        row['cases']+=1;cases+=1
        checks={
            'decoded_failures':obs.decoded_hex!=packet.hex(),
            'crc_gate_failures':not any(item[0]=='stream_crc_valid' for item in obs.crc_snapshots),
            'ack_failures':obs.selected!='ACK' or obs.response_pid!=0xd2,
            'publication_failures':obs.published_length!=len(packet),
            'sample_bit_failures':bool(obs.sample_mismatches),
            'turnaround_failures':obs.turnaround_thirds is None or not 64<=obs.turnaround_thirds<=208,
            'quarter_window_failures':any(not 8<=value<=24 for value in obs.sample_phases),
        }
        for name,failed in checks.items():row[name]+=failed
        if obs.turnaround_thirds is not None:row['turnaround_thirds'].append(obs.turnaround_thirds)
        row['sample_phase_thirds'].extend(obs.sample_phases)
        if any(checks.values()) and len(failures)<12:
            failures.append({'checks':checks,'observation':asdict(obs)})
    for row in summaries.values():
        for name in ('turnaround_thirds','sample_phase_thirds'):
            values=row[name];row[name]=[min(values),max(values)] if values else []
    return {'result':'DIAGNOSTIC ONLY','sha256':build['sha256'],'cases':cases,
            'rows':list(summaries.values()),'first_failures':failures}


def diagnose_dribble(build, full=False):
    """Six is the total transition-free tail, not six arbitrary extra bits."""
    rows=[]; failures=[]; cases=0
    phases=range(-47,1) if full else (-45,-24,-9,0)
    patterns=(0,255,0x7e,0x81) if full else (0x7e,)
    for length in range(9):
        for pid in (0xc3,0x4b):
            if not length and pid==0xc3:continue
            for value in patterns:
                payload=bytes([value])*length
                packet=bytes([pid])+payload+crc16(payload)
                original,_=wire(packet)
                last=2;last_transition=0
                for index,level in enumerate(original[:-3]):
                    if level!=last:last_transition=index
                    last=level
                tail=len(original)-3-last_transition
                for extra in range(7):
                    row={'payload_bytes':length,'pid':hex(pid),'pattern':value,
                         'extra_bits':extra,'tail_intervals':tail+extra,
                         'within_six_intervals':tail+extra<=6,'cases':0,
                         'decoded_failures':0,'crc_gate_failures':0,'ack_failures':0,
                         'publication_failures':0,'sample_bit_failures':0,'turnaround_failures':0,
                         'turnaround_thirds':[]}
                    for phase in phases:
                        levels,metadata=wire(packet,dribble=(1,)*extra)
                        obs,_,_=receive(build,packet,phase,levels=levels,metadata=metadata)
                        cases+=1;row['cases']+=1
                        checks={
                            'decoded_failures':obs.decoded_hex!=packet.hex(),
                            'crc_gate_failures':not any(item[0]=='stream_crc_valid' and item[2:4]==[0xb0,0x01]
                                                        for item in obs.crc_snapshots),
                            'ack_failures':obs.selected!='ACK' or obs.response_pid!=0xd2,
                            'publication_failures':obs.published_length!=len(packet),
                            'sample_bit_failures':bool(obs.sample_mismatches),
                            'turnaround_failures':obs.turnaround_thirds is None or not 64<=obs.turnaround_thirds<=208,
                        }
                        for key,failed in checks.items():row[key]+=failed
                        if obs.turnaround_thirds is not None:row['turnaround_thirds'].append(obs.turnaround_thirds)
                        if row['within_six_intervals'] and any(checks.values()) and len(failures)<16:
                            failures.append({'tail_intervals':tail+extra,'extra_bits':extra,
                                             'checks':checks,'observation':asdict(obs)})
                    times=row['turnaround_thirds'];row['turnaround_thirds']=[min(times),max(times)] if times else []
                    rows.append(row)
    return {'result':'DIAGNOSTIC ONLY','sha256':build['sha256'],'cases':cases,
            'rows':rows,'first_failures':failures}


def diagnose_tolerance(build, full=False):
    """Bounded, optional digital probes; these do not certify USB compliance."""
    scenarios=[('nominal',0,None,1),('host_fast_500ppm',500,None,1),
               ('host_slow_500ppm',-500,None,1)]
    scenarios += [(f'{profile}_{sign:+d}',0,profile,sign)
                  for profile in JITTER_PROFILES for sign in (-1,1)]
    phases=range(-47,1) if full else (-45,-24,-9,0)
    frames=[]
    for length in (0,1,4,8):
        for pid in (0xc3,0x4b):
            if not length and pid==0xc3:continue
            for value in (0,255,0x7e):
                payload=bytes([value])*length
                frames.append((bytes([pid])+payload+crc16(payload),{},0xd2))
    # The full nominal matrix found a late three-one empty-DATA1 tail that
    # four selected entry phases missed. Keep this known boundary in every
    # optional rate/jitter sweep as well as in the strict regression test.
    for extra in (1,3,5):
        packet=b'\x4b\x00\x00'
        levels,metadata=wire(packet,dribble=(1,)*extra)
        frames.append((packet,{'levels':levels,'metadata':metadata},0xd2))
    for tx_length in (0x5a,4,12):
        frames.append((token(0x69,17),{'prior_token':0,'address':17,'tx_length':tx_length},
                       0x5a if tx_length==0x5a else 0x4b))
    rows=[];failures=[]
    for name,ppm,profile,sign in scenarios:
        row={'scenario':name,'source_ppm':ppm,'jitter_profile':profile,
             'jitter_sign':sign,'cases':0,'decoded_failures':0,'ack_failures':0,
             'crc_gate_failures':0,
             'publication_failures':0,'sample_bit_failures':0,'turnaround_failures':0,
             'turnaround_thirds':[],'sample_phase_thirds':[]}
        if profile:
            row['interval_jitter_ns']={key:float(value) for key,value in differential_edge_errors(profile).items()}
        for packet,options,expected_pid in frames:
            for phase in phases:
                obs,_,_=receive(build,packet,phase,source_ppm=ppm,
                                jitter_profile=profile,jitter_sign=sign,**options)
                data=packet[0] in (0xc3,0x4b)
                checks={
                    'decoded_failures':obs.decoded_hex!=packet.hex(),
                    'crc_gate_failures':data and not any(item[0]=='stream_crc_valid' and item[2:4]==[0xb0,0x01]
                                                        for item in obs.crc_snapshots),
                    'ack_failures':obs.response_pid!=expected_pid,
                    'publication_failures':obs.published_length!=(len(packet) if data else 0),
                    'sample_bit_failures':bool(obs.sample_mismatches),
                    'turnaround_failures':obs.turnaround_thirds is None or not 64<=obs.turnaround_thirds<=208,
                }
                row['cases']+=1
                for key,failed in checks.items():row[key]+=failed
                if obs.turnaround_thirds is not None:row['turnaround_thirds'].append(obs.turnaround_thirds)
                row['sample_phase_thirds'].extend(obs.sample_phases)
                if any(checks.values()) and len(failures)<16:
                    failures.append({'scenario':name,'checks':checks,
                                     'dribble_bits':sum(item[0]=='dribble' for item in options.get('metadata',())),
                                     'observation':asdict(obs)})
        for key in ('turnaround_thirds','sample_phase_thirds'):
            values=row[key];row[key]=[min(values),max(values)] if values else []
        rows.append(row)
    return {
        'result':'DIAGNOSTIC ONLY','sha256':build['sha256'],
        'cases':sum(row['cases'] for row in rows),'rows':rows,'first_failures':failures,
        'assumptions':{
            'receiver_cpu_hz':16_000_000,
            'source_rate_sweep_ppm':[-500,0,500],
            'rate_and_full_interval_jitter_combined':False,
            'reason':'USB 2.0 section 7.1.15.1 already allocates frequency error in jitter budgets.',
            'receiver_interval_jitter_bounds_ns':{'consecutive':75,'paired':45},
            'references':['USB 2.0 sections 7.1.11 and 7.1.15.1',
                          'Table 7-10 TDJR1/TDJR2 and Figure 7-51'],
            'eop':'Two ideal SE0 bit cells, ideal return to J; no EOP skew or width variation.',
            'scope':'Bounded periodic digital edge patterns; no analog rise/fall, electrical noise, or hardware clock measurement.',
            'sample_bit_failures':'Metadata cell mismatch is reported separately from decoded bytes and CRC.',
        },
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=PROTOTYPE/'build/streaming-v2/manifest.json')
    parser.add_argument('--suite',choices=['smoke','positive','diagnostic','diagnostic-full',
                                         'dribble','dribble-full','tolerance','tolerance-full'],default='smoke')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--quiet',action='store_true',help='Print only aggregate diagnostic counts.')
    args=parser.parse_args()
    try:
        build=load_build(args.manifest)
        if args.suite.startswith('tolerance'):
            report=diagnose_tolerance(build,args.suite=='tolerance-full')
        elif args.suite.startswith('dribble'):
            report=diagnose_dribble(build,args.suite=='dribble-full')
        elif args.suite.startswith('diagnostic'):
            report=diagnose(build,args.suite=='diagnostic-full')
        else:
            report=run_suite(build,args.suite)
    except Exception as error:
        print(json.dumps({'result':'FAIL','type':type(error).__name__,'detail':str(error)},indent=2))
        raise SystemExit(1)
    if not args.suite.startswith(('diagnostic','dribble','tolerance')):
        report['result']='PASS'
    if args.report:
        args.report.write_text(json.dumps(report,indent=2)+'\n')
    visible=report
    if args.quiet and 'rows' in report:
        fields=('decoded_failures','crc_gate_failures','ack_failures','publication_failures',
                'sample_bit_failures','turnaround_failures','quarter_window_failures')
        fields=tuple(name for name in fields if any(name in row for row in report['rows']))
        visible={name:report[name] for name in ('result','sha256','cases')}
        visible['failure_counts']={name:sum(row.get(name,0) for row in report['rows']) for name in fields}
        if args.suite.startswith('dribble'):
            legal=[row for row in report['rows'] if row['within_six_intervals']]
            visible['within_six_intervals_cases']=sum(row['cases'] for row in legal)
            visible['within_six_intervals_failures']={name:sum(row.get(name,0) for row in legal) for name in fields}
    print(json.dumps(visible,indent=2))


if __name__=='__main__':main()
