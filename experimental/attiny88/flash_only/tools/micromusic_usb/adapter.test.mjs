import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadMicroMusic, USBWire, usbCoreClass} from './core.mjs';

const library = await loadMicroMusic();
const Core = usbCoreClass(library), REG = library.AT88_DATA;
const image = (...words) => Uint8Array.from(words.flatMap(word => [word & 255, word >> 8]));
const io = address => address - 32;

test('MicroMusic exposes the required AVRe instructions instead of an adapter executor', () => {
    const cpu = new Core(image(0x9800, 0x9900, 0x9b00, 0xfa00, 0xf800));
    for (let pc = 0; pc < 5; pc++) assert.notEqual(cpu.op[pc], 0);
});

test('IN retains the instruction-start PIN sample; OUT writes on its final edge', () => {
    const input = 0xb000 | (16 << 4) | ((io(REG.PIND) & 48) << 5) | (io(REG.PIND) & 15);
    const output = 0xb800 | (16 << 4) | ((io(REG.PORTD) & 48) << 5) | (io(REG.PORTD) & 15);
    const cpu = new Core(image(input, output), {entry: 8,
        wave: {boundaries: [0, 8], levels: [4, 2]}});
    cpu.step();
    assert.equal(cpu.cyc, 9); assert.equal(cpu.r[16], 4);
    assert.equal(cpu.pinReads[0][0], 7.5 - 1e-7);
    cpu.step();
    assert.deepEqual(cpu.events, [[10, io(REG.PORTD), 4]]);
});

test('PCIF masked W1C preserves unrelated bits and SBI uses its two-clock write edge', () => {
    const sbi = 0x9a00 | (io(REG.PCIFR) << 3) | 2;
    const cpu = new Core(image(sbi), {wave: {boundaries: [0, 4], levels: [4, 2]}});
    cpu.data[REG.PCIFR] = 3; cpu.step();
    assert.equal(cpu.clearAt, 10); assert.equal(cpu.data[REG.PCIFR], 3);
    cpu.writeIO(io(REG.PCIFR), 1, 1); assert.equal(cpu.data[REG.PCIFR], 2);
});

test('PCINT same-edge set/clear priority is explicit and independently selectable', () => {
    for (const flagPriority of ['set', 'clear']) {
        const cpu = new Core(image(0), {entry: 8, flagPriority,
            wave: {boundaries: [0.75], levels: [4]}});
        cpu.clearAt = 3; // This low-half-cycle edge gives set events at 3 and 4.
        assert.equal(cpu.pendingPCIF(3), flagPriority === 'set');
        assert.equal(cpu.pendingPCIF(4), true);
    }
});

test('bad wire ordering and unsupported programming fail explicitly', () => {
    assert.throws(() => new USBWire({boundaries: [2, 1], levels: [2, 4]}), /increasing/);
    const cpu = new Core(image(0x95e8));
    assert.throws(() => cpu.step(), /Unsupported|unsupported/);
    assert.throws(() => cpu.writeIO(io(REG.SPMCSR), 1), /programming/);
});
