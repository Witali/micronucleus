// Execute the merged reply copier and compare with an independent USB CRC.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
const music=process.env.MICROMUSIC_ROOT||'C:/Work/MicroMusic';
const {AVRCore}=await import(pathToFileURL(path.join(music,'web-player/lib/avr-reference.js')).href);
function crc16(bytes) {
  let crc=0xffff;
  for(const byte of bytes) {
    crc^=byte;
    for(let bit=0;bit<8;bit++)crc=(crc>>>1)^((crc&1)?0xa001:0);
  }
  return crc^0xffff;
}
let seed=0x1688;
function randomByte() {seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return seed&255;}
for(const file of process.argv.slice(2)) {
  const meta=JSON.parse(fs.readFileSync(file)),s=meta.symbols;
  const flash=new Uint8Array(8192).fill(255);
  flash.set(fs.readFileSync(path.join(path.dirname(file),meta.body_file)),meta.image_address);
  const cpu=new AVRCore(flash,null,{target:'attiny88',cpuHz:16000000,fastIdle:false,fastBlocks:false});
  const oldFlash=new Uint8Array(8192).fill(255);
  oldFlash.set(fs.readFileSync(path.join(root,'../variants/strict_usb_verified/BOOTLOADER_BODY_1AC0_VERIFIED.bin')),0x1ac0);
  const oldCPU=new AVRCore(oldFlash,null,{target:'attiny88',cpuHz:16000000,fastIdle:false,fastBlocks:false});
  const oldEntry=meta.baseline_symbols.usb_tx_prepare_pending_reply??meta.baseline_symbols.L1dfc;
  const oldExit=meta.baseline_symbols.bootloader_check_idle_timeout??meta.baseline_symbols.L1e64;
  let maximumExtraCycles=-Infinity;
  let cases=0;
  function check(length,ram,bytes) {
    const address=ram?0x180:0x400;
    for(const target of [cpu,oldCPU]) {
      target.r.fill(0xa5);target.r[1]=0;target.r[2]=ram;target.r[28]=0;target.r[29]=1;
      target.data[0x5d]=255;target.data[0x5e]=2;
      (ram?target.data:target.rom).set(bytes,address);
      target.data[0x10f]=0x5a;target.data[0x100]=length;target.data[0x101]=0xc3;
      target.data[0x110]=address&255;target.data[0x111]=address>>8;
    }
    cpu.pc=s.usb_tx_prepare_pending_reply/2;
    const started=cpu.cyc;
    const payload=bytes.slice(0,Math.min(length,8));
    let mixed=0,shifts=0,complete=false;
    for(let step=0;step<1200;step++) {
      const pc=cpu.pc*2;
      if(pc===s.bootloader_check_idle_timeout){complete=true;break;}
      if(pc===s.usb_crc16_mix_byte||pc===s.usb_crc16_core_end) {
        assert.equal(cpu.r[24],length-payload.length,'CRC clobbered the live message remainder');
      }
      if(pc===s.usb_crc16_core_end+2) {
        assert.equal(cpu.c,Number(payload.length<8),'Final XL comparison supplied the wrong short-packet borrow');
      }
      if(pc===s.usb_tx_copy_flash_payload+2&&cpu.r[23]) {
        assert.equal(cpu.c,1,'CP must supply inverted-CRC carry-in');
        assert.ok(cpu.r[23]<=8,'Packed byte count escaped its low five bits');
      }
      if(pc===s.usb_crc16_mix_byte){mixed++;shifts=0;assert.equal(cpu.r[29],1);}
      if(pc===s.usb_crc16_shift_bit)shifts++;
      if(pc===s.usb_crc16_byte_complete) {
        assert.equal(shifts,8,'Packed counter did not execute eight bits');
        assert.equal(cpu.r[23],payload.length-mixed+1,'Bit loop changed remaining bytes');
      }
      cpu.step();
    }
    assert.ok(complete,'Reply preparation did not finish');
    assert.equal(mixed,payload.length);
    assert.deepEqual(Array.from(cpu.data.slice(0x102,0x102+payload.length)),Array.from(payload));
    const checksum=crc16(payload),at=0x102+payload.length;
    assert.equal(cpu.data[at]|cpu.data[at+1]<<8,checksum);
    assert.equal(cpu.data[0x10f],payload.length+4,'Final XL did not publish the packet length');
    assert.equal(cpu.data[0x100],payload.length===8?length-8:255);
    assert.equal(cpu.data[0x110]|cpu.data[0x111]<<8,address+payload.length);
    assert.equal(cpu.data[0x101],0x4b);assert.equal(cpu.r[1],0);
    const cycles=cpu.cyc-started,oldStarted=oldCPU.cyc;oldCPU.pc=oldEntry/2;
    let oldComplete=false;
    for(let step=0;step<1500;step++) {
      if(oldCPU.pc*2===oldExit){oldComplete=true;break;}
      oldCPU.step();
    }
    assert.ok(oldComplete,'Deployed reply preparation did not finish');
    const oldCycles=oldCPU.cyc-oldStarted;
    maximumExtraCycles=Math.max(maximumExtraCycles,cycles-oldCycles);
    assert.ok(cycles<=oldCycles,`Reply preparation slowed down: ${cycles} > ${oldCycles}`);
    cases++;
  }
  for(const ram of [0,1]) {
    for(let length=0;length<=8;length++)for(let byte=0;byte<256;byte++)check(length,ram,new Uint8Array(8).fill(byte));
    for(let length=9;length<255;length++)check(length,ram,Uint8Array.from({length:8},randomByte));
    for(let run=0;run<2048;run++)check(run%9,ram,Uint8Array.from({length:8},randomByte));
  }
  console.log(`PASS: ${path.basename(path.dirname(file))}: ${cases} Flash/SRAM CRC vectors, packed counter/carry, pointers/lengths; preparation delta <= ${maximumExtraCycles} cycles versus deployed`);
}
