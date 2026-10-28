"""Regression: crossover excursions must not authorize a premature USB response.

This is a digital PIN/PCINT model, not an analog or physical-board certification.
Receive mismatches/discards remain a separate reported electrical qualification.
"""
from pathlib import Path
import json
from tests35.phy_model import build, CPU, Wave, data_packet, J, K


def single_crossover(wave, index, width=3.36, fraction=0.5):
    """Insert possible single-ended zero reads around one real J/K crossover.

    USB2 7.1.4.1 permits both lines below VIH for up to210ns at low speed.
    Below VIH does not guarantee a logical zero, so this is a conservative
    digital observation model. SYNC and all other crossovers remain untouched.
    """
    time=wave.boundaries[index]
    level=wave.levels[index]
    assert index>=8 and level in (J,K) and level!=wave.levels[index-1]
    label=wave.labels[index]
    wave.boundaries[index:index+1]=[time-width*fraction,time+width*(1-fraction)]
    wave.levels[index:index+1]=[0,level]
    wave.labels[index:index+1]=[('crossover',label),label]
    wave.pin_edges=[]
    last=J
    for time,level in zip(wave.boundaries,wave.levels):
        if (last^level)&4:wave.pin_edges.append(time)
        last=level
    return wave


def run_matrix(artifact):
    packet=data_packet(bytes([255])*8)
    end_label=artifact['symbols']['usb_rx_end_packet']
    cases=0
    receive_failures=[]
    early_admissions=[]
    for rate in (1_499_250,1_500_000,1_500_750):
        for sign in (-1,0,1):
            jitter=lambda index,level:sign*(0.55 if level==J else -0.55)
            pristine=Wave(packet,rate=rate,jitter=jitter)
            indexes=[index for index in range(8,len(pristine.bits))
                     if pristine.levels[index]!=pristine.levels[index-1]]
            for index in indexes:
                for fraction in (0,0.5,1):
                    for entry in (5,8,16,24,32,38):
                        wave=single_crossover(Wave(packet,rate=rate,jitter=jitter),index,fraction=fraction)
                        true_eop=pristine.boundaries[-3]
                        cpu=CPU(artifact,wave,entry)
                        # Authorize a SETUP DATA and seed a valid stale packet:
                        # an early partial receive must not inherit and ACK it.
                        cpu.m[0x114]=0x2d
                        cpu.r[3]=0
                        cpu.m[0x10f]=0x5a
                        cpu.m[0x116:0x116+len(packet)]=packet
                        first_eop=None
                        early=False
                        for _ in range(10000):
                            if cpu.pc==0xfffe:break
                            if first_eop is None and cpu.pc==end_label:
                                count=(11-cpu.r[23])&255
                                first_eop=dict(time=cpu.t,count=count,
                                    bytes=bytes(cpu.m[0x116:0x116+len(packet)]).hex())
                            cpu.step()
                            # Watch final handler effects, not merely the old
                            # complete-byte phase test: legal dribble may add a
                            # second accepted phase in a future receiver gate.
                            if cpu.t<true_eop and cpu.r[3]==11:early=True
                        else:
                            raise AssertionError('USB handler did not return within its packet bound')
                        if any(time<true_eop and io==0x0a and value&6
                               for time,io,value in cpu.bus_events):early=True
                        key=dict(rate=rate,sign=sign,entry=entry,index=index,fraction=fraction)
                        if early:early_admissions.append(key)
                        if first_eop is None or first_eop['time']<true_eop or first_eop['count']!=len(packet) or first_eop['bytes']!=packet.hex():
                            receive_failures.append(key)
                        cases+=1
    assert cases==3564,cases
    report=dict(cases=cases,early_admissions=early_admissions,
                electrical_tolerance_receive_failures=len(receive_failures),
                unresolved_reference_failures=164,
                model='Digital synchronized PIN/PCINT only; no analog or board claim')
    assert not early_admissions,('premature USB admission/drive',early_admissions[:8])
    return report


if __name__=='__main__':
    artifact=build()
    report=run_matrix(artifact)
    out=Path(__file__).resolve().parent.parent/'build'/'usb-crossover-report.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+'\n')
    print(f"PASS {report['cases']} crossover cases; zero premature USB admissions")
    print(f"QUALIFICATION: {report['electrical_tolerance_receive_failures']} receive mismatches/discards; digital model only")
