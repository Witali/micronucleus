#!/usr/bin/env python3
"""Execute complete USB handler/foreground continuations across host packets.

The older independent AVR interpreter executes every opcode. Host edges latch
PCIF2 asynchronously, with write-one-to-clear at the instruction completion.
The schedule uses nominal32/3-cycle bits and the two-bit minimum host gap.
No hardware, NVM operation, forced foreground release, or forced re-entry is used.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass,asdict
import json
from pathlib import Path
import sys

from verify_streaming import TraceCPU,load_build,wire,token,crc16,response_pid,PROTOTYPE
from test_vusb_timing import dec

RX_LENGTH=0x112
RX_TOKEN=0x10d
PENDING_TOKEN=0x114
RX_BASE=0x116
ACK_WINDOW=0x12c
MEM_PROGRESS=0x134


def instruction(cpu,pc):
    dec.START=cpu.base;dec.raw=bytes(cpu.flash[cpu.base:])
    return dec.decode(pc)


@dataclass
class HostPacket:
    name:str
    data:bytes
    start:int
    levels:list
    metadata:list

    @property
    def eop_end(self):return self.start+(len(self.levels)-1)*32


class PacketPins(dict):
    def __init__(self,cpu):
        super().__init__({0x09:2,0x0a:0,0x0b:2,0x1b:0})
        self.cpu=cpu;self.packets=[];self.edges=[];self.edge_index=0;self.flag=0
        self.reads=[]

    def add(self,name,data,start):
        levels,metadata=wire(data)
        packet=HostPacket(name,bytes(data),start,levels,metadata)
        assert not self.packets or start>=self.packets[-1].eop_end+64
        self.packets.append(packet)
        previous=2
        for index,level in enumerate(levels):
            if (level^previous)&4:self.edges.append(start+index*32)
            previous=level
        self.edges.sort()
        return packet

    def sync(self,at):
        while self.edge_index<len(self.edges) and self.edges[self.edge_index]<=at:
            self.flag|=4;self.edge_index+=1

    def packet_at(self,at):
        latest=None
        for packet in self.packets:
            if packet.start>at:break
            latest=packet
        return latest

    def get(self,address,default=0):
        self.sync(self.cpu.t*3)
        if address==0x1b:return self.flag
        if address==0x09:
            packet=self.packet_at(self.cpu.t*3)
            level=2;source=('idle',-1,-1)
            if packet:
                index=(self.cpu.t*3-packet.start)//32
                if 0<=index<len(packet.levels):
                    level=packet.levels[index];source=packet.metadata[index]
            self.reads.append((self.cpu.t,self.cpu.input_pc,None if packet is None else packet.name,source,level))
            return level
        return super().get(address,default)


class PipelineCPU(TraceCPU):
    def __init__(self,build,init):
        super().__init__(build,init)
        self.stores=[];self.crc_valid=[];self.consumers=[];self.tx=[]
        self.instruction_visits=[];self.publication_labels=[];self.classifications=[]
        self.active_tx=None;self.eop_callback=None
        self.port=2;self.drive=0

    def memwrite(self,address,value):
        if address>=32:
            packet=self.io.packet_at(self.t*3) if isinstance(self.io,PacketPins) else None
            self.stores.append({'time':self.t+2,'pc':self.input_pc,'address':address,'value':value&255,
                                'packet':None if packet is None else packet.name})
        super().memwrite(address,value)

    def step(self):
        self.io.sync(self.t*3)
        oldpc=self.pc;ins=instruction(self,oldpc)
        self.instruction_visits.append((self.t,oldpc))
        if oldpc==self.labels.get('stream_crc_valid'):
            packet=self.io.packet_at(self.t*3)
            self.crc_valid.append({'time':self.t,'packet':packet.name,'residual':[self.r[25],self.r[30]]})
        for name in ('stream_publication_reserve_data','stream_publication_reserve_empty',
                     'stream_publication_check','stream_publication_commit','stream_publication_done',
                     'stream_eop_publication_check','stream_eop_publication_commit','stream_eop_publication_done'):
            if oldpc==self.labels.get(name):
                packet=self.io.packet_at(self.t*3)
                self.publication_labels.append({'time':self.t,'label':name,'packet':packet.name,
                    'flag':self.r[27],'staged_count':self.r[25],'staged_token':self.r[24],
                    'rx_length':self.m[RX_LENGTH],'rx_token':self.m[RX_TOKEN],
                    'z':self.r[30]|self.r[31]<<8})
        for label,kind in (('L1c14','IN'),('L1bd8','OUT/SETUP'),('usb_host_ack','ACK')):
            if oldpc==self.labels.get(label):
                packet=self.io.packet_at(self.t*3)
                self.classifications.append({'time':self.t,'packet':packet.name,'kind':kind,
                    'count':self.r[19],'pid':self.r[16],'ack_window':self.m[ACK_WINDOW]})
        if oldpc==self.labels.get('L1d9c') and self.m[RX_LENGTH]:
            packet=self.io.packet_at(self.t*3)
            self.consumers.append({'time':self.t,'packet':packet.name,'length':self.m[RX_LENGTH],
                                  'token':self.m[RX_TOKEN],
                                  'data':bytes(self.m[RX_BASE:RX_BASE+self.m[RX_LENGTH]]).hex()})
        events=len(self.bus_events)
        result=super().step()
        self.io.sync(self.t*3)
        if ins.op in ('out','sbi','cbi'):
            operands=[part.strip() for part in ins.operands.split(',')]
            if int(operands[0],0)==0x1b:
                if ins.op=='out':mask=self.r[int(operands[1][1:])]
                elif ins.op=='sbi':mask=1<<int(operands[1],0)
                else:mask=0 # CBI writes zero to the selected W1C bit.
                self.io.flag&=~mask
        for at,address,value in self.bus_events[events:]:
            if address==0x0a:self.drive=value&6
            if address!=0x0b:continue
            previous=self.port;self.port=value&6
            if self.drive!=6:continue
            if self.active_tx is None and previous==2 and self.port==4:
                self.active_tx={'sop':at,'eop_start':None,'eop_end':None}
            if self.active_tx is not None:
                if self.port==0 and self.active_tx['eop_start'] is None:self.active_tx['eop_start']=at
                if previous==0 and self.port==2 and self.active_tx['eop_start'] is not None:
                    self.active_tx['eop_end']=at
                    self.active_tx['pid']=response_pid(self.bus_events,self.active_tx['sop'])
                    owner=self.io.packet_at(self.active_tx['sop']*3)
                    self.active_tx['host_packet']=owner.name
                    self.active_tx['turnaround_thirds']=self.active_tx['sop']*3-owner.eop_end
                    self.active_tx['r21_at_eop_end']=self.r[21]
                    self.active_tx['flags_at_eop_end']=self.flags
                    self.tx.append(self.active_tx);self.active_tx=None
                    if self.eop_callback:self.eop_callback(self.tx[-1],len(self.tx))
        return result


def make_cpu(build,*,busy=False,initial_in=False,first_pid=0xc3,prior_token=0xe1):
    memory=bytearray(0x300);registers=[0]*32
    memory[0x100]=0xff;memory[0x10f]=12 if initial_in else 0x5a
    memory[0x114]=0 if initial_in else prior_token
    memory[0x12e]=token(0x69)[2]
    payload=bytes(range(8));queued=b'\x4b'+payload+crc16(payload)
    memory[0x101:0x101+len(queued)]=queued
    memory[0x139]=0 if initial_in or prior_token==0x2d else 4 # ST_RECEIVE
    memory[0x133]=64;memory[0x137]=first_pid
    if busy:
        old=b'\xc3'+b'previous'+crc16(b'previous')
        memory[RX_BASE:RX_BASE+len(old)]=old
        memory[RX_LENGTH]=len(old);memory[RX_TOKEN]=0xe1
    cpu=PipelineCPU(build,{'memory':memory,'registers':registers})
    cpu.pc=cpu.labels['USB_handler']
    # Supply the return PC of the actual foreground RCALL, then let RET run.
    pc=cpu.labels['L1d54']
    for _ in range(8):
        ins=instruction(cpu,pc)
        if ins.op=='rcall' and ins.target==cpu.labels['USB_handler']:
            cpu.calls.append(pc+ins.size);break
        pc+=ins.size
    else:raise AssertionError('Cannot locate actual main-loop USB_handler caller')
    cpu.io=PacketPins(cpu)
    return cpu


def data_packet(pid,payload):return bytes([pid])+payload+crc16(payload)


def run_sequence(build,scenario='out-next',phase=0,gap_thirds=64,*,length=8,first_pid=0xc3):
    """Run host packets, device TX, delayed publication and real foreground."""
    assert gap_thirds>=64
    initial_in=scenario in ('in-ack','in-retry')
    if not length:first_pid=0x4b
    prior_token=0x2d if scenario=='setup-single' else 0xe1
    cpu=make_cpu(build,busy=scenario=='busy-rx',initial_in=initial_in,first_pid=first_pid,prior_token=prior_token)
    initial_busy=bytes(cpu.m[RX_BASE:RX_BASE+cpu.m[RX_LENGTH]]).hex()
    first=data_packet(first_pid,bytes(range(length)))
    if scenario=='setup-single':first=data_packet(0xc3,bytes.fromhex('8006000100000800'))
    if initial_in:first=token(0x69)
    if scenario in ('corrupt-retry','corrupt-only'):first=first[:-1]+bytes([first[-1]^1])
    first_host=cpu.io.add('first',first,phase)
    if scenario=='corrupt-retry':
        second=cpu.io.add('retry-token',token(0xe1),first_host.eop_end+640)
        cpu.io.add('retry-data',data_packet(first_pid,bytes(range(length))),second.eop_end+gap_thirds)

    def next_host(tx,index):
        start=tx['eop_end']*3+gap_thirds
        if scenario in ('out-next','out-retry','out-corrupt') and index==1:
            if scenario=='out-retry':start+=512 # Lost ACK recovery waits; no immediate host ACK assumed.
            out=cpu.io.add('next-token',token(0xe1),start)
            pid=first_pid if scenario=='out-retry' else first_pid^0x88
            payload=bytes(range(length)) if scenario=='out-retry' else bytes(range(length,length*2))
            following=data_packet(pid,payload)
            if scenario=='out-corrupt':following=following[:-1]+bytes([following[-1]^1])
            cpu.io.add('next-data',following,out.eop_end+gap_thirds)
        elif scenario in ('out-in','busy-rx') and index==1:
            cpu.io.add('next-in',token(0x69),start)
        elif scenario=='in-ack' and index==1:
            # Token gaps can be arbitrarily long; an ACK SOP must still be
            # within the device-response window. Keep that separate.
            ack=cpu.io.add('host-ack',b'\xd2',tx['eop_end']*3+min(gap_thirds,192))
            cpu.io.add('next-in',token(0x69),ack.eop_end+gap_thirds)
        elif scenario=='in-retry' and index==1:
            cpu.io.add('retry-in',token(0x69),start+512)
        elif scenario=='in-retry' and index==2:
            ack=cpu.io.add('host-ack',b'\xd2',tx['eop_end']*3+min(gap_thirds,192))
            cpu.io.add('next-in',token(0x69),ack.eop_end+gap_thirds)
    cpu.eop_callback=next_host
    for _ in range(45000):
        cpu.step()
        last=cpu.io.packets[-1]
        if cpu.t*3>last.eop_end+2048 and cpu.pc in (
            cpu.labels.get('L1d40'),cpu.labels.get('L1e98'),cpu.labels.get('L1d3a')):
            break
    else:raise AssertionError('Packet pipeline exceeded its instruction bound')
    accepted=[event for event in cpu.stores if event['address']==RX_LENGTH and event['value']]
    publications=[]
    for event in accepted:
        valid=[item for item in cpu.crc_valid if item['packet']==event['packet'] and item['time']<=event['time']]
        publications.append({**event,'after_crc':bool(valid)})
    return {'scenario':scenario,'phase_thirds':phase,'gap_thirds':gap_thirds,
            'payload_length':length,'first_pid':first_pid,'ack_mode':build['manifest'].get('ack_mode','baseline'),
            'prior_token':prior_token,
            'sha256':build['sha256'],'cycles':cpu.t,
            'tx':cpu.tx,'publications':publications,'consumers':cpu.consumers,
            'crc_valid':cpu.crc_valid,'copy_count':cpu.m[MEM_PROGRESS],
            'copied_payload':bytes(cpu.m[0x140:0x140+cpu.m[MEM_PROGRESS]]).hex(),
            'remaining':cpu.m[0x133],'expected_pid':cpu.m[0x137],
            'rx_length':cpu.m[RX_LENGTH],'rx_token':cpu.m[RX_TOKEN],
            'tx_length':cpu.m[0x10f],'ack_window':cpu.m[ACK_WINDOW],
            'publication_labels':cpu.publication_labels,'initial_busy_packet':initial_busy,
            'publication_token_stores':[event for event in cpu.stores if event['address']==RX_TOKEN and event['value']],
            'classifications':cpu.classifications,
            'host_packets':[{'name':p.name,'packet':p.data.hex(),'start':p.start,'eop_end':p.eop_end} for p in cpu.io.packets]},cpu


def require_valid_publication(report):
    assert all(event['after_crc'] for event in report['publications']),report
    for consumer in report['consumers']:
        matching=[event for event in report['publications'] if event['time']<=consumer['time']]
        assert matching or report['scenario']=='busy-rx',report
        assert consumer['token'] in (0xe1,0x2d),report


def assess(report):
    scenario=report['scenario'];length=report['payload_length']
    pids={'single':[0xd2],'setup-single':[0xd2],'corrupt-only':[],'out-next':[0xd2,0xd2],
          'out-retry':[0xd2,0xd2],'out-corrupt':[0xd2],'out-in':[0xd2,0x5a],
          'in-ack':[0x4b,0x5a],'in-retry':[0x4b,0x4b,0x5a],
          'busy-rx':[0x5a,0x5a],'corrupt-retry':[0xd2]}[scenario]
    expected_count=2*length if scenario=='out-next' else 8 if scenario=='busy-rx' else (
        0 if scenario in ('in-ack','in-retry','corrupt-only','setup-single') else length)
    packets={item['name']:item['packet'] for item in report['host_packets']}
    owners=[]
    for consumer in report['consumers']:
        previous=[event for event in report['publications'] if event['time']<=consumer['time']]
        owner=packets[previous[-1]['packet']] if previous else report['initial_busy_packet']
        owners.append(consumer['data']==owner and consumer['length']==len(bytes.fromhex(owner)) and consumer['token']==report['prior_token'])
    checks={
        'publication_after_crc':all(event['after_crc'] for event in report['publications']),
        'token_publication_after_crc':all(any(item['packet']==event['packet'] and item['time']<=event['time']
            for item in report['crc_valid']) for event in report['publication_token_stores']),
        'consumer_has_complete_owned_packet':all(owners),
        'response_sequence':[item['pid'] for item in report['tx']]==pids,
        'turnaround':all(64<=item['turnaround_thirds']<=208 for item in report['tx']),
        'foreground_copied_expected_bytes':report['copy_count']==expected_count,
        'metadata_released':report['rx_length']==0,
    }
    required_tokens={'out-next':('next-token',),'out-retry':('next-token',),'out-corrupt':('next-token',),
        'out-in':('next-in',),'busy-rx':('next-in',),
        'in-ack':('first','host-ack','next-in'),
        'in-retry':('first','retry-in','host-ack','next-in'),
        'corrupt-retry':('retry-token',)}.get(scenario,())
    checks['following_tokens_validated']=all(any(item['packet']==name for item in report['classifications'])
                                           for name in required_tokens)
    if report['ack_mode'] in ('deferred','eop'):
        stages=[item for item in report['publication_labels'] if item['label'] in (
            'stream_publication_commit','stream_eop_publication_commit')]
        checks['pending_metadata_is_reserved']=all(item['flag']==1 and item['rx_length']==0 and item['z']==0x100
            and item['staged_count']==len(bytes.fromhex(packets[item['packet']])) and item['staged_token']==report['prior_token'] for item in stages)
        if report['ack_mode']=='deferred':
            checks['publication_after_ack_eop']=all(any(tx['host_packet']==event['packet'] and tx['pid']==0xd2
                and tx['eop_end']<=event['time'] for tx in report['tx']) for event in report['publications'])
        else:
            checks['publication_in_ack_eop']=all(any(tx['host_packet']==event['packet'] and tx['pid']==0xd2
                and tx['eop_start']<=event['time']<=tx['eop_end'] for tx in report['tx']) for event in report['publications'])
    checks['eop_wait_counter_zero']=all(tx['r21_at_eop_end']==0 for tx in report['tx'])
    return checks


def tx_waveform(cpu,tx):
    """PORTD/DDRD transitions relative to SOP, including drive/release."""
    start=max(at for at,port,value in cpu.bus_events if port==0x0a and value&6==6 and at<=tx['sop'])
    end=min(at for at,port,value in cpu.bus_events if port==0x0a and value&6==0 and at>=tx['eop_end'])+1
    return [(at-tx['sop'],port,value&6) for at,port,value in cpu.bus_events if start<=at<=end]


def compare_waveforms(new_report,new_cpu,old_report,old_cpu):
    matched=[]
    for tx in new_report['tx']:
        candidates=[item for item in old_report['tx'] if item['host_packet']==tx['host_packet'] and item['pid']==tx['pid']]
        if not candidates:continue
        old=candidates[0]
        matched.append({'host_packet':tx['host_packet'],'pid':tx['pid'],
            'same_port_ddr_waveform':tx_waveform(new_cpu,tx)==tx_waveform(old_cpu,old),
            'same_final_flags':tx['flags_at_eop_end']==old['flags_at_eop_end'],
            'same_wait_counter':tx['r21_at_eop_end']==old['r21_at_eop_end']==0,
            'turnaround_change_thirds':tx['turnaround_thirds']-old['turnaround_thirds']})
    return matched


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=PROTOTYPE/'build/streaming-v2/manifest.json')
    parser.add_argument('--scenario',choices=['single','setup-single','corrupt-only','out-next','out-retry','out-corrupt','out-in','in-ack','in-retry','busy-rx','corrupt-retry'])
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--quiet',action='store_true')
    parser.add_argument('--full',action='store_true')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args();build=load_build(args.manifest)
    results=[]
    scenarios=[args.scenario] if args.scenario else ['single','setup-single','corrupt-only','out-next','out-retry','out-corrupt','out-in','in-ack','in-retry','busy-rx','corrupt-retry']
    baseline=load_build(args.baseline) if args.baseline else None
    for scenario in scenarios:
        for phase in (range(-47,1) if args.full else (-45,-24,-9,0)):
            for gap in ((64,65,66,96,128,192,256,512,1024,2048) if args.full else (64,512,2048)):
                result,cpu=run_sequence(build,scenario,phase,gap)
                require_valid_publication(result);result['checks']=assess(result)
                if baseline:
                    old,old_cpu=run_sequence(baseline,scenario,phase,gap)
                    result['baseline_checks']=assess(old)
                    result['new_regressions']=[name for name,passed in result['checks'].items()
                                               if not passed and result['baseline_checks'].get(name,False)]
                    result['tx_waveform_comparison']=compare_waveforms(result,cpu,old,old_cpu)
                results.append(result)
    report={'result':'DIGITAL PIPELINE DIAGNOSTIC','sha256':build['sha256'],'cases':len(results),'rows':results}
    if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
    if args.quiet:
        print(json.dumps({'result':report['result'],'sha256':build['sha256'],'cases':len(results),
            'failed_checks':{name:sum(not row['checks'].get(name,True) for row in results)
                             for name in sorted({name for row in results for name in row['checks']})},
            'new_regressions':sum(bool(row.get('new_regressions')) for row in results)},indent=2))
    else:print(json.dumps(report,indent=2))


if __name__=='__main__':main()
