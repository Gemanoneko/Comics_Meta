import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
if (process.platform !== 'win32' || process.arch !== 'x64' || process.env.COMICS_META_BUILD_JOB !== '1') throw new Error('Run installer builds only through the reviewed Windows x64 owned-job route');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
if (path.resolve(process.cwd()) !== root) throw new Error('Installer build must run from its isolated worktree');
// Never use the user's/shared Electron or electron-builder caches.
for (const [name, folder] of [['ELECTRON_CACHE', 'electron'], ['ELECTRON_BUILDER_CACHE', 'electron-builder']]) {
  const owned = path.join(root, 'build', 'cache', folder);
  if (process.env[name] && path.resolve(process.env[name]) !== owned) throw new Error('Build cache must use reviewed owned path: ' + name);
  process.env[name] = owned;
}
await promisify(execFile)('C:/Python314/python.exe', ['-I', '-S', '-B', path.join(root, 'scripts/packaging/assemble-runtime.py'), '--guard-build'], { cwd: root, windowsHide: true, maxBuffer: 1024 * 1024 });
const { build, Platform, Arch } = await import('electron-builder');
// Local artifacts only. Sully owns publication and named-tag release operations.
await build({ config: 'electron-builder.config.cjs', targets: Platform.WINDOWS.createTarget(['nsis'], Arch.x64), publish: 'never' });
