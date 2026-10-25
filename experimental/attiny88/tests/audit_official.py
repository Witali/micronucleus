#!/usr/bin/env python3
"""ATtiny88 audit against AVR encodings/datasheet conditions. Does not emulate USB electrical layer."""
from pathlib import Path
import re, json, hashlib, subprocess, collections
root=Path(__file__).resolve().parent.parent
S=root/'source/micronucleus_t88_audited.S'
BIN=root/'build/bootloader_body.bin'
BASE=root/'reference/upstream_t88_default.bin'
BOOT=0x1b00;OLD=0x1a40;FLASH=8192;PAGE=64
s=S.read_text();b=BIN.read_bytes();original=BASE.read_bytes()
checks=[]; problems=[]
def check(name,ok,details=''):
 checks.append(dict(name=name,passed=bool(ok),detail=details))
 if not ok:problems.append(name+': '+details)
def u16(addr):return int.from_bytes(b[addr-BOOT:addr-BOOT+2],'little')
def signed(v,bits):return v-(1<<bits) if v & (1<<(bits-1)) else v
def branch_target(at,w):
 if (w&0xf000)==0xc000 or (w&0xf000)==0xd000:
  return ((at//2+1+signed(w&0xfff,12))&0xfff)*2
 if (w&0xfc00) in (0xf000,0xf400):
  return ((at//2+1+signed((w>>3)&0x7f,7))&0xfff)*2
 return None
# Parse literal assembly, preserving label and sizes where known
lines=s.splitlines(); syms={}; program=[]; p=BOOT
for line in lines:
 t=line.split('/*')[0].strip()
 if not t or t.startswith(('.', '#', '*', '/', '*/')):
  if t.startswith('.byte'):
   # descriptor uses arbitrary expressions, count commas
   p+=len(t[5:].split(','))
  elif t.startswith('.word'):
   p+=2
  continue
 if t.endswith(':'):
  syms[t[:-1]]=p;continue
 op=t.split()[0].lower()
 if op in ('lds','sts','jmp','call'): n=4
 elif op in ('add','adc','ldi','rjmp','rcall','brbs','brbc','eor','out','in','movw','mov','cpi','cpc','sub','subi','sbci','sbc','std','ldd','sbiw','adiw','push','pop','ret','reti','st','ld','lpm','spm','wdr','nop','andi','ori','or','and','inc','dec','com','neg','ror','lsr','swap','sbi','cbi','sbis','sbic','sbrc','sbrs','cpse','cp','bst','bld','bset','bclr'):
  n=2
 else:
  raise ValueError(f'Unrecognized source op at {p:04X}: {t}')
 program.append((p,op,t,n)); p+=n
check('Code length from assembler source',p==BOOT+len(b),f'source end={p:04X}, binary end={BOOT+len(b):04X}')
check('Loader fits into 1280 reserved bytes',len(b)<=FLASH-BOOT,f'code={len(b)}, reserved={FLASH-BOOT}, spare={FLASH-BOOT-len(b)}')
check('Bootloader page aligned',BOOT%PAGE==0,f'BOOT=0x{BOOT:04x}')
check('Device descriptor reports application size excluding 4-byte postscript',b[2:4]==bytes([(BOOT-4)>>8,(BOOT-4)&255]),f'{b[2:4].hex()} vs {(BOOT-4):04X}')
check('No multiply opcodes / unsupported shortcuts',not re.search(r'^\s*(mul|muls|mulsu|fmul|fmuls|fmulsu|jmp|call|elpm|eijmp|eicall)\b',s,re.M|re.I),'Tiny88 lacks hardware MUL, etc')
# Boot reset vector wrap at 4K program words
rjmp=candidate=(0xc000|((BOOT//2-1)&0x0fff))
check('Reset RJMP 12-bit PC wrapping reaches 0x1b00',(((rjmp&0xfff)+1)&0xfff)==BOOT//2,f'opcode=0x{rjmp:04x}')
# Postscript branch
app=syms['app_jump'];word=u16(app)
check('Exit jump targets 4-byte preloader postscript', branch_target(app,word)==BOOT-4,f'addr={app:#x}, opcode={word:04x}, target={branch_target(app,word):#x}')
# flash programming registers and proximity of writes: SPMCSR 0x57 SRAM = 0x37 IO, values 0x01/03/05/0x11
spms=[(p,op,t) for p,op,t,n in program if op=='spm']
check('All expected SPM instructions present',len(spms)>=3,f'found={len(spms)}, addresses={[hex(x[0]) for x in spms]}')
for at,op,t in spms:
 preceding=[(addr,o,raw) for addr,o,raw,n in program if addr<at and addr>=at-8]
 # On all SPM paths, immediately preceding opcode must write SPMCSR, STS SRAM 0x0057 or OUT I/O 0x37
 prev=[x for x in program if x[0]+x[3]==at]
 ok=any(re.match(r'\s*(sts\s+0x0057,|out\s+0x37,)', x[2],re.I) for x in prev)
 check(f'SPM write enable is immediately before instruction {at:#x}',ok,'; '.join(x[2] for x in prev))
# Independent LDD/STD displacement encoding. q bits [13,11,10,2,1,0]. Compare exact q/reg/Y/Z.
qerrors=[]; count_ld=0
for at,op,t,n in program:
 if op not in ('ldd','std'):continue
 word=u16(at)
 qr=((word>>8)&0x20)|((word>>7)&0x18)|(word&7)
 m=re.search(r'\b([YZ])\+(\d+)\b',t)
 if not m: qerrors.append((hex(at),'no displacement',t)); continue
 q=int(m.group(2));target=m.group(1)
 reg=int(re.search(r'\br(\d+)\b',t).group(1))
 detected_reg=(word>>4)&31
 decodedbase='Y' if (word&8) else 'Z'
 is_store=bool(word&0x200)
 if (q,reg,target,op=='std')!=(qr,detected_reg,decodedbase,is_store):qerrors.append((hex(at),t,qr,detected_reg,decodedbase,is_store,hex(word)))
 count_ld+=1
check('All LDD/STD opcodes match register, base and 6-bit displacement',not qerrors,f'tested={count_ld}; failures={qerrors[:10]}')
# Internal jumps must land on instruction beginnings or an explicit postscript outside code
start_addresses={at for at,_,_,_ in program}
# .word app_jump is code, not parsed insn; include
start_addresses.add(app)
invalid=[]; branches=0
for at,op,t,n in program:
 if op in ('rjmp','rcall','brbc','brbs'):
  w=u16(at); dest=branch_target(at,w);branches+=1
  if dest not in start_addresses and dest!=BOOT-4:invalid.append((hex(at),t,hex(dest)))
check('All relative jumps/calls land at instruction boundaries',not invalid,f'checked={branches}, invalid={invalid[:15]}')
# compare low-level routines raw identical original and optimized
crca=syms['usb_crc16_append']; usba=syms['USB_handler']; pagea=syms['usb_program_page'];
segments=[]
for name,olda,newa,oldend,newend in [('usb_crc16_append',0x1a8c,crca,0x1ab8,usba),('USB_handler',0x1ab8,usba,0x1cce,pagea)]:
 orig=original[olda-OLD:oldend-OLD];now=b[newa-BOOT:newend-BOOT]
 check(f'{name} binary byte-identical',now==orig,f'old={olda:#x}, new={newa:#x}, length={len(now)}, SHA256={hashlib.sha256(now).hexdigest()}')
 segments.append(name)
# Verify the source contains an explicit 64-byte page-base alignment before page write.
pagewrite_source=s[s.find('L1d86:'):s.find('L1d9a:')]
check('Page write Z address zeroes PCWORD bits before SPM', bool(re.search(r'andi\s+r30,\s*0xc0',pagewrite_source,re.I)),'required by ATtiny88 datasheet §19.3')
# Change limits and hardware caveats
check('Program text region ends at flash address < 0x2000',BOOT+len(b)<=FLASH)
check('SPM CSR addresses used are official 0x57 data / 0x37 IO', bool(re.search(r'\bsts\s+0x0057',s)) and bool(re.search(r'\bout\s+0x37',s)))
check('No unresolved external or pseudocode placeholder',not ('<unknown>' in s or 'TODO' in s))
# Ensure Intel HEX and ISP image consistent (including postscript FF and correct reset vector)
isp=(root/'build/ISP_fresh.bin').read_bytes()
check('ISP image correctly sized',len(isp)==FLASH)
check('ISP reset vector correct',int.from_bytes(isp[:2],'little')==rjmp)
check('ISP image boot segment identical to compiled binary',isp[BOOT:BOOT+len(b)]==b)
check('ISP image preserved user application erased (no 00 padding)', all(v==0xff for v in isp[2:BOOT]),'This image erases original program; use fresh ISP only')
check('No unconditional LED pin operations in optimized source',not re.search(r'^\s*(sbi|cbi)\s+0x[b],\s*0\b',s,re.M|re.I))
# A documented limitation of earlier differential emulator, NOT proof of SPM correctness
old_sim=(root/'tests/emulator_diff_test.py').read_text()
warnings=[]
if "op in ('spm','wdr','nop'):pass" in old_sim:
 warnings.append('Older 1200-case differential simulator treats SPM as a no-op; separate SPM tests now cover command-level page flash behaviour.')
warnings.extend(['No physical USB signalling test performed; packet turnaround and whole device performance unverified', '16 MHz exceeds ordinary ATtiny88 12 MHz rating; Automotive variant permits 16 MHz at sufficient VCC'])
spm_tests=json.loads((root/'tests/spm_boundary_tests.json').read_text())
check('Separate SPM boundary/flash model tests executed',spm_tests['tests']>=30 and spm_tests['result'].startswith('OPTIMIZED PASS'),f"tests={spm_tests['tests']}, legacy violations={spm_tests['legacy_violations']}")
res={ 'audited_binary':'micronucleus_t88_bootloader_body.bin', 'code_bytes':len(b),'start_address':hex(BOOT),'result':'STATIC PASS; HARDWARE NOT TESTED' if not problems else 'ISSUES FOUND', 'checks':checks, 'problems':problems,'warnings':warnings,'limitations':['No physical USB transmission/receive verification','Older randomized tests simulate neither real SPM nor USB electrical behavior','Disassembly supplied by LLVM omits q[4:3] for some LDD/STD; independent decoding validated them','Actual fuse bits and board clock not read from hardware'] }
out=root/'tests/official_audit.json';out.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n')
for c in checks:print(('PASS' if c['passed'] else 'FAIL'),c['name'],c['detail'])
print('ISSUES',len(problems));print('JSON',out)
