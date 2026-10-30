"""Execute emitted AVR opcodes against independent low-speed NRZI waveforms.

The model includes clocked GPIO and PCIF, but excludes analog thresholds,
metastability and oscillator drift. Passing this is not USB certification.
"""
import json, os, random
from tests35.phy_model import *


def receive(art, packet, wave, entry):
    cpu=CPU(art,wave,entry)
    exits=complete_frame_entries(art)
    for _ in range(10000):
        if cpu.pc in exits:
            # Incoming DATA CRC16 values may be discarded under the sole
            # approved waiver. Both CRC byte positions/count still matter;
            # PID/payload and all token/handshake bytes must remain exact.
            meaningful=len(packet)-2 if packet[0] in (0xc3,0x4b) else len(packet)
            assert bytes(cpu.m[0x116:0x116+meaningful])==packet[:meaningful],('decoded bytes',packet.hex(),entry,wave.period)
            assert cpu.r[23]==len(packet),('decoded length',packet.hex(),cpu.r[23])
            return cpu
        if cpu.pc==0xFFFE:break
        cpu.step()
    raise AssertionError(('full packet rejected',packet.hex(),entry,wave.period))


def rejects_framing(art, wave, entry):
    cpu=CPU(art,wave,entry)
    exits=complete_frame_entries(art)
    for _ in range(10000):
        if cpu.pc in exits:return False
        if cpu.pc==0xFFFE:return True
        cpu.step()
    raise AssertionError('partial frame did not finish')


def test_receive(art):
    rng=random.Random(0x35E0)
    packets={bytes([0xD2]),bytes([0x5A]),bytes([0x1E])}
    for address in range(128):
        for pid in (0x69,0x2D,0xE1):packets.add(token(pid,address=address))
    for pid in (0xC3,0x4B):
        for length in range(9):
            for value in (0,0xFF,0x55,0xAA):packets.add(data_packet(bytes([value])*length,pid))
            packets.add(data_packet(bytes(rng.randrange(256) for _ in range(length)),pid))
        for value in range(256):packets.add(data_packet(bytes([value]),pid))
    cases=0
    for packet in sorted(packets):receive(art,packet,eop_wave(packet,64/3),8);cases+=1
    dense=[token(0x69),token(0x69,address=127),token(0x2D),token(0x2D,address=127),token(0xE1),
           data_packet(bytes(8)),data_packet(bytes([255])*8),data_packet(bytes([255])*8,0x4B),bytes([0xD2])]
    entries=[quarter/4 for quarter in range(20,157)] if os.environ.get('USB_PHY_EXHAUSTIVE')=='1' else [5,8,16,24,32,38]
    for rate in (1_499_250,1_500_000,1_500_750):
        for width in (10.72,64/3,24):
            for packet in dense:
                for entry in entries:receive(art,packet,eop_wave(packet,width,rate),entry);cases+=1
    for sign in (-1,1):
        jitter=lambda index,line:sign*(0.55 if line==J else -0.55)
        for rate in (1_499_250,1_500_750):
            for width in (10.72,24):
                for packet in dense:
                    for entry in (5,8,16,24,32,38):
                        receive(art,packet,eop_wave(packet,width,rate,jitter=jitter),entry);cases+=1
    print('PASS raw complete-byte packets, rates, phases, 670ns EOP and edge jitter',cases,flush=True)
    return cases


def test_partial(art):
    cases=0
    for length in range(1,8):
        for pattern in range(1<<length):
            bits=bits_wave(b'\xD2')[0].bits+[(pattern>>n)&1 for n in range(length)]
            entries=(5,8,16,24,32,38) if os.environ.get('USB_PHY_EXHAUSTIVE')=='1' else (8,)
            rates=(1_499_250,1_500_000,1_500_750) if os.environ.get('USB_PHY_EXHAUSTIVE')=='1' else (1_500_000,)
            widths=(10.72,64/3,24) if os.environ.get('USB_PHY_EXHAUSTIVE')=='1' else (64/3,)
            for entry in entries:
                for rate in rates:
                    for width in widths:
                        # ACK ends with two ones. Legal dribble may extend
                        # the complete final run to six, never seven.
                        dribble=pattern==(1<<length)-1 and length<=4
                        rejected=rejects_framing(art,from_bits(bits,rate,width),entry)
                        assert rejected!=dribble,('dribble/framing',length,pattern,entry,rate,width)
                        cases+=1
    # Missing final CRC bits can otherwise alias a complete byte with bit7=0.
    for address in range(128):
        packet=token(0x69,address=address);complete=bits_wave(packet)[0].bits
        for missing in range(1,8):
            wire=from_bits(complete[:-missing])
            row=probe(art,packet,address=address,cache=packet[2],wave=wire)
            assert not row['checkpoints']['usb_rx_handle_in'] and not row['bus'],(address,missing,row)
            cases+=1
    print('PASS permitted dribble, malformed tails and truncated token CRC fields',cases,flush=True)
    return cases


def test_stuff_errors(art):
    packets={token(pid,address=address) for pid in (0x69,0x2D,0xE1) for address in range(128)}
    for pid in (0xC3,0x4B):
        for count in range(9):
            for value in (0,255,0x55,0xAA):packets.add(data_packet(bytes([value])*count,pid))
        for value in range(256):packets.add(data_packet(bytes([value]),pid))
    cases=0;routes=set()
    reject_labels={value for name,value in art['symbols'].items()
                   if name.startswith('usb_rx_reject_stuff')}
    def reject(packet,at,entry=8,rate=1_500_000):
        nonlocal cases
        wire=from_bits(bits_wave(packet,at)[0].bits,rate)
        cpu=CPU(art,wire,entry);cpu.m[0x114]=0xE1;cpu.m[0x10f]=0x5A
        if packet[0] in (0x69,0x2D,0xE1):
            cpu.m[0x10c]=packet[1]&127;cpu.r[8]=packet[2]
        detected=False;admitted=False
        names={value:name for name,value in art['symbols'].items() if name.startswith('usb_rx_unstuff_')}
        for _ in range(10000):
            if cpu.pc==0xFFFE:break
            if cpu.pc in names:routes.add(names[cpu.pc])
            if cpu.pc in reject_labels:detected=True
            if cpu.pc==art['symbols']['usb_rx_recovered_j'] and not detected:admitted=True
            cpu.step()
        else:raise AssertionError('malformed-symbol wave did not finish')
        assert detected and not admitted and not cpu.bus_events,(packet.hex(),at,entry,rate,detected,admitted,cpu.bus_events)
        cases+=1
    for packet in sorted(packets):
        for at in bits_wave(packet)[1]:reject(packet,at)
    for packet in (token(0x69,address=63),token(0x69,address=126),token(0xE1,address=7),
                   data_packet(bytes([255])*8),data_packet(bytes([255])*8,0x4B)):
        for at in bits_wave(packet)[1]:
            for rate in (1_499_250,1_500_000,1_500_750):
                for entry in (5,8,16,24,32,38):reject(packet,at,entry,rate)
    required={'usb_rx_unstuff_bit6','usb_rx_unstuff_bit7','usb_rx_unstuff_even_bit','usb_rx_unstuff_odd_bit'}
    assert required<=routes,routes
    print('PASS raw malformed mandatory stuffed zeros, all four RX paths',cases,flush=True)
    return cases


def test_tokens_and_eop(art):
    responses=[];cases=0
    for address in range(128):
        packet=token(0x69,address=address)
        row=probe(art,packet,address=address,cache=packet[2])
        assert row['response'] is not None and 64/3<=row['response']<=208/3,(address,row)
        responses.append(row['response']);cases+=1
    for packet in [token(0x69,endpoint=endpoint) for endpoint in (1,2,15)]+[
            token(0x69)[:2],token(0x69)+b'\0',bytes([0x96])+token(0x69)[1:]]:
        row=probe(art,packet);assert not row['checkpoints']['usb_rx_handle_in'] and not row['bus'],row;cases+=1
    for width in (10.72,64/3,24):
        for entry in (5,8,16,24,32,38):
            packet=token(0x69);row=probe(art,packet,entry,wave=eop_wave(packet,width))
            assert row['response'] is not None and 64/3<=row['response']<=208/3,(width,entry,row)
            responses.append(row['response']);cases+=1
    for recovery in (0,6):
        for entry in (5,8,16,24,32,38):
            packet=token(0x69);row=probe(art,packet,entry,wave=eop_wave(packet,64/3,recovery=recovery))
            assert not row['bus'],(recovery,entry,row);cases+=1
    for entry in (5,8,16,24,32,38):
        packet=token(0x69);row=probe(art,packet,entry,wave=eop_wave(packet,160))
        assert not row['bus'],(entry,row);cases+=1
    print('PASS token admission, physical EOP-J turnaround, held SE0/SE1 silence',cases,
          'response cycles',min(responses),max(responses),flush=True)
    return cases


if __name__=='__main__':
    art=build()
    count=test_receive(art)+test_partial(art)+test_stuff_errors(art)+test_tokens_and_eop(art)
    print('PASS linked PHY waveform cases',count,'bytes',art['size'],'SHA256',art['sha256'],flush=True)
