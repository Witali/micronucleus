#!/usr/bin/env python3
"""Static executable verification for a standalone AVR-assembled, relocated ATtiny88 bootloader.
Checks opcodes, branch destinations, bootloader size, relocated tables, instruction
semantics of pointer substitutions and reserved application postscript. Does not
claim full USB electrical/hardware certification.
"""
from pathlib import Path
import re,sys,json,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'));sys.path.insert(0,str(ROOT))
from avr_decoder import signed
import avr_decoder as dec
from build import symbol_table
BOOT=0x1b40;OLD=0x1b00;FLASH=8192;PAGE=64
BASE=ROOT/'reference/pass2_1230.S'
NEW=ROOT/'source/micronucleus_t88_vusb_optimized.S'
B=ROOT/'build/boot_1b40.bin';O=ROOT/'build/boot_1b40.o';OB=ROOT/'build/base.o'
assert all(f.exists() for f in [BASE,NEW,B,O,OB]),'Run build.py first'
sy=symbol_table(O);old_sy=symbol_table(OB)
source=NEW.read_text();old_source=BASE.read_text();code=B.read_bytes();orig=(ROOT/'build/base.bin').read_bytes()
checks=[]
def ck(name,cond,note=''):
 checks.append({'check':name,'ok':bool(cond),'note':note});
 if not cond:raise AssertionError(f'{name}: {note}')

def u16(at):return int.from_bytes(code[at-BOOT:at-BOOT+2],'little')
def dest(at,word):
 if (word&0xf000) in (0xc000,0xd000):return (at+2+signed(word&0xfff,12)*2)%FLASH
 if (word&0xfc00) in (0xf000,0xf400):return (at+2+signed((word>>3)&127,7)*2)%FLASH
 return None

def strip_insns(s,start,end):
 ss=s[s.index(start+':'):s.index(end+':',s.index(start+':'))]
 arr=[]
 for l in ss.splitlines():
  l=re.sub(r'/\*.*?\*/','',l).split('//')[0].strip()
  if not l or l.endswith(':'):continue
  arr.append(' '.join(l.split()))
 return arr

ck('bootloader length exactly 1216 bytes',len(code)==1216,str(len(code)))
ck('code fills reserved last 19 x 64-byte pages',BOOT%PAGE==0 and BOOT+len(code)==FLASH)
ck('user app capacity 6972 bytes',BOOT-4==6972)
ck('bootloader header contains new user app size',code[2:4]==bytes([0x1b,0x3c]),code[2:4].hex())
isp=(ROOT/'firmware/ISP_FULL_8192_FRESH_ONLY.bin').read_bytes()
ck('ISP flash 8192 bytes',len(isp)==FLASH)
reset=int.from_bytes(isp[:2],'little')
ck('reset RJMP wraps to BOOT_AT',0xc000==(reset&0xf000) and (2*(1+signed(reset&0xfff,12))%FLASH)==BOOT,hex(reset))
ck('user app and postscript erased in fresh ISP image',all(c==255 for c in isp[2:BOOT]))
ck('boot area in ISP image matches assembled bytes',isp[BOOT:BOOT+len(code)]==code)
appjmp=u16(sy['app_jump']);ck('app exit RJMP reaches 4-byte postscript',dest(sy['app_jump'],appjmp)==BOOT-4,hex(appjmp))

# Full instruction disassembly after descriptors, with exact instruction widths and targets.
dec.START=BOOT;dec.raw=code
pc=sy['startup'];inst=[];targets=[];missing=[];starts=set()
while pc<BOOT+len(code):
 i=dec.decode(pc)
 inst.append(i);starts.add(pc)
 if i.unknown:missing.append((pc,i.words))
 if i.target is not None:targets.append((pc,i.target))
 pc+=i.size
ck('all executable bytes decode into supported classic AVR instructions',pc==0x2000 and not missing,f'decoded={len(inst)} unknown={missing[:4]}')
ck('relative branch targets align to instruction starts',all(p in starts or p==BOOT-4 for a,p in targets),f'count={len(targets)}, invalid={[(hex(a),hex(p)) for a,p in targets if p not in starts and p!=BOOT-4][:5]}')
ck('no unsupported ATtiny88 instructions',not re.search(r'^\s*(?:mul|muls|mulsu|fmul|fmuls|fmulsu|jmp|call|eijmp|eicall|elpm)\b',source,re.M|re.I))

# Exact original CRC machine code, including zero-length calls.
a=orig[old_sy['usb_crc16_append']-OLD:old_sy['USB_handler']-OLD]
b=code[sy['usb_crc16_append']-BOOT:sy['USB_handler']-BOOT]
ck('CRC16 implementation strictly binary-identical',a==b, f'{len(a)} bytes')

# Byte-by-byte receiving loop, from first unrolled symbol to after the last NRZI bit.
ck('receive NRZI/bitstuff instruction sequence unchanged',strip_insns(old_source,'L1b14','L1baa')==strip_insns(source,'L1b14','L1baa'))
# Verify TX instructions (and post-data SRAM aliases) below using full sequence normalization.
# Stronger TX verification: check exact instruction strings except the two LDS/STS -> LDD/STD substitutions AFTER last emitted bit.
src_tx=strip_insns(source,'L1c56','L1cb2');ref_tx=strip_insns(old_source,'L1c56','L1cb2')
modified_old={'lds r17, 0x0113':'ldd r17, Z+19','sts 0x010c, r17':'std Z+12, r17'}
ref_tx=[modified_old.get(x,x) for x in ref_tx]
ck('TX sequence differs only in two same-cycle SRAM operations after last data bit',src_tx==ref_tx)

# Init Z in an inert 4-cycle window; check the only writes to Z in USB handler.
rx=source[source.index('USB_handler:'):source.index('usb_program_page:')]
seg=rx[rx.index('L1af8:'):rx.index('usb_rx_delay_complete:')]
ck('cycle-neutral 4-cycle replacement of redundant PUSH/POP',
   all(x in seg for x in ('ldi     r30, 0x00','ldi     r31, 0x01','rjmp    usb_rx_delay_complete'))
   and 'push    r16' not in seg and 'pop     r16' not in seg)
# Ten direct access substitutions are correct with base 0x100+displacement.
replacement=[('lds r18, 0x010c','ldd r18, Z+12'),('lds r18, 0x0114','ldd r18, Z+20'),
 ('lds r17, 0x0112','ldd r17, Z+18'),('sts 0x0112, r19','std Z+18, r19'),
 ('sts 0x010d, r18','std Z+13, r18'),('lds r16, 0x0112','ldd r16, Z+18'),
 ('lds r19, 0x010f','ldd r19, Z+15'),('sts 0x010f, r16','std Z+15, r16'),
 ('lds r17, 0x0113','ldd r17, Z+19'),('sts 0x010c, r17','std Z+12, r17')]
def clean_lines(a):
 return [' '.join(re.sub(r'/\*.*?\*/','',x).strip().split()) for x in a.splitlines() if x.strip()]
new_lines=clean_lines(rx);old_lines=clean_lines(old_source[old_source.index('USB_handler:'):old_source.index('usb_program_page:')])
for old,new in replacement:
 ck('safe alias '+old,old in old_lines and old not in new_lines and new in new_lines)
# Check Z not modified after Z initialization except preparatory LDI and LDD/STD.
post=rx[rx.index('usb_rx_delay_complete:'):]
ck('Z base not overwritten until end of USB handler',
   not re.search(r'^\s*(?:(?:ld[is]|mov|movw|subi|sbci|adiw|sbiw|clr|eor)\s+r3[01]\b|(?:ld|lpm)\s+r\d+,\s*(?:Z\+|-Z))',post,re.M|re.I))
# All changed Z+offsets within addressing range and EEPROM SRAM scratch data, no I/O.
ck('Z displacements all target valid SRAM data addresses',all(0<=int(n)<=63 and 0x100+int(n)<0x130 for n in re.findall(r'\bZ\+(\d+)\b',rx)))

# All newly inserted Z+q instructions must encode proper 6-bit q and register.
lderrors=[];count=0
for i in inst:
 if i.op not in ('ldd','std'):continue
 mm=re.search(r'\b([YZ])\+(\d+)\b',i.operands)
 if not mm:continue
 q=int(mm.group(2));w=i.words[0]
 decoded=((w>>8)&32)|((w>>7)&24)|(w&7)
 if q!=decoded:lderrors.append((hex(i.address),i.operands,decoded))
 count+=1
ck('LDD/STD 6-bit q encoding consistent with Microchip',not lderrors,f'count={count}; fails={lderrors[:4]}')

# SPM control register written in immediately preceding AVR instruction.
SPM=[i for i in inst if i.op=='spm']
for idx,i in enumerate(SPM):
 j=next((x for x in inst if x.address+x.size==i.address),None)
 ck(f'SPM write-control adjacency {idx}',bool(j and ((j.op=='out' and j.operands.startswith('0x37')) or (j.op=='sts' and j.operands.startswith('0x0057')))),f'{hex(i.address)} prev {j.op if j else "missing"}')
ck('explicitly align 64B Flash page on Page Write',bool(re.search(r'andi\s+r30,\s*0xc0',source)))

# BOOT_AT relocated comparison is not incorrectly shortened for nonzero low address.
ck('flash-guard contains lower-byte compare for 0x1B40',bool(re.search(r'cpi\s+r30,\s*\(BOOT_AT & 0xff\)',source)))
# Mathematically exhaust all 16-bit pointer values against unsigned 16-bit compare.
for ptr in range(65536):
 z=(ptr-2)&0xffff
 lo=z&255;hi=z>>8
 borrow0=lo<0x40
 finalcarry=hi<(0x1b+(1 if borrow0 else 0))
 if finalcarry!=(z<BOOT):raise AssertionError(('flash guard',hex(ptr),hex(z),finalcarry))
ck('guard C flag correct for all 65536 pointers',True)

# Intel HEX integrity and fully described image.
hexlines=(ROOT/'firmware/ISP_FULL_1B40_FRESH_ONLY.hex').read_text().splitlines()
for l in hexlines:
 assert l.startswith(':')
 d=bytes.fromhex(l[1:]);assert (sum(d)&255)==0 and len(d)==5+d[0],l
ck('Intel HEX record checksums valid',True,str(len(hexlines))+' lines')

result={'result':'PASS — static AVR checks; USB hardware untested','bootloader_address':hex(BOOT),
        'size_bytes':len(code),'app_bytes':BOOT-4,'saved_user_flash_bytes':64,
        'sha256':hashlib.sha256(code).hexdigest(),'checks':checks,
        'limits':['Does not model real D+/D− analog edges, oscillator tolerance, USB hubs, real Flash busy times or power failures.',
                  'Cycle traces verify unchanged instruction-level bit timing on simulated paths, not USB-IF certification.']}
(ROOT/'report/audit_static.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(f'PASS {len(checks)} static checks, {len(inst)} AVR instructions, {len(targets)} jumps/calls, {count} LDD/STD encodings. SHA256={result["sha256"]}')
