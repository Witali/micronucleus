// Exhaust the actual Flash-read guard over every 16-bit address and length 1..8.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const music=process.env.MICROMUSIC_ROOT||'C:/Work/MicroMusic';
const {AVRCore}=await import(pathToFileURL(path.join(music,'web-player/lib/avr-reference.js')).href);
for(const file of process.argv.slice(2)) {
  const meta=JSON.parse(fs.readFileSync(file)),symbols=meta.symbols;
  const flash=new Uint8Array(8192).fill(255);
  flash.set(fs.readFileSync(path.join(path.dirname(file),meta.body_file)),meta.image_address);
  const cpu=new AVRCore(flash,null,{target:'attiny88',cpuHz:16000000,fastIdle:false,fastBlocks:false});
  cpu.r[28]=0;cpu.r[29]=1;
  function check(address,length,index=0) {
    cpu.data.set([address&255,address>>8,index&255,index>>8,length&255,length>>8],0x119);
    cpu.pc=symbols.flash_read/2;
    for(let step=0;step<30;step++) {
      const pc=cpu.pc*2;
      if(pc===symbols.usb_reply_set_pointer||pc===symbols.ee_empty) {
        const expected=index===0&&length>=1&&length<=8&&address+length<=meta.application_bytes;
        assert.equal(pc===symbols.usb_reply_set_pointer,expected,`Address ${address}, length ${length}, index ${index}`);
        if(expected)assert.equal(cpu.r[18]|cpu.r[19]<<8,address,'Read pointer changed');
        return;
      }
      cpu.step();
    }
    throw new Error('Flash-read guard did not reach a result');
  }
  for(let address=0;address<65536;address++)for(let length=1;length<=8;length++)check(address,length);
  for(const address of [0,1,meta.application_bytes-8,meta.application_bytes-1,meta.application_bytes,65535]) {
    for(const length of [0,9,255,256,65535])check(address,length);
    for(const index of [1,255,256,65535])check(address,1,index);
  }
  console.log(`PASS: ${path.basename(path.dirname(file))}: 524288 Flash address/length combinations, invalid lengths/index and unchanged pointers`);
}
