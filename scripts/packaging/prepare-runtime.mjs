// Explicit Windows preparation, run under the owned-process supervisor with a
// 600000ms total deadline. No installer, browser or package lifecycle script runs.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';
import {randomUUID} from 'node:crypto';
import contract from './toolchain-inputs.cjs';
const {sha, need, plain, memberPath, tree, sourcePins, readInputs} = contract;
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

export function parseListing(text, projection) {
  const all = text.trim().split(/\r?\n\r?\n/).filter(Boolean).map(block => {
    const fields = Object.fromEntries(block.split(/\r?\n/).map(line => {
      const split = line.indexOf(' = ');
      need(split > 0, 'unrecognised archive listing');
      return [line.slice(0, split), line.slice(split + 3)];
    }));
    const name = memberPath((fields.Path || '').replaceAll('\\', '/'));
    return {name, fields};
  });
  const selected = projection ? all.filter(item => projection.includes(item.name)) : all;
  need(selected.length > 0 && (!projection || selected.length === projection.length), 'archive projection incomplete');
  const seen = new Set();
  let bytes = 0;
  for (const {name, fields} of selected) {
    need(!seen.has(name.toLowerCase()), 'duplicate archive member: ' + name);
    seen.add(name.toLowerCase());
    need(!fields['Symbolic Link'] && !fields['Hard Link'] && !/[lL]/.test(fields.Attributes || '')
      && fields.Encrypted !== '+', 'linked/encrypted archive member: ' + name);
    const size = Number(fields.Size);
    need(Number.isSafeInteger(size) && size >= 0 && size <= 512 * 1024 ** 2, 'archive member size: ' + name);
    bytes += size;
    need(bytes <= 1024 ** 3 && seen.size <= 30000, 'archive expansion bound');
  }
  return selected.map(item => item.name);
}

export async function acquire(item, cache, budget) {
  memberPath(item.filename);
  need(!item.filename.includes('/') && /^[a-f0-9]{64}$/.test(item.sha256), 'invalid download pin');
  const file = plain(path.join(cache, item.filename));
  if (fs.existsSync(file)) {
    need(sha(fs.readFileSync(file)) === item.sha256, 'cached checksum mismatch: ' + item.filename);
    return file;
  }
  let url = new URL(item.url), response;
  for (let redirects = 0; redirects <= 5; redirects++) {
    need(url.protocol === 'https:' && !url.username && !url.password, 'HTTPS download required');
    response = await fetch(url, {redirect: 'manual', signal: AbortSignal.timeout(Math.min(90000, budget()))});
    if (![301, 302, 303, 307, 308].includes(response.status)) break;
    need(redirects < 5 && response.headers.has('location'), 'download redirect limit');
    url = new URL(response.headers.get('location'), url);
    await response.body?.cancel();
  }
  need(response.ok, 'download failed: ' + item.filename + ' HTTP ' + response.status);
  const parts = [];
  let size = 0;
  for await (const part of response.body) {
    budget();
    size += part.length;
    need(size <= 256 * 1024 ** 2, 'download size limit: ' + item.filename);
    parts.push(part);
  }
  const bytes = Buffer.concat(parts);
  need(sha(bytes) === item.sha256, 'download checksum mismatch: ' + item.filename);
  fs.writeFileSync(file, bytes, {flag: 'wx'});
  return file;
}

export async function prepare(options = {}) {
  const started = Date.now();
  const budget = () => { const left = 540000 - (Date.now() - started); need(left > 0, 'preparation deadline'); return left; };
  const lock = JSON.parse(fs.readFileSync(path.join(root, 'scripts/packaging/toolchain-lock.json')));
  const runtime = JSON.parse(fs.readFileSync(path.join(root, 'scripts/packaging/runtime-lock.json')));
  need(process.platform === 'win32' && process.arch === 'x64', 'Windows x64 preparation only');
  need(process.versions.node === lock.nodeVersion, 'use Node ' + lock.nodeVersion);
  const output = plain(options.output || path.join(root, 'build/toolchain'));
  const cache = plain(options.cache || path.join(root, 'build/downloads'));
  const sources = sourcePins(root);
  if (options.verify) {
    readInputs(root, output);
    console.log(JSON.stringify({toolchain: 'VERIFIED', output}));
    return;
  }
  need(!fs.existsSync(output), 'output exists; use --verify or choose a fresh --output directory');
  const cacheRelative = path.relative(output, cache);
  need(cacheRelative.startsWith('..' + path.sep) || path.isAbsolute(cacheRelative), 'download cache must be outside prepared output');
  const npmRoot = path.join(path.dirname(process.execPath), 'node_modules/npm');
  need(JSON.parse(fs.readFileSync(plain(path.join(npmRoot, 'package.json')))).version === lock.npmVersion,
    'use npm ' + lock.npmVersion + ' beside Node');
  fs.mkdirSync(path.dirname(output), {recursive: true});
  fs.mkdirSync(cache, {recursive: true});
  // Existing output is never repurposed or removed. Without the final manifest
  // the build refuses it. Do not rename executable trees after running tools:
  // Windows can retain image handles until the outer owned Job has closed.
  fs.mkdirSync(output);
  const work = plain(output + '.preparing-' + randomUUID());
  fs.mkdirSync(work);
  const dependencies = path.join(output, 'dependencies');
  fs.mkdirSync(dependencies);
  for (const filename of ['package.json', 'package-lock.json']) fs.copyFileSync(path.join(root, filename), path.join(dependencies, filename), fs.constants.COPYFILE_EXCL);
  const npmConfig = path.join(work, 'npm');
  fs.mkdirSync(npmConfig);
  for (const filename of ['user.npmrc', 'global.npmrc']) fs.writeFileSync(path.join(npmConfig, filename), '', {flag: 'wx'});
  const env = {...process.env};
  for (const key of Object.keys(env)) if (/^(npm_config_|node_options$|electron_|playwright_|gh_token$|github_token$|npm_token$|node_auth_token$)/i.test(key)) delete env[key];
  Object.assign(env, {NPM_CONFIG_USERCONFIG: path.join(npmConfig, 'user.npmrc'),
    NPM_CONFIG_GLOBALCONFIG: path.join(npmConfig, 'global.npmrc'), NPM_CONFIG_CACHE: path.join(cache, 'npm'),
    NPM_CONFIG_IGNORE_SCRIPTS: 'true', NPM_CONFIG_AUDIT: 'false', NPM_CONFIG_FUND: 'false',
    NPM_CONFIG_UPDATE_NOTIFIER: 'false', ELECTRON_SKIP_BINARY_DOWNLOAD: '1', PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD: '1',
    TEMP: npmConfig, TMP: npmConfig});
  function run(file, args) {
    const result = spawnSync(file, args, {cwd: work, env, windowsHide: true, encoding: 'utf8', timeout: budget(), maxBuffer: 16 * 1024 ** 2});
    need(!result.error && result.status === 0, path.basename(file) + ' failed: ' + (result.error || result.stderr || result.stdout));
    return result.stdout;
  }
  console.log('Preparing lockfile dependencies with lifecycle scripts disabled ...');
  run(process.execPath, [path.join(npmRoot, 'bin/npm-cli.js'), 'ci', '--prefix', dependencies,
    '--ignore-scripts', '--no-audit', '--no-fund', '--include=dev', '--registry=https://registry.npmjs.org', '--fetch-retries=0']);
  const archiver = plain(path.join(dependencies, 'node_modules/7zip-bin/win/x64/7za.exe'));
  need(sha(fs.readFileSync(archiver)) === lock.archiverSha256, '7za binary checksum');
  const downloads = new Map();
  for (const item of [...lock.native, runtime.python, runtime.sevenZip, ...runtime.wheels]) {
    downloads.set(item.filename, await acquire(item, cache, budget));
    console.log('Verified ' + item.filename);
  }
  function extract(item, target, projection = item.projection) {
    const archive = downloads.get(item.filename);
    need(sha(fs.readFileSync(plain(archive))) === item.sha256, 'archive changed: ' + item.filename);
    const names = parseListing(run(archiver, ['l', '-slt', '-ba', '-sccUTF-8', archive]), projection);
    fs.mkdirSync(plain(target), {recursive: true});
    run(archiver, ['x', '-y', '-sccUTF-8', '-o' + target, archive, ...(projection ? names : [])]);
    tree(target);
  }
  const native = path.join(output, 'native'), capsule = path.join(output, 'capsule');
  for (const item of lock.native) extract(item, path.join(native, item.name));
  const python = path.join(capsule, 'runtime/python'), sevenZip = path.join(capsule, 'runtime/7zip');
  extract(runtime.python, python);
  extract(runtime.sevenZip, sevenZip, ['7z.exe', '7z.dll', 'License.txt']);
  const packages = path.join(python, 'Lib/site-packages');
  fs.mkdirSync(packages, {recursive: true});
  const wheels = path.join(work, 'wheels');
  for (const wheel of runtime.wheels) {
    const expanded = path.join(wheels, wheel.name);
    extract(wheel, expanded);
    for (const file of tree(expanded).files) {
      let relative = file.path, targetRoot = packages;
      if (relative.split('/')[0].endsWith('.data')) {
        need(wheel.name === 'greenlet' && relative === 'greenlet-3.5.6.data/headers/greenlet.h', 'unsupported wheel relocation: ' + relative);
        targetRoot = python;
        relative = 'Include/greenlet/greenlet.h';
      }
      const to = plain(path.join(targetRoot, memberPath(relative)));
      fs.mkdirSync(path.dirname(to), {recursive: true});
      fs.copyFileSync(path.join(expanded, file.path), to, fs.constants.COPYFILE_EXCL);
    }
  }
  fs.writeFileSync(plain(path.join(python, 'python314._pth')), 'python314.zip\n.\nLib/site-packages\n../../engine\n');
  for (const filename of ['electron/electron.exe', 'nsis/Bin/makensis.exe', 'winCodeSign/rcedit-x64.exe'])
    need(fs.statSync(plain(path.join(native, filename)), {throwIfNoEntry: false})?.isFile(), 'native layout missing: ' + filename);
  // Import-only smoke: no app, browser, installer or user state.
  const smoke = path.join(work, 'runtime-smoke.py');
  fs.writeFileSync(smoke, 'import sys, sqlite3, PIL, playwright, greenlet, pyee, typing_extensions\nassert sys.version_info[:3] == (3, 14, 8)\nprint("Runtime imports OK")\n', {flag: 'wx'});
  console.log(run(path.join(python, 'python.exe'), ['-I', '-B', smoke]).trim());
  need(run(path.join(sevenZip, '7z.exe'), ['i']).includes('26.04'), '7-Zip runtime version');
  // Scratch intermediates remain beside the output for the host's session-folder
  // cleanup policy. The manifest is the completion marker, published last.
  const manifest = {schema: 1, platform: 'win32-x64', sources,
    nodeVersion: lock.nodeVersion, npmVersion: lock.npmVersion,
    trees: {native: tree(native), capsule: tree(capsule), dependencies: tree(path.join(dependencies, 'node_modules'))}};
  need(JSON.stringify(sourcePins(root)) === JSON.stringify(sources), 'source pins changed during preparation');
  const pending = path.join(output, 'toolchain-manifest.pending.json');
  fs.writeFileSync(pending, JSON.stringify(manifest, null, 2) + '\n', {flag: 'wx'});
  for (const [key, relative] of Object.entries({native: 'native', capsule: 'capsule', dependencies: 'dependencies/node_modules'}))
    contract.verifyTree(path.join(output, relative), manifest.trees[key]);
  need(!fs.existsSync(path.join(output, 'toolchain-manifest.json')), 'completion manifest appeared during preparation');
  fs.renameSync(pending, path.join(output, 'toolchain-manifest.json'));
  console.log(JSON.stringify({toolchain: 'READY', output, manifestSha256: sha(fs.readFileSync(path.join(output, 'toolchain-manifest.json'))),
    python: path.join(output, 'capsule/runtime/python/python.exe'), sevenZip: path.join(output, 'capsule/runtime/7zip/7z.exe')}));
}

function parseArgs(args) {
  const options = {};
  for (let i = 0; i < args.length; i++) {
    const key = args[i];
    if (key === '--verify') options.verify = true;
    else {
      need(['--output', '--cache'].includes(key) && args[i + 1] && !args[i + 1].startsWith('--'), 'usage: prepare-runtime.mjs [--output <fresh-dir>] [--cache <download-dir>] [--verify]');
      options[key.slice(2)] = path.resolve(args[++i]);
    }
  }
  return options;
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href)
  prepare(parseArgs(process.argv.slice(2))).catch(error => { console.error(error.stack || error); process.exitCode = 1; });
