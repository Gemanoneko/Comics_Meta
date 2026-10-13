import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createRequire } from 'node:module';
const run = promisify(execFile);
const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const build = path.join(root, 'build');
const stage = path.join(build, 'staged');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const permittedHosts = new Set(['www.python.org', 'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com', 'files.pythonhosted.org']);

async function plain(target) {
  for (let current = path.resolve(target); ; current = path.dirname(current)) {
    try { if ((await fs.lstat(current)).isSymbolicLink()) throw new Error('Reparse path refused: ' + current); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (path.dirname(current) === current) break;
  }
}
async function download(item) {
  if (!/^[A-Za-z0-9_.-]+$/.test(item.filename) || !/^[a-f0-9]{64}$/.test(item.sha256)) throw new Error('Invalid runtime input manifest entry');
  const destination = path.join(build, 'downloads', item.filename);
  await plain(destination);
  try {
    const existing = await fs.readFile(destination);
    if (hash(existing) !== item.sha256) throw new Error('Existing input checksum mismatch: ' + item.filename);
    return destination;
  } catch (error) { if (error.code !== 'ENOENT') throw error; }
  let url = item.url;
  for (let redirect = 0; redirect <= 5; redirect++) {
    const parsed = new URL(url);
    if (parsed.protocol !== 'https:' || !permittedHosts.has(parsed.hostname) || parsed.username || parsed.password) throw new Error('Download origin refused');
    const response = await fetch(url, { redirect: 'manual', signal: AbortSignal.timeout(120000) });
    if ([301, 302, 303, 307, 308].includes(response.status)) {
      url = new URL(response.headers.get('location'), url).href;
      await response.body?.cancel();
      continue;
    }
    if (!response.ok) throw new Error('Download failed: ' + item.filename + ' HTTP ' + response.status);
    const chunks = [];
    let size = 0;
    for await (const chunk of response.body) {
      size += chunk.length;
      if (size > 150000000) throw new Error('Download size limit exceeded');
      chunks.push(chunk);
    }
    const bytes = Buffer.concat(chunks);
    if (hash(bytes) !== item.sha256) throw new Error('Downloaded input checksum mismatch: ' + item.filename);
    await fs.writeFile(destination, bytes, { flag: 'wx' });
    return destination;
  }
  throw new Error('Download redirect limit exceeded');
}
async function inventory(directory) {
  const result = [];
  async function walk(current) {
    for (const entry of (await fs.readdir(current, { withFileTypes: true })).sort((a,b) => a.name.localeCompare(b.name))) {
      const filename = path.join(current, entry.name);
      await plain(filename);
      if (entry.isDirectory()) await walk(filename);
      else if (entry.isFile()) result.push({ path: path.relative(directory, filename).replaceAll('\\', '/'), sha256: hash(await fs.readFile(filename)) });
      else throw new Error('Non-regular staged file refused');
    }
  }
  await walk(directory);
  return result;
}
async function main() {
  if (process.platform !== 'win32' || process.arch !== 'x64' || process.env.COMICS_META_BUILD_JOB !== '1') throw new Error('Run only inside the reviewed Windows x64 owned-job build route');
  await plain(build);
  // Native lstat attributes reject all Windows reparse types, including dangling outputs.
  await run('C:/Python314/python.exe', ['-I', '-S', '-B', path.join(root, 'scripts/packaging/assemble-runtime.py'), '--guard-prepare'], { cwd: root, windowsHide: true, maxBuffer: 1024 * 1024 });
  const lock = JSON.parse(await fs.readFile(path.join(root, 'scripts/packaging/runtime-lock.json'), 'utf8'));
  const actualPins = (await fs.readFile(path.join(root, 'requirements.txt'), 'utf8')).split(/\r?\n/).map(s => s.trim()).filter(s => s && !s.startsWith('#')).sort();
  const lockedPins = lock.wheels.map(w => w.name + '==' + w.version).sort();
  if (JSON.stringify(actualPins) !== JSON.stringify(lockedPins)) throw new Error('Runtime wheel lock differs from requirements.txt');
  if (lock.schema !== 1 || lock.platform !== 'win32-x64') throw new Error('Unsupported runtime lock');
  await fs.mkdir(path.join(build, 'downloads'), { recursive: true });
  // Sequential transfers share the enclosing job deadline; never launch parallel builds.
  for (const item of [lock.python, ...lock.wheels, lock.sevenZip]) await download(item);
  await run('C:/Python314/python.exe', ['-I', '-S', '-B', path.join(root, 'scripts/packaging/assemble-runtime.py')], { cwd: root, windowsHide: true, maxBuffer: 1024 * 1024 });
  const extractor = require('7zip-bin').path7za;
  if (!path.resolve(extractor).startsWith(path.join(root, 'node_modules') + path.sep)) throw new Error('Extractor outside locked build dependency graph');
  await plain(extractor);
  const unpack = path.join(build, 'sevenzip-extracted');
  await plain(unpack);
  try { await fs.lstat(unpack); throw new Error('7-Zip extraction output already exists'); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  await run('C:/Python314/python.exe', ['-I', '-S', '-B', path.join(root, 'scripts/packaging/assemble-runtime.py'), '--guard-extract'], { cwd: root, windowsHide: true, maxBuffer: 1024 * 1024 });
  await run(extractor, ['x', path.join(build, 'downloads', lock.sevenZip.filename), '-o' + unpack, '-y', '-bb0'], { cwd: root, windowsHide: true, maxBuffer: 1024 * 1024 });
  const sevenZip = path.join(stage, 'runtime', '7zip');
  await fs.mkdir(sevenZip, { recursive: true });
  for (const name of ['7z.exe', '7z.dll', 'License.txt']) {
    await plain(path.join(unpack, name));
    await fs.copyFile(path.join(unpack, name), path.join(sevenZip, name), fs.constants.COPYFILE_EXCL);
  }
  const python = path.join(stage, 'runtime', 'python', 'python.exe');
  const validation = 'import sys, importlib.metadata as m; assert sys.version_info[:3] == (3,14,8); ' + lock.wheels.map(w => 'assert m.version(' + JSON.stringify(w.name) + ') == ' + JSON.stringify(w.version)).join('; ') + '; import PIL.Image, playwright.sync_api, greenlet, sqlite3; print("Bundled CPython and exact runtime dependencies ready")';
  await run(python, ['-I', '-B', '-c', validation], { cwd: stage, windowsHide: true, maxBuffer: 1024 * 1024 });
  const formats = await run(path.join(sevenZip, '7z.exe'), ['i'], { cwd: stage, windowsHide: true, maxBuffer: 1024 * 1024 });
  if (!/Rar/.test(formats.stdout)) throw new Error('Bundled 7-Zip lacks RAR support');
  await fs.writeFile(path.join(build, 'staged-manifest.json'), JSON.stringify({ schema: 1, inputs: lock, files: await inventory(stage) }, null, 2) + '\n', { flag: 'wx' });
  console.log('Authenticated embedded runtime staged. No installed Python or 7-Zip dependency.');
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
