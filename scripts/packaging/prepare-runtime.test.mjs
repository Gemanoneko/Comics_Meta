import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {parseListing, acquire, prepare} from './prepare-runtime.mjs';
import contract from './toolchain-inputs.cjs';
const {memberPath, tree, verifyTree, dependencyFingerprint, sha} = contract;
const scratch = process.env.COMICS_META_TEST_SCRATCH;
assert.ok(scratch && path.isAbsolute(scratch), 'explicit isolated test scratch required');
const base = path.join(scratch, 'toolchain-' + randomUUID());
fs.mkdirSync(base, {recursive: true});
const listing = (name, extra = '') => `Path = ${name}\nSize = 12\nAttributes = A\nEncrypted = -\n${extra}`;

test('normal archive members and explicit rcedit projection pass', () => {
  assert.deepEqual(parseListing(listing('Bin\\makensis.exe')), ['Bin/makensis.exe']);
  assert.deepEqual(parseListing(listing('rcedit-x64.exe') + '\n' + listing('darwin/lib.dylib', 'Symbolic Link = target\n'), ['rcedit-x64.exe']), ['rcedit-x64.exe']);
});

test('archive traversal, Windows aliases, links, duplicates and missing projections fail', () => {
  for (const name of ['../escape', '/absolute', 'C:/escape', 'x/../escape', 'x/NUL.txt', 'x/file.', 'x/file:stream'])
    assert.throws(() => memberPath(name));
  assert.throws(() => parseListing(listing('foo', 'Symbolic Link = target\n')), /linked/);
  assert.throws(() => parseListing(listing('Foo') + '\n' + listing('foo')), /duplicate/);
  assert.throws(() => parseListing(listing('foo'), ['missing']), /projection/);
});

test('manifest verifies positive control and refuses modified or extra bytes', () => {
  const dir = path.join(base, 'tree');
  fs.mkdirSync(dir);
  fs.writeFileSync(path.join(dir, 'a'), 'original');
  const manifest = tree(dir);
  verifyTree(dir, manifest);
  fs.writeFileSync(path.join(dir, 'a'), 'changed');
  assert.throws(() => verifyTree(dir, manifest), /manifest mismatch/);
  fs.writeFileSync(path.join(dir, 'a'), 'original');
  fs.writeFileSync(path.join(dir, 'extra'), 'extra');
  assert.throws(() => verifyTree(dir, manifest), /manifest mismatch/);
});

test('only root version bumps preserve the dependency fingerprint', () => {
  const dir = path.join(base, 'lock');
  fs.mkdirSync(dir);
  const pkg = {version: '0.5.0', dependencies: {x: '1.0.0'}};
  const lock = {version: pkg.version, lockfileVersion: 3, packages: {'': {...pkg}, 'node_modules/x': {
    version: '1.0.0', resolved: 'https://registry.npmjs.org/x/-/x-1.0.0.tgz', integrity: 'sha512-YWJjZA=='}}};
  const save = () => {fs.writeFileSync(path.join(dir, 'package.json'), JSON.stringify(pkg)); fs.writeFileSync(path.join(dir, 'package-lock.json'), JSON.stringify(lock));};
  save();
  const first = dependencyFingerprint(dir);
  pkg.version = lock.version = lock.packages[''].version = '0.6.0';
  save();
  assert.equal(dependencyFingerprint(dir), first);
  fs.mkdirSync(path.join(dir, 'scripts/packaging'), {recursive: true});
  for (const filename of ['runtime-lock.json', 'toolchain-lock.json'])
    fs.writeFileSync(path.join(dir, 'scripts/packaging', filename), '{\n  "pin": "original"\n}\n');
  const pins = contract.sourcePins(dir);
  for (const filename of ['runtime-lock.json', 'toolchain-lock.json'])
    fs.writeFileSync(path.join(dir, 'scripts/packaging', filename), '{\r\n  "pin": "original"\r\n}\r\n');
  assert.deepEqual(contract.sourcePins(dir), pins);
  lock.packages['node_modules/x'].integrity = 'sha512-ZWZnaA==';
  save();
  assert.notEqual(dependencyFingerprint(dir), first);
  lock.packages['node_modules/x'].resolved = 'file:elsewhere';
  save();
  assert.throws(() => dependencyFingerprint(dir), /unpinned/);
});

test('download cache reuses authenticated bytes and fails closed on tampering', async () => {
  const dir = path.join(base, 'cache');
  fs.mkdirSync(dir);
  fs.writeFileSync(path.join(dir, 'pinned.zip'), 'good');
  const item = {filename: 'pinned.zip', sha256: sha(Buffer.from('good')), url: 'https://invalid.example/never-requested'};
  assert.equal(await acquire(item, dir, () => 1000), path.join(dir, 'pinned.zip'));
  fs.writeFileSync(path.join(dir, 'pinned.zip'), 'bad');
  await assert.rejects(acquire(item, dir, () => 1000), /checksum mismatch/);
});

test('incomplete inputs cannot build and existing output cannot be overwritten', async () => {
  const dir = path.join(base, 'incomplete');
  fs.mkdirSync(dir);
  fs.writeFileSync(path.join(dir, 'keep'), 'original');
  assert.throws(() => contract.readInputs(base, dir), /inputs incomplete/);
  await assert.rejects(prepare({output: dir, cache: path.join(base, 'cache')}), /output exists/);
  assert.equal(fs.readFileSync(path.join(dir, 'keep'), 'utf8'), 'original');
});
