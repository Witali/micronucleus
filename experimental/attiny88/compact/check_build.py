from pathlib import Path
import hashlib, subprocess, sys, json,re
p=Path(__file__).resolve().parent
source_dir=p/'variants/strict_usb_optimized'

def run(cmd):
 r=subprocess.run(cmd,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(f'{cmd}:\n{r.stderr}')
 return r.stdout

def build(source, mode='NONE',boot=0x1b00):
 name=Path(source).stem+'_'+mode.lower()+'_'+str(boot)
 obj=p/(name+'.o');binary=p/(name+'.bin')
 relocatable=p/(name+'.reloc.o')
 run(['clang','-target','avr','-mmcu=attiny88',f'-DBOOT_AT={hex(boot)}',f'-DLED_MODE={mode}', '-I',str(p/'vendor'), '-c','-x','assembler-with-cpp',str(source),'-o',str(relocatable)])
 # LLVM 18 retains AVR branches as relocations. Keep the historical .o API,
 # but give opcode tests a fully linked ELF, as in the other ATtiny88 builds.
 # Historical opcode comparisons deliberately place larger baselines beyond
 # 8 KiB. Release fit is checked separately in build_release26.py.
 run(['avr-ld','-m','avr25','--defsym=__TEXT_REGION_LENGTH__=0x10000',
      '-Ttext=0','-e','bootloader_start','-o',str(obj),str(relocatable)])
 reloc=run(['llvm-objdump','-r',str(obj)])
 assert 'R_AVR_' not in reloc,reloc
 run(['llvm-objcopy','-O','binary','-j','.text',str(obj),str(binary)])
 contents=binary.read_bytes()
 assert contents[:boot]==bytes(boot)
 body=contents[boot:]
 syms={}
 for s in run(['llvm-objdump','-t',str(obj)]).splitlines():
  m=re.match(r'^([0-9a-f]+)\s+\S+\s+(?:\.text|\*ABS\*)\s+[0-9a-f]+\s+(.+)$',s)
  if m:syms[m[2]]=int(m[1],16)
 return {'source':str(source),'mode':mode,'size':len(body),'sha256':hashlib.sha256(body).hexdigest(),'boot':boot,'body':body,'symbols':syms,'obj':obj}

if __name__=='__main__':
 base=source_dir/'micronucleus_t88_optimized.S'
 cand=source_dir/'micronucleus_t88_pass16.S'
 for mode in ('NONE','ACTIVE_HIGH','ACTIVE_LOW'):
  a=build(base,mode)
  b=build(cand,mode)
  print(mode,'before',a['size'],a['sha256'],'after',b['size'],b['sha256'])
  for section in (('USB_handler','flash_buffer_append_word'),):
   s,e=section
   buf1=a['body'][a['symbols'][s]-a['boot']:a['symbols'][e]-a['boot']]
   buf2=b['body'][b['symbols'][s]-b['boot']:b['symbols'][e]-b['boot']]
   print('PHY',len(buf1),len(buf2),'identical:',buf1==buf2)
  assert b['size']==a['size']-2
  assert a['body'][a['symbols']['USB_handler']-a['boot']:a['symbols']['flash_buffer_append_word']-a['boot']]==b['body'][b['symbols']['USB_handler']-b['boot']:b['symbols']['flash_buffer_append_word']-b['boot']]
