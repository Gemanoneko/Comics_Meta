const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
module.exports = async function verifyStaged(context) {
  if (process.platform !== 'win32' || process.env.COMICS_META_BUILD_JOB !== '1') throw new Error('Packaging requires the reviewed owned-job build route');
  const root = context.packager.projectDir;
  const stage = path.join(root, 'build', 'staged');
  const manifest = JSON.parse(await fs.readFile(path.join(root, 'build', 'staged-manifest.json'), 'utf8'));
  if (manifest.schema !== 1 || !Array.isArray(manifest.files)) throw new Error('Invalid staged manifest');
  const actual = [];
  async function walk(directory) {
    for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
      const filename = path.join(directory, entry.name);
      if (entry.isSymbolicLink()) throw new Error('Staged reparse point refused');
      if (entry.isDirectory()) await walk(filename);
      else if (entry.isFile()) actual.push({ path: path.relative(stage, filename).replaceAll('\\', '/'), sha256: crypto.createHash('sha256').update(await fs.readFile(filename)).digest('hex') });
      else throw new Error('Non-regular staged file refused');
    }
  }
  await walk(stage);
  const ordered = values => values.sort((a,b) => a.path.localeCompare(b.path));
  if (JSON.stringify(ordered(actual)) !== JSON.stringify(ordered(manifest.files))) throw new Error('Staged runtime/source changed after verification');
  const version = (await fs.readFile(path.join(root, 'VERSION'), 'utf8')).trim();
  const stagedVersion = (await fs.readFile(path.join(stage, 'engine', 'VERSION'), 'utf8')).trim();
  if (version !== context.packager.appInfo.version || stagedVersion !== version) throw new Error('VERSION, package version and bundled engine version differ');
  const lock = JSON.parse(await fs.readFile(path.join(root, 'scripts', 'packaging', 'runtime-lock.json'), 'utf8'));
  if (JSON.stringify(lock) !== JSON.stringify(manifest.inputs)) throw new Error('Runtime lock changed after staging');
  const expectedSource = [];
  for (const name of (await fs.readdir(root)).filter(name => name.endsWith('.py') || ['VERSION', 'requirements.txt'].includes(name))) expectedSource.push({ source: path.join(root, name), packaged: 'engine/' + name });
  async function staticSources(directory) {
    for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
      const filename = path.join(directory, entry.name);
      if (entry.isSymbolicLink()) throw new Error('Static source reparse point refused');
      if (entry.isDirectory()) await staticSources(filename);
      else if (entry.isFile()) expectedSource.push({ source: filename, packaged: 'engine/' + path.relative(root, filename).replaceAll('\\', '/') });
      else throw new Error('Non-regular static source refused');
    }
  }
  await staticSources(path.join(root, 'static'));
  const engine = manifest.files.filter(item => item.path.startsWith('engine/'));
  if (engine.length !== expectedSource.length) throw new Error('Engine source inventory changed after staging');
  for (const item of expectedSource) {
    const frozen = engine.find(file => file.path === item.packaged);
    if (!frozen || crypto.createHash('sha256').update(await fs.readFile(item.source)).digest('hex') !== frozen.sha256) throw new Error('Engine source changed after staging: ' + item.packaged);
  }
};
