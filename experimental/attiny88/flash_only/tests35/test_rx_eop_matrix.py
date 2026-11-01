"""Dense legal EOP/dribble responses and certified receive-jitter corners.

These are physical waveform tests of linked instructions. A short crossover
must not authorize a packet, and a legal 670 ns EOP must not be discarded.
The separate malformed-token crossover gate remains mandatory.
"""
from tests35 import ep0_model as h
from tests35.ep0_cases import bind
from tests35.phy_model import from_bits, complete_frame_entries
from tests35.rx_jitter_patterns import corners

ENTRIES=(5,8.25,16.5,24.75,32,38.25)


def tails(packet):
    run=0
    for bit in reversed(h.Wave(packet).bits):
        if not bit:break
        run+=1
    return range(7-run)


def wire(packet,tail,rate,width,sign=0):
    out=from_bits(h.Wave(packet).bits+[1]*tail,rate,width)
    # This older, legal 68.75 ns next-edge pattern complements the full
    # 75/45 ns corner families below; it is not a substitute for them.
    if sign:
        for index in range(len(out.bits)):
            out.boundaries[index]+=sign*(0.55 if out.levels[index]==h.J else -0.55)
        out.pin_edges=[];before=h.J
        for when,line in zip(out.boundaries,out.levels):
            if (before^line)&4:out.pin_edges.append(when)
            before=line
    return out


def receive(art,packet,incoming,entry):
    cpu=h.CPU(art,incoming,entry);cpu.r[24:26]=[0xa5,0xb6]
    cpu.m[0x10f]=0x5a
    if packet[0] in (0x69,0x2d,0xe1):
        cpu.m[0x10c]=packet[1];cpu.r[8]=packet[2]
    if packet[0] in (0xc3,0x4b):
        cpu.m[0x114]=0x2d if packet[0]==0xc3 else 0xe1
        cpu.r[11]=0xc0
    targets=complete_frame_entries(art)
    decoded=False
    for _ in range(16000):
        if cpu.pc==0xfffe:break
        if cpu.pc in targets:
            # The approved incoming DATA CRC16 exception permits discarded
            # numeric CRC storage. PID/payload and both CRC byte positions
            # still have to be complete; token CRC5 remains exact.
            meaningful=len(packet)-2 if packet[0] in (0xc3,0x4b) else len(packet)
            decoded|=cpu.r[23]==len(packet) and bytes(cpu.m[0x116:0x116+meaningful])==packet[:meaningful]
        cpu.step()
    else:raise AssertionError('EOP matrix handler did not return')
    assert cpu.r[24:26]==[0xa5,0xb6] and not cpu.raw_stack,'EOP matrix ABI/stack'
    start=next((when for when,io,value in cpu.bus_events if io==11 and value&6==h.K),None)
    response=None if start is None else start-incoming.boundaries[-2]
    return decoded,response


def check(art):
    bind(art);errors=[];responses=[];counts={'data_tails':0,'jitter':0}
    def observe(group,packet,incoming,entry,context):
        decoded,response=receive(art,packet,incoming,entry)
        expected_response=packet[0] in (0x69,0xc3,0x4b)
        if not decoded:errors.append(('decode',group,context))
        if expected_response:
            if response is None or not 2*(85/8)<=response<=6.5*min(85/8,incoming.period):
                errors.append(('response',group,context,response))
            if response is not None:responses.append(response)
        counts[group]+=1

    packets=[h.data_packet(bytes([value])*8,0xc3) for value in (0,255,0x55,0xaa,0x9f,0x15)]
    packets += [h.data_packet(payload,0x4b) for payload in (b'',bytes(8),bytes([255])*8,bytes(range(8)))]
    for packet in packets:
        for tail in tails(packet):
            for rate in (1499250,1500000,1500750):
                for width in (10.72,64/3,24):
                    for sign in (-1,0,1):
                        incoming=wire(packet,tail,rate,width,sign)
                        for entry in ENTRIES:
                            observe('data_tails',packet,incoming,entry,(packet.hex(),tail,rate,width,sign,entry))
    print('EOP legal DATA tail matrix:',counts['data_tails'],'cases;',len(errors),'errors',flush=True)

    packets=[bytes([pid]) for pid in (0xd2,0x5a,0x1e)]
    packets += [h.token(pid,address=address) for pid in (0x69,0x2d,0xe1) for address in (0,63,127)]
    packets += [h.data_packet(bytes([value])*8,pid) for value in (0,255,0x55,0xaa,0x9f,0x15) for pid in (0xc3,0x4b)]
    for packet in packets:
        for rate in (1499250,1500750):
            for width in (10.72,24):
                for incoming in corners(wire(packet,0,rate,width)):
                    for entry in ENTRIES:
                        observe('jitter',packet,incoming,entry,(packet.hex(),rate,width,entry,incoming.jitter_certificate))
    report=dict(bytes=art['size'],sha256=art['sha256'],cases=counts,errors=errors,
                response_range=[min(responses),max(responses)] if responses else None)
    return report


def test():
    import json
    art=h.build();report=check(art)
    output=h.ROOT/'build'/('eop-matrix-'+art['sha256'][:16]+'.json')
    output.write_text(json.dumps(report,indent=2)+'\n')
    print('EOP specification matrix:',report['cases'],'errors',len(report['errors']),report['response_range'],flush=True)
    assert not report['errors'],('EOP matrix failures',report['errors'][:4])


if __name__=='__main__':test()
