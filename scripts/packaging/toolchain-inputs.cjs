'use strict';
// Preparation/build contract: exact regular-file trees, no reparse entries.
const fs = require('node:fs');
const path = require('node:path');
const {createHash} = require('node:crypto');
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const need = (ok, message) => { if (!ok) throw Error('Toolchain: ' + message); };

function plain(target) {
  target = path.resolve(target);
  for (let p = target;; p = path.dirname(p)) {
    const stat = fs.lstatSync(p, {throwIfNoEntry: false});
    need(!stat?.isSymbolicLink(), 'reparse path refused: ' + p);
    if (path.dirname(p) === p) break;
  }
  return target;
}

function memberPath(name) {
  need(typeof name === 'string' && name.length > 0 && !name.includes('\\'), 'invalid member name');
  for (const part of name.split('/')) {
    need(part && part !== '.' && part !== '..' && !/[<>:"|?*\x00-\x1f]/.test(part)
      && !/[ .]$/.test(part) && !/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(part),
    'unsafe member: ' + name);
  }
  return name;
}

function tree(root) {
  root = plain(root);
  need(fs.statSync(root, {throwIfNoEntry: false})?.isDirectory(), 'directory missing: ' + root);
  const files = [], directories = [];
  function walk(dir) {
    for (const entry of fs.readdirSync(dir, {withFileTypes: true})) {
      const file = path.join(dir, entry.name), relative = path.relative(root, file).split(path.sep).join('/');
      memberPath(relative);
      need(!entry.isSymbolicLink(), 'reparse entry refused: ' + file);
      if (entry.isDirectory()) { directories.push(relative); walk(file); }
      else {
        need(entry.isFile(), 'nonregular entry refused: ' + file);
        const bytes = fs.readFileSync(file);
        files.push({path: relative, size: bytes.length, sha256: sha(bytes)});
      }
    }
  }
  walk(root);
  return {directories: directories.sort(), files: files.sort((a, b) => a.path < b.path ? -1 : a.path > b.path ? 1 : 0)};
}

function dependencyFingerprint(root) {
  const lock = JSON.parse(fs.readFileSync(plain(path.join(root, 'package-lock.json'))));
  const pkg = JSON.parse(fs.readFileSync(plain(path.join(root, 'package.json'))));
  need(lock.lockfileVersion === 3, 'requires package-lock v3');
  const canonical = value => JSON.stringify(Object.entries(value || {}).sort(([a], [b]) => a.localeCompare(b)));
  for (const key of ['dependencies', 'devDependencies', 'optionalDependencies'])
    need(canonical(pkg[key]) === canonical(lock.packages[''][key]), key + '/lock mismatch');
  // Version bumps do not invalidate identical dependency contents.
  delete lock.version;
  delete lock.packages[''].version;
  for (const [location, item] of Object.entries(lock.packages)) {
    if (!location) continue;
    memberPath(location);
    need(location.startsWith('node_modules/') && !item.link && /^https:\/\/registry\.npmjs\.org\//.test(item.resolved)
      && /^sha512-[A-Za-z0-9+/]+={0,2}$/.test(item.integrity), 'unpinned dependency: ' + location);
  }
  return sha(Buffer.from(JSON.stringify(lock)));
}

function sourcePins(root) {
  // Git's Windows checkout may use CRLF. Pin the JSON values, not whitespace.
  const jsonHash = file => sha(Buffer.from(JSON.stringify(JSON.parse(fs.readFileSync(plain(file))))));
  return {dependencies: dependencyFingerprint(root),
    runtime: jsonHash(path.join(root, 'scripts/packaging/runtime-lock.json')),
    native: jsonHash(path.join(root, 'scripts/packaging/toolchain-lock.json'))};
}

function verifyTree(root, expected) {
  need(JSON.stringify(tree(root)) === JSON.stringify(expected), 'manifest mismatch: ' + root);
}

function readInputs(root, inputs) {
  const file = plain(path.join(inputs, 'toolchain-manifest.json'));
  need(fs.statSync(file, {throwIfNoEntry: false})?.isFile(), 'inputs incomplete; run prepare:runtime first: ' + inputs);
  const manifest = JSON.parse(fs.readFileSync(file));
  need(manifest.schema === 1 && manifest.platform === 'win32-x64', 'unsupported manifest');
  need(JSON.stringify(manifest.sources) === JSON.stringify(sourcePins(root)), 'prepared inputs do not match committed pins');
  for (const [key, relative] of Object.entries({native: 'native', capsule: 'capsule', dependencies: 'dependencies/node_modules'}))
    verifyTree(path.join(inputs, relative), manifest.trees[key]);
  return manifest;
}

module.exports = {sha, need, plain, memberPath, tree, dependencyFingerprint, sourcePins, verifyTree, readInputs};
