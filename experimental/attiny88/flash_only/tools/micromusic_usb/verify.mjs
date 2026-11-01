// Compare two independent instruction executors on one immutable wire fixture.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {loadMicroMusic, runRequest} from './core.mjs';

const filename = process.argv[2];
if (!filename) throw new Error('Usage: node verify.mjs fixtures.json; set MICROMUSIC_ROOT.');
const fixtures = JSON.parse((await readFile(filename, 'utf8')).replace(/^\uFEFF/, ''));
assert.equal(fixtures.schema, 'micronucleus-micromusic-usb-v1');
const library = await loadMicroMusic();
const errors = [];
let tested = 0;
for (const fixture of fixtures.cases) {
    tested++;
    try {
        const actual = await runRequest({...fixture, artifact: fixtures.artifact}, library);
        for (const key of ['cycles', 'registers', 'sreg', 'memory', 'events', 'pinReads', 'checkpoints'])
            assert.deepEqual(actual[key], fixture.expected[key], `${fixture.name}: ${key}`);
    } catch (error) {
        errors.push({name: fixture.name, error: error.message});
        if (errors.length === 10) break;
    }
}
process.stdout.write(JSON.stringify({body: fixtures.artifact.sha256, bytes: fixtures.artifact.size,
    cases: fixtures.cases.length, tested, errors, sourceHashes: library.hashes}, null, 2) + '\n');
if (errors.length) process.exitCode = 1;
